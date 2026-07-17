# Comportement expérimental du `GreedyCoopAgent` — critères de décision et immobilité

> Analyse des deux parties enregistrées dans
> [`trajectories/config_test_visual/3/3_0_0.json`](../trajectories/config_test_visual/3/3_0_0.json)
> et [`3_0_1.json`](../trajectories/config_test_visual/3/3_0_1.json).
> Objectif : documenter **les critères que l'IA utilise pour décider**, et **expliquer pourquoi
> elle reste parfois immobile sans raison apparente**.
>
> Méthode : chaque état enregistré a été **rejoué à travers la vraie politique**
> (`CoopExchangePolicy` de [`simulation_exchange.py`](../simulation_exchange.py), pilotée par
> [`agent_coop.py`](../agent_coop.py)). Aux points de décision, l'action **rejouée = action
> enregistrée** (ex. g481 `INT`/`INT`, g509 `E`/`E`, g517 `S`/`S`) : la trace provient bien du
> code actuel, et l'introspection interne (rôle, but, drapeaux) est donc fiable.

---

## 1. Contexte des deux parties

| | Partie 0 (`3_0_0`) | Partie 1 (`3_0_1`) |
|---|---|---|
| Layout | `test_exchange_benefit2` | `test_exchange_benefit` |
| Durée | 3345 gameloops | 2021 gameloops |
| Score | 36 (7 commandes livrées) | 36 |
| IA | **player 0** (`GreedyCoopAgent_0`) | player 0 |
| Humain | player 1 (`uid=3`) | player 1 |
| Actions IA (hors STAY) | `INT`149 `W`101 `E`90 `S`86 `N`83 | `INT`92 `E`42 `S`41 `W`36 `N`34 |
| **STAY** | **2836 / 3345 = 84,8 %** | **1776 / 2021 = 87,9 %** |

Les deux parties sont **réussies** (7 commandes chacune) : l'IA change bien de rôle et coopère
(elle opère des deux côtés de la carte). L'immobilité observée n'est donc **pas** un blocage du
pipeline — c'est un ensemble de comportements d'attente, la plupart **volontaires**.

Layout `test_exchange_benefit2` (partie 0), repères utilisés ci-dessous :

```
      x=0  1  2  3  4  5  6
 y=0   X  S  X  X  X  X  X      S = service (1,0)
 y=1   D  .  .  .  .  .  X      D = distributeur assiettes (0,1)
 y=2   X  .  .  X  X  .  X      C = planche à découper (0,3)
 y=3   C  .  X  .  .  .  X      P = marmite (4,6)
 y=4   X  X  X  .  X  X  X      O = distributeur oignons (6,5)
 y=5   X  .  .  .  .  .  O      T = distributeur tomates (5,6)
 y=6   X  X  X  X  P  T  X      zones d'échange : (2,3) et (1,4)
```

