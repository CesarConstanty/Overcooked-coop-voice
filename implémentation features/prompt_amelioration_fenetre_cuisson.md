# PROMPT — Exploiter la fenêtre de cuisson (relais coopératif, layouts connexes)

> À donner tel quel à un agent de développement. Il est **autonome** : tout le contexte
> nécessaire est ci-dessous. Objectif : améliorer le débit du relais coopératif
> `CoopExchangePolicy` en supprimant le temps mort pendant la cuisson d'une soupe.

---

## 1. CONTEXTE

Jeu type **Overcooked** pour des expériences de sciences cognitives (MDP Python).
`simulation_exchange.py` (à la racine) est un banc d'essai hors-Flask qui fait jouer **deux
`GreedyAgent`** exploitant les **zones d'échange `Y`**, et mesure le **nombre de pas** pour
livrer toutes les commandes (mode `compare` : AVEC zones vs SANS zones).

Sur un layout **connexe** (les deux chefs atteignent tout), le relais est assuré par la
classe **`CoopExchangePolicy`** (dans `simulation_exchange.py`). Rôles **asymétriques** :

- **cook** = un vrai `GreedyAgent` qui PILOTE la recette : source les ingrédients, remplit
  la marmite, lance la cuisson, prend l'assiette, dresse, sert (`cook_action`).
- **prep** = un **processeur passif** qui RÉAGIT seulement (`prep_action`) : il découpe ce
  qui arrive sur sa planche ou relayé sur une zone `Y`, fournit une assiette *si le cook ne
  s'en occupe pas déjà*, relaie les coupés vers la marmite, sert un plat (soupe) relayé.

Un objet dont la station de destination est « du côté du partenaire » est **relayé** via une
zone `Y` (dépôt → l'autre le reprend), décision prise par estimation du gain en pas
(`_relay_gain`, qui OBSERVE la position du partenaire). Détails : voir
`implémentation features/comportement_greedy_agent.md`.

Contrainte matérielle importante des layouts visés : il y a **UNE seule marmite**.

---

## 2. LE PROBLÈME À CORRIGER

Quand tous les ingrédients d'une recette sont dans la marmite et qu'elle **cuit** :

1. le **cook** va chercher l'**assiette**, revient au bord de la marmite et **attend** (il
   répète INTERACT) jusqu'à ce que la soupe soit prête (~27 tics pour `[O,O,O]`) ;
2. le **prep** n'a rien à traiter (planche vide, aucun brut relayé, et l'assiette est déjà
   « en transit » côté cook) → il reste **immobile (`STAY`)**.

→ Pendant toute la fenêtre de cuisson, **les deux chefs sont oisifs** et **personne ne
prépare la recette suivante**. C'est le principal manque à gagner de débit. (Preuve : tracer
`test_exchange_benefit`, t≈104→130 : `COOK … dis … interact` en boucle, `PREP … STAY`.)

Pourquoi actuellement : (a) le prep ne source jamais d'ingrédient de lui-même (rôle passif,
et les distributeurs sont côté cook) ; (b) le cook, dès qu'une soupe cuit, va
*prioritairement* chercher l'assiette (logique du `GreedyAgent` de base) et attend, au lieu
de pré-approvisionner ; (c) marmite unique : la recette suivante ne peut être *assemblée*
qu'une fois la soupe dressée+servie.

---

## 3. OBJECTIF

**Exploiter la fenêtre de cuisson.** Pendant qu'une soupe **cuit** (et n'est pas encore
prête) :

- c'est le **prep** qui va chercher l'**assiette** (son distributeur `D` est de son côté) et
  la **relaie** au cook (dépôt sur une zone `Y`) — le cook la récupère juste à temps pour
  dresser ;
- le **cook**, ainsi libéré, va **pré-sourcer** le(s) ingrédient(s) de la **PROCHAINE**
  recette et les fait **découper** (relais vers le prep) pendant la cuisson, pour qu'ils
  soient **prêts (coupés, en attente sur une zone)** dès que la marmite se libère.

