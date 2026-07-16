# Comportement du GreedyAgent dans `simulation_exchange.py`

Ce document explique **comment `simulation_exchange.py` pilote un (ou deux) `GreedyAgent`**
pour leur faire **exploiter les zones d'échange `Y`**, et comment il mesure le nombre de
pas nécessaires pour finir un niveau. Il se concentre **uniquement** sur ce fichier : la
logique interne de l'agent (`agent.py`) est traitée comme une **boîte noire** dont on
rappelle seulement le strict nécessaire.

> **La boîte noire en une phrase.** Un `GreedyAgent` vise la recette de plus haute **valeur**
> et, tick par tick, dirige *son* chef vers l'action utile la **moins coûteuse** (en pas).
> **Livré à lui-même, il n'utilise JAMAIS une zone d'échange pour aider** : il ne pose sur un
> comptoir que pour *jeter* un objet inutile. Sur un layout où tout lui est accessible, il
> fait donc le **tour complet** au lieu de passer par une zone.
>
> **Le rôle de `simulation_exchange.py`.** Ajouter une **couche de coordination** par-dessus
> les agents pour qu'ils exploitent les zones `Y` — *quand c'est utile* — et **mesurer** le
> gain : nombre de pas AVEC zones vs SANS.

---

## Sommaire

