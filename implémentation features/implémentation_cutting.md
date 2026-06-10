# CONTEXTE
Tu travailles sur un jeu type Overcooked utilisé pour des expériences en sciences
cognitives (Python pour la logique MDP + Phaser/JS pour le rendu + Flask pour le serveur).
Je veux ajouter une étape de DÉCOUPE des ingrédients sur un nouvel élément interactif
(une planche à découper). Certaines recettes exigeront que leurs ingrédients soient
coupés AVANT d'être mis dans la marmite, sinon la soupe ne compte pas.

# CONTRAINTES NON NÉGOCIABLES
1. Toute la fonctionnalité doit être paramétrable et désactivable via config.json.
   Quand le toggle est OFF, le comportement actuel du jeu doit être STRICTEMENT
   inchangé (aucune régression).
2. Ne casse aucune fonctionnalité existante. Prends comme modèle d'intégration la
   feature déjà présente "ASYMMETRIC DISPENSERS" (tuiles 'A'/'B') : cherche les
   commentaires [ASYMMETRIC DISPENSERS] dans le code et calque-toi sur ce pattern.
3. L'agent IA "greedy" (GreedyHumanModel) doit intégrer l'étape de découpe dans sa
   logique de décision.
4. L'enregistrement des résultats (trajectoires JSON) doit tracer les événements de
   découpe.

# DÉCISION DE CONCEPTION (déjà arrêtée, à respecter)
- Ne PAS modifier l'identité de la classe Recipe (basée sur les ingrédients triés +
  cache ALL_RECIPES_CACHE). À la place :
  - Ajouter un attribut booléen `chopped` (défaut False) sur ObjectState, propagé
    jusque dans SoupState.
  - Ajouter dans config.json un ensemble de recettes nécessitant la découpe.
  - La validation à la cuisson/livraison vérifie que tous les ingrédients étaient
    `chopped` si la recette l'exige ; sinon valeur 0 / non comptée.
- Nouvelle tuile de terrain 'C' = planche à découper.

# ASSETS DÉJÀ CRÉÉS (dans static/assets/)
- terrain_cut.png + terrain_cut.json : tuile planche à découper.
- objects_cut.png + objects_cut.json : ingrédients coupés (onion/tomato coupés).
- soups_cut.png + soups_cut.json : soupes réalisées avec ingrédients coupés.
Charge-les comme atlas Phaser dans graphics.js preload() exactement comme les atlas
existants (clés suggérées : "terrain_cut", "objects_cut", "soups_cut"). Ouvre les
fichiers .json pour récupérer les noms de frames EXACTS avant de coder le rendu.