Ainsi, à la fin de la cuisson : soupe dressée immédiatement (assiette déjà là) ET ingrédients
suivants déjà coupés → la marmite se re-remplit sans temps mort.

---

## 4. CONTRAINTES NON NÉGOCIABLES

1. **Ne modifier QUE `simulation_exchange.py`.** Ne pas toucher `overcooked_ai_py/agents/agent.py`,
   ni `simulation.py` (dont `coop_deconflict`), ni les layouts.
2. **Invariant no-op.** Le comportement doit rester **strictement inchangé** sur :
   - les layouts **auto-suffisants** (routés vers `GreedyPair`) ;
   - les layouts **séparés** (routés vers `ExchangePolicy`) — l'amélioration ne concerne QUE
     `CoopExchangePolicy` (connexe).
3. **Zéro régression.** Après modification, `--mode compare` doit toujours livrer 7/7 (ou
   6/6) sur TOUS les layouts ci-dessous, avec un nombre de pas **≤ à l'actuel** (idéalement
   STRICTEMENT inférieur là où une fenêtre de cuisson existe) :

   | layout | attendu AVANT | cible APRÈS |
   |---|---|---|
   | `test_exchange_benefit`  | 7/7 en 619 | 7/7, **< 619** souhaité |
   | `test_exchange_benefit2` | 7/7 en 650 | 7/7, **< 650** souhaité |
   | `test_exchange_benefit3` | 7/7 en 599 | 7/7, **< 599** souhaité |
   | `test_exchange_forced`   | 7/7 en 615 | 7/7 = 615 (inchangé : `ExchangePolicy`) |
   | `test_asym01`            | 6/6 en 532 | 6/6 = 532 (inchangé : `ExchangePolicy`) |
   | `test01`                 | 6/6 en 267 | 6/6 = 267 (inchangé : `GreedyPair`) |

4. **Pas de sur-production / d'orphelins.** Ne pré-sourcer que ce que la PROCHAINE recette
   peut réellement valider. Le throttle par type existe déjà (`_oversupplied` / `_in_flight_of`) :
   s'en servir, ne pas le contourner. Ne jamais laisser un ingrédient coupé sans commande
   valide (interblocage d'orphelins déjà vécu).
5. **Le jeu doit toujours se terminer** (aucun deadlock/livelock ; horizon non atteint).
6. **Préserver les correctifs récents** de `CoopExchangePolicy` :
   - rôles **statiques** entre 2 IA (`joint`), dynamiques uniquement face à un humain (`solo_action`) ;
   - le prep **relaie toujours** vers une station côté cook, il n'y **livre jamais** lui-même
     (sinon il se coince dans le cul-de-sac d'accès à la marmite) ;
   - `_park` (un prep oisif sort d'un cul-de-sac au lieu de `STAY`).

---

## 5. PISTES D'IMPLÉMENTATION (indicatives)

Repères utiles dans `CoopExchangePolicy` : `cook_action`, `prep_action`, `_relay_gain`,
`_oversupplied` / `_in_flight_of`, `_dish_needed`, `_dish_in_transit`, `_fetch_ingredient`,
`_nearest_free_exchange`, `_park`. Le cook expose son intention via
`self.cook.intentions['goal']` (`'D'` = va chercher une assiette, `'O'`/`'T'` = ingrédient,
`'P'` = marmite, `'S'` = service) et l'état recette via `self.cook.next_order_info`. L'état de
la marmite : `mdp.get_pot_states(state)` (`'cooking'`, `'ready'`), et une soupe :
`state.get_object(pot).is_cooking` / `.is_ready` / `.cook_time_remaining` si disponible.

1. **Assiette fournie par le prep en priorité.** Rendre le prep **fournisseur d'assiette
   prioritaire** dès qu'une soupe cuit ET qu'aucune assiette n'est déjà en transit (il fait
   déjà ceci — étape 3 de `prep_action` — mais se désiste via `_dish_in_transit` parce que le
   cook la prend en premier). Il faut donc surtout empêcher le cook de la prendre (point 2).
   Bien relayer l'assiette côté cook (le cook la reprend et dresse). Éviter la **course à
   l'assiette** : un seul fournisseur (ne pas fabriquer deux assiettes).

2. **Détourner le cook de l'assiette pendant la cuisson.** Dans `cook_action`, quand la soupe
   est **en cours de cuisson** (pas encore prête, il reste des tics) ET que le prep peut/va
   fournir l'assiette, **empêcher le cook d'aller la chercher lui-même** (cas
   `self.cook.intentions['goal']=='D'` ciblant le distributeur) et le rediriger vers le
   **sourcing du prochain ingrédient**. Astuce possible : recalculer la décision du cook sur
   un état « masqué » (comme `_mask_raw_on_exchange`) où l'on neutralise le déclencheur
   « aller chercher l'assiette », afin que son propre greedy choisisse spontanément le
   prochain ingrédient. **Repli obligatoire** : si la soupe devient PRÊTE et qu'aucune
   assiette n'arrive, le cook doit pouvoir aller la chercher lui-même (ne jamais rester
   bloqué à attendre une assiette qui ne vient pas).

3. **Vérifier le throttle pendant la cuisson.** Pendant la cuisson, la marmite « la plus
   avancée » vue par le cook est celle qui cuit (filtrée de `hl_info`) → le « besoin » calculé
   correspond déjà à la **prochaine** recette. Vérifier que `_oversupplied` autorise bien de
   pré-sourcer ~une recette d'avance **sans** dépasser le nombre de zones `Y` libres (sinon le
   cook tiendrait un brut sans zone où le déposer → il le découperait lui-même = régression).