*Côté PREP* (gauche) : planche `C` + assiette `D`. *Côté COOK* (bas-droite) : marmite `P` +
distributeurs `O`/`T` + service `S`. Les deux **zones d'échange** (2,3)/(1,4) relient les deux
côtés (dépôt/retrait d'objets).

---

## 2. Les critères de décision de l'IA

L'IA est un **greedy coopératif adaptatif**. À chaque décision, la chaîne est :

```
solo_action()  →  1. choisir le RÔLE (complémentaire au joueur)
               →  2a. si COOK : cook_action()
               →  2b. si PREP : prep_action()
```

le tout **cadencé** par le moteur de jeu (`ticks_per_ai_action`, §2.4).

### 2.1 Choix du rôle — complémentaire à ce que fait le joueur

`solo_action` (simulation_exchange.py) observe **le partenaire humain** et prend le rôle
**opposé**, via un score signé `_human_prep_score` :

| Signal observé sur le joueur | Score | Rôle pris par l'IA |
|---|---|---|
| tient un ingrédient **brut** (oignon/tomate non coupé) | `+99` | **COOK** (le joueur va découper) |
| tient une **assiette** ou une **soupe** | `−99` | **PREP** (le joueur dresse/sert) |
| tient un coupé / mains vides | position | selon la proximité des **cœurs** de station |
| plus proche de la planche que de la marmite | `> 0` | **COOK** |
| plus proche de la marmite que de la planche | `< 0` | **PREP** |

Garde-fous anti-oscillation :
- **`ROLE_HYST_SOLO = 1`** : il faut un écart net (≥ 1) pour basculer.
- **`ROLE_DWELL = 15`** décisions minimum entre deux bascules.
- **bascule uniquement mains vides** (`can_switch`) : on ne change jamais de rôle en plein
  portage (anti-rebond d'un objet à mi-relais).

> Exemple (partie 0, fin de l'épisode oversupply) : le joueur porte un oignon coupé du côté
> prep (1,3) vers le côté cook (5,1) ; à mesure qu'il traverse, le score passe de `+99` à `−…`
> et l'IA repasse **COOK → PREP** (g≈957) — elle épouse le déplacement du joueur.

### 2.2 Comportement COOK — `cook_action`

Priorités (dans l'ordre du code) :

1. **Fenêtre de cuisson / pré-sourcing** : pendant qu'une soupe cuit, si une assiette est
   *sécurisée* et qu'il reste assez de temps (`rem > ETA + COOK_DISH_MARGIN`), le cook va
   **pré-sourcer l'ingrédient de la recette suivante** au lieu d'attendre au bord de la marmite.
   Sinon il **s'engage à dresser** (`_serve_committed`).
2. **Relais** d'un objet tenu **si sa destination est côté prep** (garde-fou de côté +
   gain estimé `_relay_gain`) ; sinon il livre lui-même (pot / service / dressage).
3. **Throttle anti-surproduction** (`_oversupplied`) : mains vides, si le but greedy est
   d'aller **puiser** un ingrédient au distributeur mais qu'il en **circule déjà assez**
   (`_in_flight_of ≥ min(besoin, DEPTH)`), il **STAY** (voir §3, cause 3).
4. **Masquage des bruts sur zone** (`_mask_raw_on_exchange`) : le cook **ignore** les
   ingrédients bruts déposés sur les zones (c'est au prep de les découper) ; il ne « voit »
   que les **coupés** et **assiettes**.
5. Sinon : **action greedy native** (aller au distributeur / à la marmite / au service).

### 2.3 Comportement PREP — `prep_action`

**Tenant un objet :**
- **brut** → planche pour le découper ;
- **plat (soupe)** → **servir soi-même** (un plat n'est *jamais* relayé — anti-livelock) ;
- objet dont la station suivante est **côté cook** → **relayer** via une zone (il n'entre
  jamais dans la cuisine) ;
- sinon → livrer à la station prep.

**Mains vides**, par ordre de priorité :
1. **servir une soupe** relayée sur une zone (fin de pipeline = priorité) ;
2. **travailler une planche** occupée (découper / récupérer le coupé) ;
3. **prendre un brut** relayé sur une zone (pour le découper) ;
4. **fournir une assiette** au cook (si une soupe cuit et qu'aucune assiette n'est déjà en transit) ;
5. **rien à faire → `_park`** : STAY sur place (ou un pas hors d'un cul-de-sac).

### 2.4 Cadence de décision et ralentissements (moteur, `game.py`)

L'IA ne décide **pas** à chaque tick : elle agit quand `curr_tick % ticks_per_ai_action == 0`.
Entre deux décisions, l'action par défaut est **STAY**. `ticks_per_ai_action` varie selon un
système de ralentissement **délibéré** (`_update_ai_speed`, priorité décroissante) :

| État | Vitesse (ticks/décision) | Durée | Déclencheur |
|---|---|---|---|
| Début d'essai | **100** | 30 ticks | premières secondes de l'essai |
| Changement d'**asset** | **20** | 10 ticks | l'intention `goal` passe à `O/T/D/S/C` |
| Changement de **recette** | **16** | 20 ticks | l'intention `recipe` change |
| Normal | **4** | — | par défaut |

Ce ralentissement est une **fonctionnalité expérimentale** : laisser à l'humain le temps de lire
les **bulles d'intention visuelles** (`visual_bubbles`, recette affichée 2 s) avant que l'IA
n'agisse. **C'est la première cause de l'immobilité perçue** (voir §3, cause 1).

---

## 3. Pourquoi l'IA reste immobile — 6 causes, avec exemples

> Sur les épisodes d'immobilité prolongée (position figée ≥ 25 gameloops) : **23 épisodes,
> 1717/3345 gameloops (51 %)** en partie 0 ; **21 épisodes, 1244/2021 (62 %)** en partie 1.
> `agent_stuck_loop = 0` dans les deux cas : le détecteur natif de blocage ne s'est **jamais**
> déclenché — l'immobilité est faite de STAY **décidés**, pas d'un greedy coincé en boucle.

### Cause 1 — Ralentissement délibéré *(dominante, ~½ des gameloops)*

Même en pleine action, l'IA ne bouge qu'**1 tick sur 4** (cadence de base) ; jusqu'à **1 tick sur
20 ou 100** pendant les ralentissements. Vu par le joueur : l'IA « avance par à-coups » puis se
fige.

> **Exemple — début d'essai** (partie 0, g[1..37]) : l'IA fait 3 pas `E` puis reste immobile
> ~34 gameloops. C'est le ralentissement *début d'essai* (100 ticks/décision, ~3 s) — voulu.

Ce n'est **pas** un dysfonctionnement : c'est le mécanisme de communication d'intention.

### Cause 2 — Découpe sur place *(immobile mais productif)*

Pour découper, l'IA (prep) reste **plantée face à la planche** et **interagit en boucle**. La
position ne change pas, mais elle travaille.

> **Exemple** (partie 0, g[474..521], IA = PREP à (1,3)) :
> - g477 `W` : elle se tourne vers la planche `C` (0,3) ;
> - g481 `INT` : elle **pose l'oignon brut** sur la planche (mains vides à g482) ;
> - g485→g505 `INT`×… : elle **hache** l'oignon (interactions répétées) ;
> - g506 : elle **reprend l'oignon coupé** (`oni*`) ;
> - g509 `E` puis g513 `INT` : elle le **relaie** sur la zone (2,3).
>
> Détecté comme « immobile 100 gameloops » alors que c'est un cycle **découpe + relais** complet.

### Cause 3 — Throttle anti-surproduction : le cook **attend** l'ingrédient déjà en transit

Le cas d'immobilité **le plus long et le plus déroutant**. Le cook, mains vides, **veut** aller
chercher un ingrédient, mais s'**abstient** parce qu'un exemplaire **circule déjà** (tenu par le
joueur, ou posé sur une zone) : `_oversupplied` renvoie STAY.

> **Exemple clé** (partie 0, g[814..969], **156 gameloops figés**) :
> - IA = **COOK** à (5,3), mains vides, **but = distributeur d'oignons** (5,5)→(6,5) ;
> - `miss = ['onion','tomato']` : la marmite attend un oignon et une tomate ;
> - mais un **oignon coupé est dans la main du joueur** (à (1,3)) et une tomate/oignon sont déjà
>   sur les zones/planche → `_in_flight_of(onion) ≥ 1` → **oversupplied → STAY** ;
> - de plus, les **bruts sur zone sont masqués** au cook (`_mask_raw_on_exchange`) : il ne peut
>   pas non plus « se dépanner » avec eux.
>
> → Le cook **attend rationnellement** que le pipeline (joueur-prep : découper → relayer) lui
> livre un ingrédient **coupé** sur une zone. Il repart **dès que** le joueur amène enfin
> l'oignon (g≈957, l'IA se remet en mouvement).

**Nuance importante (friction réelle)** : le throttle renvoie `STAY` au lieu de **rediriger vers
l'autre ingrédient manquant**. Ici la tomate est aussi attendue ; si elle n'était pas en transit,
le cook pourrait aller la puiser — mais tant que son *but greedy courant* pointe vers l'oignon
saturé, il attend. **C'est la cause la plus proche d'un « immobile sans raison apparente »** du
point de vue du joueur : l'IA a une raison (ne pas surproduire), mais elle est invisible et longue
si le joueur tarde à relayer ce qu'il tient.

### Cause 4 — Prep oisif (`_park`) : plus rien à préparer

Quand le prep a tout découpé/relayé et qu'une assiette est déjà en transit, **il n'a plus de
tâche** : `prep_action` tombe sur `_park` → STAY (attente non bloquante).

> **Exemple** (partie 0, g[1151..1240], IA = PREP à (2,2)) : à g1151 l'IA vient de **relayer une
> assiette** sur la zone (2,3) ; ensuite, aucune planche à travailler, aucun brut sur zone,
> assiette déjà en transit → elle **se gare et attend** ~90 gameloops que du brut réapparaisse
> (le joueur est parti chercher une tomate côté cuisine).

### Cause 5 — Bloquée par le joueur *(couloir 1-large)*

Face à un humain il n'y a pas de `coop_deconflict` : si l'unique chemin est **occupé par le
joueur**, l'IA retente la même direction et **piétine** jusqu'à ce qu'il dégage (l'`auto_unstuck`,
activé côté humain, finit par la libérer).

> **Exemple** (partie 0, g[203..227], IA = PREP à (3,5)) : elle veut monter au **Nord** vers
> (3,4), mais **le joueur campe en (3,4)** → elle décide `N` en boucle sans avancer, ~24 gameloops,
> jusqu'à ce que le joueur bouge.

### Cause 6 — Attente autour de la marmite (fenêtre de cuisson)

Quand une soupe cuit et qu'il n'y a **pas** de fenêtre à exploiter (pas d'ingrédient à
pré-sourcer, ou `_serve_committed` engagé), le cook **attend** près de la marmite le moment de
dresser/servir — position figée le temps de la cuisson.

> Observable en partie 0 autour du dépôt de soupe en (4,6) : l'IA stationne côté cuisine en
> attendant l'assiette / la fin de cuisson.

---

## 4. Synthèse : « feature » vs friction réelle

| Cause | Nature | Vu par le joueur | Voulu ? |
|---|---|---|---|
| 1. Ralentissement (cadence + slowdowns) | mécanisme d'intention | avance par à-coups, se fige | ✅ oui (expérimental) |
| 2. Découpe sur place | tâche productive | immobile mais « travaille » | ✅ oui |
| 3. Throttle anti-surproduction | attente rationnelle | **fige longtemps, raison invisible** | ⚠️ oui, mais friction si le joueur retient l'objet |
| 4. Prep oisif (`_park`) | pas de tâche disponible | attend, inactif | ✅ oui (non bloquant) |
| 5. Bloquée par le joueur | conflit de couloir | piétine sur place | ❌ non désiré (atténué par `auto_unstuck`) |
| 6. Attente de cuisson | temps mort inévitable | stationne près du pot | ✅ oui |

**L'essentiel de l'immobilité est voulu** : la cadence/ralentissement (cause 1) domine, et les
attentes 2/3/4/6 traduisent une coordination correcte avec l'humain. Les deux frictions réelles :

- **Cause 3** — l'attente peut être **très longue** si le joueur garde en main un ingrédient déjà
  en circulation ; l'IA ne se rabat pas sur l'autre ingrédient manquant. *Piste* : dans
  `_oversupplied`, au lieu de `STAY`, tenter de **réorienter le but vers un type manquant NON
  saturé** avant d'attendre.
- **Cause 5** — piétinement quand le joueur bloque l'unique passage ; déjà atténué par
  l'`auto_unstuck` du cerveau cook côté humain, mais un `coop_deconflict` léger vis-à-vis du
  joueur réduirait encore les à-coups.

---

## 5. Repères pour re-vérifier

- Détection des épisodes : position IA figée ≥ 25 gameloops.
- Rejeu introspectif : reconstruire chaque état (`OvercookedState.from_dict`) puis
  `GreedyCoopAgent.action(state)` en lisant `cook_i` (rôle), `cook.chosen_goal` (but),
  `next_order_info['missing_ingredients_in_MA_pot']` (manquants), `_human_prep_score` (signal de
  rôle) et `_oversupplied` (throttle).
- Points de contrôle validés : g481 `INT`/`INT`, g509 `E`/`E`, g517 `S`/`S` (rejeu = enregistré).

*Voir aussi [`comportement_greedy_agent.md`](comportement_greedy_agent.md) pour le greedy de base
et [`simulation_exchange.py`](../simulation_exchange.py) (`CoopExchangePolicy`) pour le code de la
couche coopérative.*