# AVANT DE CODER
1. Explore le repo et confirme l'emplacement et le rôle de :
   - overcooked_ai_py/mdp/overcooked_mdp.py (Recipe, ObjectState, SoupState,
     _assert_valid_grid, resolve_interacts, get_state_transition,
     step_environment_effects, EVENT_TYPES, log_object_pickup/drop/potting,
     get_*_dispenser_locations, soup_to_be_cooked_at_location, deliver_soup,
     get_recipe_value)
   - overcooked_ai_py/planning/planners.py (MediumLevelActionManager :
     get_medium_level_actions, put_onion_in_pot_actions, pickup_onion_actions,
     start_cooking_actions)
   - overcooked_ai_py/agents/agent.py et agent_tomato.py (GreedyHumanModel.ml_action,
     gestion des intentions/goal, RationalAgent.hl_info cost_to_complete)
   - game.py (mapping asset_names, ai_asset_slowdown, intentions)
   - static/js/graphics.js (preload, terrain_to_img, _drawState,
     _ingredientsToSpriteFrame, asymmetric_dispenser_tiles)
   - app.py (passage des params aux templates, trial_save_routine / event_infos)
   - config.json, trials.json, overcooked_ai_py/data/layouts/*.layout
2. Lis les .json des nouveaux atlas pour connaître les frames disponibles.
3. Présente-moi un PLAN d'implémentation court par fichier, puis attends ma
   validation avant de modifier le code.

# IMPLÉMENTATION ATTENDUE (après validation du plan)
config.json
- Dans layout_globals ET dans les blocs de config : cutting_enabled (bool),
  chop_time (int), recipes_requiring_chopping (liste de recettes),
  cutting_board_symbol (défaut "C"). Ajouter "C" à ai_asset_slowdown_intentions
  si pertinent.

overcooked_ai_py/mdp/overcooked_mdp.py
- ObjectState : attribut `chopped` propagé dans __init__, deepcopy, __eq__, __hash__,
  to_dict, from_dict.
- _assert_valid_grid (toutes les occurrences) : 'C' ajouté aux caractères valides et
  à is_not_free.
- get_cutting_board_locations() (calqué sur get_onion_dispenser_locations()).
- resolve_interacts : branche `elif terrain_type == 'C'` (déposer ingrédient brut,
  couper via interaction(s) répétée(s) ou progression de chop_time, récupérer
  l'ingrédient coupé). Toute la branche conditionnée par cutting_enabled.
- Pot/livraison : si la recette exige la découpe, n'accorder valeur/validation que si
  tous les ingrédients de la soupe sont chopped.
- step_environment_effects : faire progresser la découpe si elle est temporisée.
- EVENT_TYPES + helper log_object_chop (sur le modèle de log_object_potting).

overcooked_ai_py/planning/planners.py
- Nouveaux générateurs de motion goals : put_ingredient_on_board_actions,
  chop_actions, pickup_chopped_actions.
- get_medium_level_actions : insérer ces actions ; vérifier que les positions 'C'
  sont des features atteignables par le MotionPlanner.

overcooked_ai_py/agents/agent.py + agent_tomato.py
- GreedyHumanModel.ml_action : insérer l'étape découpe AVANT "mettre dans le pot"
  quand la recette ciblée l'exige et que l'ingrédient n'est pas coupé. Conditionné
  par cutting_enabled.
- Ajouter un code d'intention "couper" (ex. 'C') pour l'affichage des intentions et
  le ralentissement IA.
- RationalAgent : intégrer le coût de découpe dans cost_to_complete.

game.py
- asset_names : ajouter 'C': 'Chop'. Vérifier la prise en compte de 'C' dans
  ai_asset_slowdown.

static/js/graphics.js
- preload : charger terrain_cut / objects_cut / soups_cut (avec garde
  textures.exists, comme les autres).
- terrain_to_img (les DEUX branches) : 'C' -> frame de la planche.
- _drawState : rendu des ingrédients coupés (atlas objects_cut), soupes coupées
  (atlas soups_cut), et indicateur de progression de découpe (sur le modèle du
  timesprite de cuisson).
- _ingredientsToSpriteFrame : gérer la variante "coupée" si nécessaire.

app.py
- Passer cutting_enabled/chop_time aux templates d'instructions.
- Vérifier que les nouveaux EVENT_TYPES remontent dans data["event_infos"] jusqu'au
  JSON de trajectoire (trial_save_routine). Ajouter les params de découpe à
  trial_config_data pour l'analyse.

static/templates/instructions_recipe*.html
- Section "Découpe" conditionnée par {% if cutting_enabled %}.

layouts + trials.json
- Placer des tuiles 'C' dans les layouts visés (grille valide + accessibles aux deux
  joueurs). Marquer les recettes nécessitant la découpe.

# POINTS DE VIGILANCE
- L'attribut chopped doit faire l'aller-retour serveur<->client (sérialisation), sinon
  désync d'état et rendu incohérent.
- Cohérence des DEUX copies de validation de grille et des DEUX branches de
  terrain_to_img.
- Invalidation éventuelle du cache MotionPlanner après ajout de la feature 'C'.

# FIN
Après implémentation : liste les fichiers modifiés, explique comment activer/désactiver
la feature via config.json, et indique comment tester rapidement (config OFF = jeu
identique à l'actuel ; config ON = recette à découper jouable de bout en bout).
Ne lance aucune commande destructive ; propose les commandes de test avant de les
exécuter.