4. **Rester simple et réversible.** Idéalement, l'amélioration s'exprime en quelques branches
   ajoutées à `cook_action` / `prep_action`, activées uniquement dans la fenêtre
   « soupe en cuisson, pas prête ». Hors de cette fenêtre, comportement inchangé.

---

## 6. PIÈGES CONNUS (déjà rencontrés — à éviter)

- **Sur-production** : sans borne au besoin réel, le cook empile des ingrédients qu'aucune
  commande valide ne consomme → orphelins bloquants. Se caler sur le besoin par type.
- **Zones saturées** : ne pas pré-sourcer plus d'ingrédients qu'il n'y a de zones `Y` libres.
- **Double assiette** : cook + prep qui vont chacun chercher une assiette → une gaspillée,
  et churn. Un seul fournisseur.
- **Repli assiette** : soupe prête avant l'arrivée de l'assiette → le cook doit pouvoir la
  chercher lui-même, sinon la soupe n'est jamais emportée (interblocage).
- **Rôles / dead-ends** : ne pas réintroduire d'oscillation de rôle (rester statique en 2 IA),
  ni faire entrer le prep dans un cul-de-sac (il relaie, il ne livre pas côté cook).

---

## 7. VÉRIFICATION (obligatoire)

```bash
# 1) Non-régression + gain : tous doivent finir 7/7 (ou 6/6), pas ≤ actuel.
for L in test_exchange_benefit test_exchange_benefit2 test_exchange_benefit3 \
         test_exchange_forced test_asym01 test01; do
  python simulation_exchange.py --mode compare --layout $L | grep "AVEC zones"
done
```

- **Attendu** : forced=615, asym01=532, test01=267 (INCHANGÉS) ; benefit/benefit2/benefit3
  toujours 7/7 avec un nombre de pas **≤** (idéalement **<**) l'actuel (619 / 650 / 599).
- **Preuve du comportement** : tracer une fenêtre de cuisson (ex. `test_exchange_benefit`
  autour de t≈104-130) et vérifier que, pendant que la soupe cuit, **le cook pré-source /
  fait découper le prochain ingrédient** (au lieu de tenir l'assiette et d'attendre) et que
  **le prep fournit et relaie l'assiette**.
- **Robustesse** : aucun layout n'atteint l'horizon (pas de nouveau deadlock/livelock).

Documenter le changement (docstring de la classe + `comportement_greedy_agent.md`) et, si un
comportement non évident est découvert, l'y consigner.