1. [Ce que fait le fichier](#1-ce-que-fait-le-fichier)
2. [Comment les agents sont fabriqués et pilotés](#2-comment-les-agents-sont-fabriqués-et-pilotés)
3. [Le choix de la politique selon la topologie](#3-le-choix-de-la-politique-selon-la-topologie)
4. [Politique 1 — `GreedyPair` (référence, sans zones)](#4-politique-1--greedypair)
5. [Politique 2 — `ExchangePolicy` (layouts séparés)](#5-politique-2--exchangepolicy)
6. [Politique 3 — `CoopExchangePolicy` (layouts connexes)](#6-politique-3--coopexchangepolicy)
7. [La dé-confliction des déplacements](#7-la-dé-confliction-des-déplacements)
8. [La mesure et les trois modes d'exécution](#8-la-mesure-et-les-trois-modes-dexécution)
9. [Tableaux de synthèse](#9-tableaux-de-synthèse)

---

## 1. Ce que fait le fichier

`simulation_exchange.py` est un **banc d'essai** hors-jeu (sans serveur Flask) qui répond à
une question : **« ce layout gagne-t-il des pas grâce aux zones d'échange, et combien ? »**

Il joue une partie complète en **deux variantes** puis compare :

| Variante | Zones `Y` | Comportement |
|---|---|---|
| **AVEC zones** | utilisables (dépôt/retrait autorisés) | couche de relais active |
| **SANS zones** | neutralisées (les `Y` deviennent de simples murs) | deux greedy libres |

La bascule se fait dans `build_env(..., exchange=True/False)` : quand `exchange=False`, la
liste `counter_goals` (les positions `Y`) est **vidée** → l'agent ne peut plus rien y
déposer/reprendre, la zone n'est plus qu'un comptoir mur.

> **Ce qu'on mesure** (`rollout`) : le nombre de **pas** (`steps`) jusqu'à ce que **toutes
> les commandes** soient livrées, plus le nombre de dépôts/retraits sur zone (`Ydrop`/`Ypick`).

---

## 2. Comment les agents sont fabriqués et pilotés

### `make_greedy(...)` — un chef prêt à jouer

Chaque chef est un `GreedyAgent` branché sur le `mdp` (les règles) et le `mlam` (le
catalogue d'actions + le planificateur de déplacement). Deux réglages importants :

- **`ai_see_asset`** : l'agent tient-il compte de l'objet que porte son partenaire ? Mis à
  `False` pour le rôle « cuisine » des relais (évite qu'il croie une marmite complète alors
  que le partenaire tient encore l'ingrédient).
- **`auto_unstuck`** : l'agent se dégage-t-il seul s'il reste figé ? `False` dans les modes
  automatiques (la dé-confliction, §7, s'en charge) ; `True` en **jeu manuel** (§8), où il
  n'y a pas de dé-confliction.

### Optimisation de démarrage

Le planificateur *joint* (deux agents à la fois) est en `O(P⁴)` (30–40 min ici) et **inutile**
pour un greedy — qui ne consulte que le planificateur **mono-agent**. Le fichier neutralise
donc son pré-calcul (`JointMotionPlanner._populate_all_plans → {}`) : le `mlam` se construit
instantanément, **comportement inchangé**.

### Le contrat d'une « politique »

Chaque politique expose une méthode `joint(state, t)` qui renvoie **le couple d'actions**
`(action_chef_0, action_chef_1)`. Le `rollout` l'appelle à chaque tick, dé-conflicte le
résultat (§7), puis fait avancer le jeu d'un pas.

---

## 3. Le choix de la politique selon la topologie

`_make_policy` **inspecte la structure du layout** et choisit automatiquement la bonne
stratégie (repli sûr, jamais de plantage) :

```
                Les deux chefs sont-ils dans la MÊME zone praticable ?
                                     │
             NON (2 composantes)     │      OUI (1 composante = layout CONNEXE)
        reliées par des passes 'Y'   │                    │
                     │               │        A-t-il zones 'Y' + planche + assiette + marmite ?
                     ▼               │            │                         │
              ExchangePolicy         │           OUI                       NON
         (rôles par composante)      │            ▼                         ▼
                                     │     CoopExchangePolicy          GreedyPair
                                     │     (rôles + gain ESTIMÉ)    (2 greedy libres)
```

- **`GreedyPair`** — aucune structure à exploiter (layout auto-suffisant) → deux greedy
  libres. C'est aussi la variante **SANS zones** de toute comparaison.
- **`ExchangePolicy`** — deux zones **séparées** reliées uniquement par des `Y` (ex.
  `test_exchange_forced`).
- **`CoopExchangePolicy`** — une seule zone **connexe** mais avec un pipeline de découpe
  relayable (ex. `test_exchange_benefit`, `test_exchange_benefit2`).

> **Point commun aux deux relais.** Un seul chef reste un **vrai `GreedyAgent`**, le **cook**
> (il choisit la recette, remplit la marmite, cuit, dresse, sert). L'autre, le **prep**, est
> un **processeur explicite** codé dans le fichier : il découpe ce qui lui arrive, fournit
> des assiettes, et relaie le reste.

---

## 4. Politique 1 — `GreedyPair`

La **référence**. Deux `GreedyAgent` totalement libres, chacun poursuivant *sa* recette.
Aucune coordination de tâche ; seule la dé-confliction des déplacements (§7) évite qu'ils se
figent mutuellement.

C'est le comportement **historique** du jeu (humain remplacé par un 2ᵉ greedy) et la
baseline « SANS zones ». Sur un layout ouvert, deux greedy libres **partagent naturellement**
toute la charge et parallélisent bien.

---

## 5. Politique 2 — `ExchangePolicy`

Pour les layouts **séparés** : chaque chef est enfermé dans sa zone, les ressources d'une
recette sont réparties de part et d'autre d'un mur de comptoirs `Y`. **Aucun chef ne peut
finir seul** — la passe est obligatoire.

**Rôles émergents** (selon *où* sont les stations) :

- **cook** = le chef dont la composante contient la **marmite** (vrai `GreedyAgent`).
- **prep** = l'autre (processeur explicite).

**Règle de routage — par appartenance à une composante.** Un chef qui tient un objet dont la
station de destination **n'est pas dans sa zone** le **dépose sur la passe la plus proche**
pontant vers la bonne zone ; le partenaire l'y récupère et poursuit :

```
   brut ─▶ planche (prep)          coupé ─▶ marmite (cook)
   assiette ─▶ marmite (cook)      soupe ─▶ service
```

**Anti-churn** : un chef ne **reprend jamais** sur une passe l'objet qu'il vient d'y poster
(sinon il tournerait en rond). Résultat sur `test_exchange_forced` : **7/7 commandes AVEC les
zones, infaisable sans**.

---

## 6. Politique 3 — `CoopExchangePolicy`

C'est le cœur de la contribution récente : faire coopérer deux greedy sur un layout
**connexe** (les deux chefs atteignent *tout*), où les zones ne sont que des **raccourcis**.

> **Pourquoi une politique dédiée ?** Sur un layout connexe, `ExchangePolicy` dégénère (pas de
> composantes séparées → aucune de ses conditions ne se déclenche) et les deux greedy feraient
> le **tour complet** de la boucle à chaque étape. On rétablit un pipeline dont l'usage des
> zones est décidé — comme demandé — par **estimation du gain en pas, l'agent OBSERVANT la
> position de son partenaire**.

### 6.1 Les rôles — statiques entre 2 IA, **dynamiques face à un humain**

Les rôles sont attribués par **proximité** : le **cook** est le chef le plus « cuisine »
(proche du bloc *marmite / service / distributeurs*), le **prep** l'autre (proche *planche /
assiette*). Selon le contexte :

- **Deux IA** (compare / visual) → rôles **quasi-statiques**, mais la bascule cook↔prep est
  **autorisée sous garde de quiescence** (`_maybe_swap_roles`, cf. §6.7). Historiquement on
  l'interdisait totalement : deux greedy symétriques n'ont pas de partenaire à « épouser » et une
  bascule fondée sur l'affinité instantanée ne fait qu'**osciller** (thrashing → la soupe rebondit
  entre les deux sans être servie ; observé sur `test_exchange_benefit3`). La garde de quiescence
  (bascule **uniquement à un point mort** du pipeline) supprime ce risque : les rôles restent de
  fait stables sur les layouts de test, mais peuvent changer si les agents dérivent.
- **Face à un humain** (`solo_action`, mode manuel) → rôles **DYNAMIQUES** : l'IA prend le
  rôle **complémentaire** de l'humain (voir §8), avec **hystérésis** (avantage d'affinité
  minimal + délai minimal entre deux bascules) pour éviter l'oscillation. Un seul « cerveau
  cook » (`GreedyAgent`) existe ; on lui **ré-affecte l'index** du chef qui joue le cook lors
  d'une bascule → la recette reste continue à travers les changements de rôle.

> **Le prep n'entre jamais dans la zone cuisine.** Un coupé / une assiette destinés à la
> marmite (côté cook) sont **toujours relayés** par le prep sur une zone d'échange, jamais
> livrés par lui : sinon il se garerait dans le **cul-de-sac d'accès à la marmite** et y
> coincerait le cook (interblocage vu sur `test_exchange_benefit3`). Un prep oisif ne
> stationne pas non plus sur un cul-de-sac (`_park` : il en sort d'un pas).

### 6.2 Le calcul de gain — `_relay_gain` (le cœur)

Chaque fois qu'un chef `i` tient un objet à destination `D`, il **estime** s'il vaut mieux le
**relayer** (déposer sur une zone `y`, le partenaire `j` termine) ou le **livrer lui-même**,
en **observant la position** de `j` :

```
   not_use = coût pour livrer D moi-même  PUIS revenir à ma station-cœur
   use(y)  = coût pour aller DÉPOSER sur la zone libre y      (je reste local)
   fin(y)  = coût pour que j prenne en y  PUIS livre à D       (position de j OBSERVÉE)

   ── RELAYER via la meilleure zone y  SSI ────────────────────────────────
     (garde-fou CÔTÉ)   D est plus proche de la maison du PARTENAIRE que de la mienne
     (gain réel)        use(y) + marge  <  not_use
     (sans retard)      fin(y)          ≤  not_use
```

Deux **garde-fous** rendent ce critère fiable :

- **Coût ancré (stable).** `not_use` inclut le **retour chez soi** (station-cœur : marmite
  pour le cook, planche pour le prep). Sans ce retour, le coût vers `D` « fond » à mesure
  qu'on s'en approche → l'agent finit par **tout faire lui-même** après avoir déjà traversé
  (critère myope).
- **Garde-fou de côté.** On ne relaie **que** vers une station réellement du côté du
  partenaire. Il empêche deux dérives : relayer un objet dont la destination est de *mon*
  côté (que le partenaire ne prendrait pas → **churn** de dépôts/reprises) ; et « tirer » le
  partenaire hors de sa zone.

> `_relay_gain` renvoie *(zone choisie, gain estimé)* ou *None* (pas de relais profitable →
> je livre moi-même). C'est l'implémentation exacte de la demande : *« observer le partenaire
> et estimer le gain en pas d'utiliser ou non la zone d'échange »*.

### 6.3 Ce qui circule — objets **et plats**

```
   OIGNON / TOMATE brut ───▶ (zone) ───▶  le PREP découpe
   COUPÉ / ASSIETTE     ◀── (zone) ◀───   le PREP relaie        le COOK met en marmite / dresse
   SOUPE (le « plat »)  ───▶ (zone) ───▶  le PREP sert    ◀── seulement si le SERVICE est côté prep
```

Le **plat** (la soupe) est donc lui aussi échangeable : si le service est du côté du prep, le
cook lui **passe le plat** au lieu de traverser toute la carte — le garde-fou de côté garantit
que ça ne se déclenche que là où c'est pertinent.

### 6.4 Deux protections indispensables sur layout connexe

- **Anti-churn (masquage).** Un brut posé sur une zone est du ressort du prep. Le cook le
  **masque** dans sa perception : il ne le « voit » pas comme un objet à reprendre → pas de
  boucle poser/reprendre, et séparation nette des rôles.
- **Anti-surproduction (throttle, PAR TYPE).** Sur un layout connexe, tout est atteignable,
  donc le throttle natif de l'agent est neutralisé : sans borne, le cook injecte **plus**
  d'ingrédients que la marmite n'en accepte → exemplaires **orphelins** qui bloquent le
  pipeline. On borne le nombre d'exemplaires **en transit** au besoin réel de la marmite en
  cours. **Par type** est impératif : un oignon en surplus ne doit pas empêcher d'aller
  chercher une **tomate** manquante (sinon interblocage).

### 6.5 Illustration — l'échange des plats en chiffres

Sur `test_exchange_benefit2`, le service est dans un cul-de-sac du côté prep :

| Mesure | Avant (le cook servait lui-même) | Après (relais du plat) |
|---|---|---|
| Steps (7 commandes) | 759 | **653** |
| Soupes relayées cook→prep | 0 | **7 / 7** |
| Passages du cook dans le cul-de-sac | 21 tics | **1 tic** |

### 6.6 Exploiter la fenêtre de cuisson — pré-sourcing (temps mort → travail utile)

**Le manque à gagner.** Quand tous les ingrédients sont dans la marmite et qu'elle **cuit**
(~26 tics pour `[O,O,O]`), le `GreedyAgent` de base fait aller le cook chercher l'**assiette**
puis **attendre** au bord de la marmite (boucle INTERACT) que la soupe soit prête ; le prep,
n'ayant plus rien à découper, reste **immobile**. Résultat : pendant toute la cuisson **les deux
chefs sont oisifs** et personne ne prépare la commande suivante.

**Le correctif (`cook_action` + `_presource_*`).** Pendant la fenêtre de cuisson, le cook
**PRÉ-SOURCE** les ingrédients de la **prochaine** recette au dispenser et les **relaie au prep
qui les découpe** — de sorte qu'à la fin de la cuisson : soupe dressée immédiatement (l'assiette
est fournie/relayée) **ET** ingrédients suivants déjà coupés, en attente sur une zone → la
marmite se re-remplit **sans temps mort**. C'est une **réaffectation de rôle DANS la fenêtre** :
le cook devient sourceur, le prep fournit l'assiette puis pré-découpe. Mécanique :

- *Quelle recette pré-sourcer ?* On rejoue le greedy du cook sur un état « pré-source » où la
  soupe **en cuisson** ET l'**ordre** qu'elle honore sont retirés (`_presource_state`) : le
  greedy y voit la marmite libre et la commande déjà honorée → il vise la **recette suivante**.
  Retirer l'ordre est indispensable — sinon le cook re-sourcerait la recette en cuisson (absente
  une 2ᵉ fois de la carte de commandes) = **surproduction / orphelins**.
- *Combien ?* Sourcing **dirigé** vers le type le plus **déficitaire** encore requis, borné par
  le throttle **par type** (`_oversupplied`) et par les **zones libres** : le cook enchaîne
  plusieurs ingrédients dans la fenêtre (oignon throttlé → tomate…) sans jamais dépasser le
  besoin réel ni saturer les passes.
- *Repli garanti (jamais de soupe non emportée).* Le cook garde un **budget** : tant qu'il reste
  plus de cuisson que le coût estimé pour aller prendre l'assiette et revenir dresser
  (`_dish_eta` + marge), il pré-source ; en-deçà — ou si aucune assiette n'est sécurisée — il
  part dresser normalement. Un verrou `_serve_committed` évite l'oscillation (l'ETA dépend de la
  position du cook).

**Où c'est actif.** Partout SAUF s'il existe une zone d'échange **« pincée »** — une zone dont
*toutes* les cases d'accès sont des cul-de-sacs (`_zone_pinched`). Une telle zone est un **piège** :
un ingrédient qu'on y relaie n'est repris qu'en **entrant dans un cul-de-sac**, où un partenaire
oisif qui se gare **interbloque** le cook (`coop_deconflict` ne peut dénouer un couloir 1-large ;
deadlock tracé sur `benefit2`, zone (1,4) pincée — 2 zones seulement, la 2ᵉ portant l'assiette).
En l'absence de zone pincée, tout relais atterrit sur une case **ouverte** → pré-sourcing sûr,
**même** en présence d'autres cul-de-sacs (`benefit3` a des cul-de-sacs mais aucun sur une zone).
Quand une zone est pincée, `cook_action` reste **strictement** le comportement d'origine
(**jamais de régression**). Critère **mécaniste**, pas un réglage par layout.

| Layout (7 commandes) | Avant | Après | Fenêtre de cuisson |
|---|---|---|---|
| `test_exchange_benefit` (ouvert) | 619 | **531** (−14 %) | pré-sourcing actif |
| `test_exchange_benefit3` (cul-de-sacs, 0 zone pincée) | 599 | **579** | pré-sourcing actif |
| `test_exchange_benefit2` (zone pincée) | 650 | 650 | désactivé (inchangé) |

> **Note 1.** Sur `benefit`, le relais reste plus lent que deux greedy libres (407) — c'est un
> layout ouvert où spécialiser les rôles déséquilibre la charge (cf. §9.2) ; le pré-sourcing
> **réduit** cet écart sans l'annuler. Le gain est net là où le relais est utilisé.
>
> **Note 2 — `benefit2`, limite fondamentale.** Il n'a que **2 zones**, dont une **pincée** (1,4).
> L'assiette occupe déjà une zone ; tout ingrédient pré-sourcé se relaierait donc **forcément** sur
> la zone pincée → piège. Aucune configuration ne l'évite avec 2 zones : le pré-sourcing y est
> intrinsèquement risqué et reste désactivé (les deux chefs y restent oisifs pendant la cuisson).

### 6.7 Changement de rôle EN COURS DE PARTIE (cook ↔ prep)

Le rôle d'un chef n'est plus figé : il peut **changer pendant la partie**, selon le contexte.

- **Réaffectation *fonctionnelle* dans la fenêtre de cuisson** (§6.6) : sans échanger les
  identités, le cook devient *sourceur* et le prep *fournisseur d'assiette + pré-découpeur* le
  temps de la cuisson, puis chacun reprend son rôle.
- **Face à un HUMAIN** (`solo_action`) : l'IA prend le rôle **complémentaire** de l'humain d'après
  la position de celui-ci, avec **hystérésis** (`ROLE_HYST`/`ROLE_DWELL`) et une garde
  **anti-rebond** (elle ne rebascule que **mains vides**, pour ne pas lâcher/rerouter un objet à
  mi-pipeline). Humain côté planche → IA cook ; humain côté marmite → IA prep.
- **Entre 2 IA** (`joint` → `_maybe_swap_roles`, activé par `dynamic_roles=True`) : la bascule
  cook↔prep est **autorisée mais sous garde de QUIESCENCE** — uniquement à un **point mort** du
  pipeline (`_quiescent` : mains vides des deux, aucune zone occupée, pas de soupe en cuisson) +
  hystérésis. Cette garde supprime le **thrashing** historique (deux greedy symétriques dont
  l'affinité oscille → la soupe rebondit sans être servie → livelock, cf. §6.1). Conséquence : à
  un point mort chacun est déjà près de son bloc, donc **aucune bascule parasite** sur les layouts
  de test (numéros inchangés), mais la **capacité** de rebasculer existe et se déclenche si les
  agents ont **dérivé** au point que le prep serait nettement mieux placé pour tenir la cuisine
  (vérifié : un cook mal placé et un prep près de la marmite → échange des rôles au point mort).

---

## 7. La dé-confliction des déplacements

Deux greedy planifient chacun **seul** : à la moindre collision, le jeu **fige les deux** et
chacun rejoue le même coup → interblocage (invisible en expérience réelle, où le partenaire
est un humain flexible). Le `rollout` insère donc une couche `coop_deconflict` *(définie dans
`simulation.py`, appelée ici)* qui **ne touche pas au choix de tâche** — elle n'arbitre que
les **déplacements** qui entreraient en collision :

1. un chef qui **travaille** (`INTERACT`) n'est jamais dérangé ;
2. un chef qui **attend** (`STAY`) cède le passage ;
3. à défaut, l'index 0 est prioritaire ; le cédant recalcule un chemin qui évite la case du
   prioritaire ;
4. **cul-de-sac** : si le cédant est **piégé** dans un cul-de-sac dont l'unique sortie est la
   case du prioritaire (et que le prioritaire veut justement y entrer — p.ex. une marmite
   dont l'accès est un cul-de-sac), c'est le **prioritaire qui s'écarte** pour laisser sortir
   le piégé (il reviendra au tick suivant). Sans cette règle, les deux se figent pour de bon
   (interblocage de `test_exchange_benefit3`).

> Cette couche fait passer une paire greedy de « ~2/36 layouts complétés » à **36/36** (les
> layouts auto-suffisants restent inchangés — la règle 4 ne s'arme que dans le cas piégé). En
> **jeu manuel** (§8), elle est absente : le partenaire humain gère lui-même les collisions.

---

## 8. La mesure et les trois modes d'exécution

Le `rollout` déroule une partie : à chaque tick il demande `policy.joint(...)`, dé-conflicte
(§7), fait avancer le jeu, et compte pas / dépôts / retraits jusqu'à ce que toutes les
commandes soient livrées (ou l'horizon atteint).

| Mode | Commande | Ce qu'il fait |
|---|---|---|
| **compare** *(défaut)* | `--mode compare` | joue **AVEC** puis **SANS** zones et affiche le verdict chiffré. |
| **visual** | `--mode visual` | fenêtre pygame : regarder les deux IA jouer (`--no-relay` = greedy libre). |
| **manual** | `--mode manual` | **jouer soi-même** un chef ; l'autre est un `GreedyAgent`. |

**Mode manuel** *(désactivé par défaut — s'active avec `--mode manual`)* : le chercheur
contrôle un chef au clavier — **Flèches / ZQSD** = se déplacer ou pivoter, **Espace** (ou E)
= interagir (maintenir pour découper), **Échap** = quitter. `--human-index {0,1}` choisit le
chef contrôlé (défaut 1, comme en prod où l'IA est le chef 0).

Le **partenaire IA** s'adapte à la topologie :

- **Layout connexe** (les deux chefs atteignent tout) → **IA ADAPTATIVE** (`solo_action`) :
  elle **observe ta position** et prend le **rôle complémentaire**, en **changeant de rôle en
  cours de partie**. Si tu occupes le bloc *prep* (planche / assiette), l'IA prend **cook**
  (elle va tenir la marmite, cuire, servir) ; si tu descends à la **marmite**, l'IA repasse
  **prep** (elle découpe, fournit les assiettes, relaie). Même hystérésis qu'en §6.1.
- **Layout séparé** (ou `--no-relay`) → `GreedyAgent` **simple** (déjà adaptatif ; sur un
  layout séparé il relaie via la logique de passe de `agent.py`), créé avec `auto_unstuck=True`
  puisqu'il n'y a pas de dé-confliction.

**Lecture du verdict de `compare` :**

- *les deux variantes finissent* → on affiche l'écart et le **minimum réalisable**. Si AVEC
  est plus lent, le message explique que sur ce layout **ouvert** le greedy libre gagne.
- *seule AVEC finit* → **« ZONES INDISPENSABLES »** (le message distingue « régions
  cloisonnées » d'un cul-de-sac qui interbloque le greedy libre).

---

## 9. Tableaux de synthèse

### 9.1 Quelle politique pour quel layout

| Type de layout | Politique | Cook (greedy) | Prep (processeur) | Zones utilisées ? |
|---|---|---|---|---|
| Auto-suffisant | `GreedyPair` | — *(2 greedy libres)* | — | non |
| Séparé (2 zones) | `ExchangePolicy` | recette + marmite + service | découpe + assiettes + relais | **oui** (obligatoire) |
| Connexe + découpe | `CoopExchangePolicy` | idem, relais si **gain estimé > 0** | découpe + assiettes + **sert les plats** | **si profitable** |

### 9.2 Quand les zones font-elles gagner ? (résultats mesurés, 7 commandes)

| Layout | AVEC zones | SANS zones | Verdict |
|---|---|---|---|
| `test_exchange_forced` (séparé) | **615** ✓ | infaisable | zones **indispensables** |
| `test_exchange_benefit2` (connexe, cul-de-sac) | **653** ✓ | infaisable | zones **indispensables** (débloquent le greedy) |
| `test_exchange_benefit` (connexe, boucle ouverte) | 619 | **407** ✓ | zones **inutiles** ici : deux greedy libres parallélisent mieux |

> **Le message clé.** Les zones d'échange **font gagner (ou rendent réalisable)** un niveau
> **seulement quand la topologie force la coopération** — régions séparées, ou couloir /
> cul-de-sac où deux greedy libres s'interbloquent. Sur une **boucle ouverte**, deux greedy
> partagent déjà toute la charge, et le relais — en spécialisant les rôles — la *déséquilibre*.
> « Steps minimum avec usage **optimal** des zones » = **min(AVEC, SANS)** : le banc d'essai
> joue les deux et rapporte honnêtement le meilleur.

---

*Fichier décrit : `simulation_exchange.py` (`GreedyPair`, `ExchangePolicy`,
`CoopExchangePolicy`, `_make_policy`, `_relay_gain`, `rollout`, `run_compare` / `run_visual`
/ `run_manual`). Dé-confliction : `coop_deconflict` dans `simulation.py`. Logique interne de
l'agent (choix de recette, découpe, attendre-vs-jeter) : `overcooked_ai_py/agents/agent.py`.*
