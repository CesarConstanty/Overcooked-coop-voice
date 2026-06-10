durée max de la partie = 
"gameTime" : 60,
durée max questionnaire hoffman = 
"hoffman_length": 300,
durée max questionnaire AATL =
"qpb_length" : 300,
durée max questionnaire agency =
"qpt_length" : 120,
durée max questionnaire QVG =
"qvg_length" : 300,
durée max questionnaire hoffman =
"ptta_length" : 300,
durée max questionnaire préférence = 
"preference_length" : 300,
durée max tutoriel général (premier tuto) = 
"explications_generales_max": 600,
durée min tutoriel général (premier tuto) = 
"explications_generales_min": 5,
durée max tutoriel de condition = 
"explications_block_max": 300,
durée min tutoriel de condition = 
"explications_block_min": 5,
durée max tutoriel de jeu = 
"timer_tuto_max": 600,
"playerZero" : "Planning",
"agent" : "Greedy",
conditions des blocs, voir app.py pour le détail = 
"conditions" : {"0":"E", "1":"E", "2":"E"},
durée affichage intention visuelle recette = 
"visual_intention_recipe_duration": 2000,
durée affichage intention visuelle asset = 
"visual_intention_asset_duration": 1500,
durée affichage intention visuelle une recette va être annoncée, non utilisé = "visual_intention_next_duration": 1000,
affichage infobulle intention recette = 
"visual_intention_show_recipe": true,
affichage infobulle intention asset = 
"visual_intention_show_asset": true,
tutoriels de blocs affichés = 
"condition_tutorials" : {"E": "tutorial_EA.html","EA": "tutorial_EA.html", "U": "tutorial_U.html", "EV": "tutorial_EV.html", "EVH": "tutorial_EVH.html"},
selections de maps en fonction des numéros de bloc =
"blocs" : {
    "0": ["test01"],
    "1": ["test01"],
    "2": ["test01"]
},
ordre aléatoire des maps dans un bloc = 
"shuffle_trials" : true,
ordre aléatoire des blocs pour un participant =
"shuffle_blocs" : true,
bornes question responsabilité dans un ordre aléatoire =
"randomize_accountability_labels" : true,
questionnaire agency à la fin de chaque essai =
"questionnaire_post_trial" : "agency_en.html",
questionnaire AATL à la fin de chaque bloc =
"questionnaire_post_bloc":"AAT_L_en.json",
questionnaire human robot fluency à la fin de chaque bloc =
"questionnaire_hoffman":"hoffman fluency_en.json",
points rapportés par une tomate =
"tomato_value" : 2,
points rapportés par un oignon =
"onion_value" : 3,
durée de cuisson d'un oignon en nombre de tick =
"onion_time" : 9,
durée de cuisson d'une tomate en nombre de tick =
"tomato_time" : 6,
inutilisé = 
"order_bonus" : 2,
nombre maximum d'ingrédient que peut contenir la marmitte =
"max_num_ingredients" : 3,
active/désactive le remplissage en continu de la liste all order pour toujours avoir 6 recettes disponibles =
"infinite_all_order" : false,
présente d'une limite de temps pour un essai =
"Game_Trial_Timer" : true,
affichage d'un trio de recette au lieu du all order de 6, si une recette est complétée le trio change =
"triplet" : false,
régle de durée du trio de recette (durée aléatoire et bornée) =
"triplet_display_min" : 10,
"triplet_display_max" : 30,
ralentissement des actions de l'AA lorsqu'il communique ses intentions =
"ai_slowdown_enabled": true,
permet à l'IA de voir l'objet tenu dans les mains du participant =
"AI_see_asset" : true,
gére la vitesse de base de l'AA =
"ai_base_speed": 4,
ralentissement de l'IA lors de la communication des intentions de recette =
"ai_slow_speed": 16,
"ai_slow_duration": 20,
ralentissement de l'IA lors du début de l'essai =
"ai_trial_start_slowdown": true,
"ai_trial_start_duration": 30,
"ai_trial_start_speed": 100,
ralentissement de l'IA uniquement pour le premier essai d'un bloc et non au début de chaque essai =
"ai_trial_start_first_only": false,
ralentissment de l'IA lors de la communication des intentions des objets =
"ai_asset_slowdown_enabled": true,
"ai_asset_slow_speed": 20,
"ai_asset_slow_duration": 10,
Définition des objets/actions qui déclenchent un ralentissement des objets de l'IA =
"ai_asset_slowdown_intentions": ["O", "T", "D", "S", "C"],
Permet d'utiliser et force la nécessité de découper les ingrédients pour des soupes valides =
"cutting_enabled" : true,
Définit le nombre d'intéraction avec la table à découper nécessaires à la découpe des ingrédients =
"chop_time" : {"onion" : 3, "tomato" : 2},
"recipes_requiring_chopping" : [["onion"], ["onion", "onion", "onion"]],
"cutting_board_symbol" : "C",
Force la condition l'ingrédient est coupé pour être placé dans la marmitte =
"Human_forced_cutting" : true