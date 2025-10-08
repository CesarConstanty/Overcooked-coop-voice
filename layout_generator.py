import numpy as np
import os
import sys
import argparse
import random, copy
import json

# Ajouter le répertoire parent au path pour permettre les imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from overcooked_ai_py.utils import rnd_int_uniform, rnd_uniform
from overcooked_ai_py.mdp.actions import Action, Direction
from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld, Recipe

EMPTY = ' '
COUNTER = 'X'
ONION_DISPENSER = 'O'
TOMATO_DISPENSER = 'T'
POT = 'P'
DISH_DISPENSER = 'D'
SERVING_LOC = 'S'
COUNTER_GOALS = 'Y'

CODE_TO_TYPE = {0: EMPTY, 1: COUNTER, 2: ONION_DISPENSER, 3: TOMATO_DISPENSER, 4: POT, 5: DISH_DISPENSER,
                6: SERVING_LOC}
CODE_TO_TYPE = {0: EMPTY, 1: COUNTER, 2: ONION_DISPENSER, 3: TOMATO_DISPENSER, 4: POT, 5: DISH_DISPENSER,
                6: SERVING_LOC}
TYPE_TO_CODE = {v: k for k, v in CODE_TO_TYPE.items()}

# Instance globale du gestionnaire de recettes pour maintenir l'état entre les générations
_global_recipe_manager = None

def get_recipe_manager(recipe_file_path="ensemble_recettes.json"):
    """
    Obtient l'instance globale du gestionnaire de recettes
    
    Args:
        recipe_file_path (str): Chemin vers le fichier de recettes
        
    Returns:
        RecipeManager: Instance du gestionnaire de recettes
    """
    global _global_recipe_manager
    
    if _global_recipe_manager is None or _global_recipe_manager.recipe_file_path != recipe_file_path:
        _global_recipe_manager = RecipeManager(recipe_file_path)
    
    return _global_recipe_manager


class RecipeManager:
    """
    Gestionnaire des recettes pour l'intégration avec ensemble_recettes.json
    """
    
    def __init__(self, recipe_file_path="ensemble_recettes.json"):
        """
        Initialise le gestionnaire de recettes
        
        Args:
            recipe_file_path (str): Chemin vers le fichier ensemble_recettes.json
        """
        self.recipe_file_path = recipe_file_path
        self.recipe_data = None
        self.available_recipes = []
        self.used_combinations = []
        self.config = None
        self.load_recipes()
    
    def load_recipes(self):
        """Charge les recettes depuis le fichier JSON"""
        try:
            with open(self.recipe_file_path, 'r', encoding='utf-8') as f:
                self.recipe_data = json.load(f)
            
            # Extraire la configuration
            self.config = self.recipe_data.get('configuration', {})
            
            # Extraire les combinaisons de recettes
            combinations = self.recipe_data.get('layout_integration_format', {}).get('combination_indices', [])
            recipe_list = self.recipe_data.get('layout_integration_format', {}).get('recipe_list', [])
            
            # Convertir les indices en recettes réelles
            self.available_recipes = []
            for combination_indices in combinations:
                combination = [recipe_list[i] for i in combination_indices]
                self.available_recipes.append(combination)
            
            print(f"RecipeManager: Chargé {len(self.available_recipes)} combinaisons de recettes depuis {self.recipe_file_path}")
            
        except FileNotFoundError:
            print(f"Attention: Fichier {self.recipe_file_path} non trouvé. Utilisation des recettes par défaut.")
            self.recipe_data = None
            self.available_recipes = []
            self.config = {}
        except Exception as e:
            print(f"Erreur lors du chargement des recettes: {e}")
            self.recipe_data = None
            self.available_recipes = []
            self.config = {}
    
    def get_random_recipe_combination(self, with_replacement=False):
        """
        Sélectionne aléatoirement une combinaison de recettes
        
        Args:
            with_replacement (bool): Si False, tire sans remise (par défaut)
            
        Returns:
            list: Liste de recettes sous forme de dictionnaires {"ingredients": [...]}
        """
        if not self.available_recipes:
            # Retourne une recette par défaut si aucune n'est disponible
            return [{"ingredients": ["onion", "onion", "onion"]}]
        
        if with_replacement or not self.used_combinations:
            # Tirage avec remise ou premier tirage
            available_indices = list(range(len(self.available_recipes)))
        else:
            # Tirage sans remise
            available_indices = [i for i in range(len(self.available_recipes)) 
                               if i not in self.used_combinations]
            
            # Si toutes les combinaisons ont été utilisées, recommencer
            if not available_indices:
                print("RecipeManager: Toutes les combinaisons ont été utilisées, redémarrage du tirage")
                self.used_combinations = []
                available_indices = list(range(len(self.available_recipes)))
        
        # Sélection aléatoire
        selected_index = random.choice(available_indices)
        
        if not with_replacement:
            self.used_combinations.append(selected_index)
        
        # Convertir en format attendu par OvercookedGridworld
        selected_combination = self.available_recipes[selected_index]
        formatted_recipes = [{"ingredients": recipe} for recipe in selected_combination]
        
        print(f"RecipeManager: Sélectionné la combinaison {selected_index + 1} avec {len(formatted_recipes)} recettes")
        
        return formatted_recipes
    
    def get_recipe_configuration(self):
        """
        Retourne la configuration des recettes (valeurs, temps)
        
        Returns:
            dict: Configuration avec onion_value, tomato_value, onion_time, tomato_time
        """
        if not self.config:
            # Configuration par défaut
            return {
                'onion_value': 3,
                'tomato_value': 2,
                'onion_time': 9,
                'tomato_time': 6
            }
        
        return {
            'onion_value': self.config.get('onion_value', 3),
            'tomato_value': self.config.get('tomato_value', 2),
            'onion_time': self.config.get('onion_time', 9),
            'tomato_time': self.config.get('tomato_time', 6)
        }
    
    def get_statistics(self):
        """Retourne des statistiques sur les recettes chargées"""
        if not self.recipe_data:
            return {"status": "Aucune recette chargée"}
        
        stats = self.recipe_data.get('statistics', {})
        return {
            "total_combinations": len(self.available_recipes),
            "combinations_used": len(self.used_combinations),
            "combinations_remaining": len(self.available_recipes) - len(self.used_combinations),
            "unique_recipes": stats.get('unique_recipes_count', 'Unknown'),
            "recipes_per_combination": stats.get('recipes_per_combination', 'Unknown')
        }



def mdp_fn_random_choice(mdp_fn_choices):
    assert type(mdp_fn_choices) is list and len(mdp_fn_choices) > 0
    return random.choice(mdp_fn_choices)


"""
size_bounds: (min_layout_size, max_layout_size)
prop_empty: (min, max) proportion of empty space in generated layout
prop_feats: (min, max) proportion of counters with features on them
"""
DEFAULT_FEATURE_TYPES = (POT, ONION_DISPENSER, DISH_DISPENSER, SERVING_LOC) # NOTE: TOMATO_DISPENSER is disabled by default

DEFAULT_MDP_GEN_PARAMS = {
    "inner_shape": (7, 7),  # Taille interne du layout (largeur, hauteur)
    "prop_empty": 0.95, # 95% d'espace vide minimum 
    "prop_feats": 0.1,  # 10% des comptoirs avec des fonctionnalités
    "start_all_orders" : [  # Recettes disponibles au début
        { "ingredients" : ["onion", "onion", "onion"]}
    ],
    "feature_types" : DEFAULT_FEATURE_TYPES,    # Types d'éléments à placer
    # Nombre minimum de chaque type d'objet
    "min_pots": 1,              # Nombre minimum de casseroles
    "min_onion_dispensers": 1,  # Nombre minimum de distributeurs d'oignons
    "min_tomato_dispensers": 1, # Nombre minimum de distributeurs de tomates
    "min_dish_dispensers": 1,   # Nombre minimum de distributeurs d'assiettes
    "min_serving_locations": 1, # Nombre minimum de zones de service
    "num_layouts_to_generate": 1 , # Nombre de layouts à générer (défaut réduit)
    "recipe_values" : [20], # Valeurs des recettes
    "recipe_times" : [20],  # Temps de cuisson
    "display": False,   # Affichage debug
    "intentions_sharing" : True, # Partage d'intentions entre agents
    # Nouveaux paramètres pour l'intégration des recettes
    "use_recipe_file": True,  # Utiliser ensemble_recettes.json
    "recipe_file_path": "ensemble_recettes.json",  # Chemin vers le fichier de recettes
    "recipe_sampling": "with_replacement",  # "with_replacement" ou "without_replacement"
    # Paramètre de type de layout
    "layout_type": "symetrique",  # "symetrique" ou "complementaire"
    # Paramètre de complexité pour layouts symétriques
    "complexity": False  # Si True, génère un labyrinthe central pour encourager les échanges
}


def DEFAULT_PARAMS_SCHEDULE_FN(outside_information = DEFAULT_MDP_GEN_PARAMS):
    mdp_default_gen_params = outside_information
    return mdp_default_gen_params


class MDPParamsGenerator(object):

    def __init__(self, params_schedule_fn):
        """
        params_schedule_fn (callable): the function to produce a set of mdp_params for a specific layout
        """
        assert callable(params_schedule_fn), "params scheduling function must be a callable"
        self.params_schedule_fn = params_schedule_fn

    @staticmethod
    def from_fixed_param(mdp_params_always):
        # s naive schedule function that always return the same set of parameter
        naive_schedule_fn = lambda _ignored: mdp_params_always
        return MDPParamsGenerator(naive_schedule_fn)

    def generate(self, outside_information={}):
        """
        generate a set of mdp_params that can be used to generate a mdp
        outside_information (dict): passing in outside information
        """
        assert type(outside_information) is dict
        mdp_params = self.params_schedule_fn(outside_information)
        return mdp_params


class LayoutGenerator(object):
    # NOTE: This class hasn't been tested extensively.

    def __init__(self, mdp_params_generator, outer_shape=(5, 4)):
        """
        Defines a layout generator that will return OvercoookedGridworld instances
        using mdp_params_generator
        """
        self.mdp_params_generator = mdp_params_generator
        self.outer_shape = outer_shape

    @staticmethod
    def mdp_gen_fn_from_dict(
            mdp_params, outer_shape=None, mdp_params_schedule_fn=None
    ):
        """
        mdp_params: one set of fixed mdp parameter used by the enviroment
        outer_shape: outer shape of the environment
        mdp_params_schedule_fn: the schedule for varying mdp params
        """
        # Mode 1: Layout prédéfini (outer_shape = None)
        # if outer_shape is not defined, we have to be using one of the defualt layout from names bank
        if outer_shape is None:
            # Charge un layout existant par nom
            assert type(mdp_params) is dict and "layout_name" in mdp_params
            mdp = OvercookedGridworld.from_layout_name(**mdp_params)
            mdp_fn = lambda _ignored: mdp
        # Mode 2: Génération procédurale (outer_shape spécifié)
        else:
            # Crée un générateur de layout dynamique
            # there is no schedule, we are using the same set of mdp_params all the time
            if mdp_params_schedule_fn is None:
                assert mdp_params is not None
                mdp_pg = MDPParamsGenerator.from_fixed_param(mdp_params_always=mdp_params)
            else:
                assert mdp_params is None, "please remove the mdp_params from the variable, " \
                                           "because mdp_params_schedule_fn exist and we will " \
                                           "always use the schedule_fn if it exist"
                mdp_pg = MDPParamsGenerator(params_schedule_fn=mdp_params_schedule_fn)
            lg = LayoutGenerator(mdp_pg, outer_shape)
            mdp_fn = lg.generate_padded_mdp
        return mdp_fn

    def generate_padded_mdp(self, outside_information={}):
        """
        Return a PADDED MDP with mdp params specified in self.mdp_params
        """
        mdp_gen_params = self.mdp_params_generator.generate(outside_information)
        # Vérification des paramètres requis
        outer_shape = self.outer_shape
        if "layout_name" in mdp_gen_params.keys() and mdp_gen_params["layout_name"] is not None:
            mdp = OvercookedGridworld.from_layout_name(**mdp_gen_params)
            mdp_generator_fn = lambda: self.padded_mdp(mdp)
        else:
            required_keys = ["inner_shape", "prop_empty", "prop_feats", "display"]
            # with generate_all_orders key start_all_orders will be generated inside make_new_layout method
            if not mdp_gen_params.get("generate_all_orders"): 
                required_keys.append("start_all_orders")
            missing_keys = [k for k in required_keys if k not in mdp_gen_params.keys()]
            if len(missing_keys) != 0:
                print("missing keys dict", mdp_gen_params)
            assert len(missing_keys) == 0, "These keys were missing from the mdp_params: {}".format(missing_keys)
            inner_shape = mdp_gen_params["inner_shape"]
            # Vérification que inner_shape rentre dans outer_shape
            assert inner_shape[0] <= outer_shape[0] and inner_shape[1] <= outer_shape[1], \
                "inner_shape cannot fit into the outershap"
            layout_generator = LayoutGenerator(self.mdp_params_generator, outer_shape=self.outer_shape)
            
            if "feature_types" not in mdp_gen_params:
                mdp_gen_params["feature_types"] = DEFAULT_FEATURE_TYPES
            # Génération du layout
            mdp_generator_fn = lambda: layout_generator.make_new_layout(mdp_gen_params)
        return mdp_generator_fn()
    
    @staticmethod
    def create_base_params(mdp_gen_params):
        assert mdp_gen_params.get("start_all_orders") or mdp_gen_params.get("generate_all_orders") or mdp_gen_params.get("use_recipe_file")
        
        # Si on utilise le fichier de recettes
        if mdp_gen_params.get("use_recipe_file", False):
            recipe_file_path = mdp_gen_params.get("recipe_file_path", "ensemble_recettes.json")
            recipe_sampling = mdp_gen_params.get("recipe_sampling", "without_replacement")
            
            # Utiliser le gestionnaire global pour maintenir l'état entre les générations
            recipe_manager = get_recipe_manager(recipe_file_path)
            
            # Obtenir une combinaison de recettes
            with_replacement = (recipe_sampling == "with_replacement")
            selected_recipes = recipe_manager.get_random_recipe_combination(with_replacement=with_replacement)
            
            # Obtenir la configuration des recettes
            recipe_config = recipe_manager.get_recipe_configuration()
            
            # Configurer Recipe avec les bonnes valeurs
            Recipe.configure({
                'onion_value': recipe_config['onion_value'],
                'tomato_value': recipe_config['tomato_value']
            })
            
            # Construire les paramètres de base
            recipe_params = {"start_all_orders": selected_recipes}
            
            # Les valeurs et temps dans le layout sont les valeurs unitaires des ingrédients
            # Pas les valeurs totales des recettes
            recipe_params["onion_value"] = recipe_config['onion_value']
            recipe_params["tomato_value"] = recipe_config['tomato_value']
            recipe_params["onion_time"] = recipe_config['onion_time']
            recipe_params["tomato_time"] = recipe_config['tomato_time']
            
            # Optionnel: calculer aussi les valeurs totales pour information
            recipe_values = []
            recipe_times = []
            
            for recipe_dict in selected_recipes:
                ingredients = recipe_dict["ingredients"]
                recipe_value = sum(
                    recipe_config['onion_value'] if ing == 'onion' else recipe_config['tomato_value']
                    for ing in ingredients
                )
                recipe_time = sum(
                    recipe_config['onion_time'] if ing == 'onion' else recipe_config['tomato_time']
                    for ing in ingredients
                )
                recipe_values.append(recipe_value)
                recipe_times.append(recipe_time)
            
            print(f"LayoutGenerator: Utilisation des recettes du fichier {recipe_file_path}")
            print(f"  - {len(selected_recipes)} recettes sélectionnées")
            print(f"  - Valeurs unitaires: oignon={recipe_config['onion_value']}, tomate={recipe_config['tomato_value']}")
            print(f"  - Temps unitaires: oignon={recipe_config['onion_time']}, tomate={recipe_config['tomato_time']}")
            print(f"  - Valeurs des recettes: {recipe_values}")
            print(f"  - Temps des recettes: {recipe_times}")
            
            # Afficher les statistiques
            stats = recipe_manager.get_statistics()
            print(f"  - Statistiques: {stats}")
            
        else:
            # Utiliser la méthode originale
            mdp_gen_params = LayoutGenerator.add_generated_mdp_params_orders(mdp_gen_params)
            recipe_params = {"start_all_orders": mdp_gen_params["start_all_orders"]}
            if mdp_gen_params.get("start_bonus_orders"):
                recipe_params["start_bonus_orders"] = mdp_gen_params["start_bonus_orders"]
            if "recipe_values" in mdp_gen_params:
                recipe_params["recipe_values"] = mdp_gen_params["recipe_values"]
            if "recipe_times" in mdp_gen_params:
                recipe_params["recipe_times"] = mdp_gen_params["recipe_times"]
        
        # Paramètres communs
        if mdp_gen_params.get("intentions_sharing") is not None:
            recipe_params["intentions_sharing"] = mdp_gen_params["intentions_sharing"]
            
        return recipe_params
        
    @staticmethod
    def add_generated_mdp_params_orders(mdp_params):
        """
        adds generated parameters (i.e. generated orders) to mdp_params,
        returns onchanged copy of mdp_params when there is no "generate_all_orders" and "generate_bonus_orders" keys inside mdp_params
        """
        mdp_params = copy.deepcopy(mdp_params)
        if mdp_params.get("generate_all_orders"):
            all_orders_kwargs = copy.deepcopy(mdp_params["generate_all_orders"])

            if all_orders_kwargs.get("recipes"):
                 all_orders_kwargs["recipes"] = [Recipe.from_dict(r) for r in all_orders_kwargs["recipes"]]
        
            all_recipes = Recipe.generate_random_recipes(**all_orders_kwargs)
            mdp_params["start_all_orders"] = [r.to_dict() for r in all_recipes]
        else:
            Recipe.configure({})
            all_recipes = Recipe.ALL_RECIPES

        if mdp_params.get("generate_bonus_orders"):
            bonus_orders_kwargs = copy.deepcopy(mdp_params["generate_bonus_orders"])

            if not bonus_orders_kwargs.get("recipes"): 
                bonus_orders_kwargs["recipes"] = all_recipes

            bonus_recipes = Recipe.generate_random_recipes(**bonus_orders_kwargs)
            mdp_params["start_bonus_orders"] = [r.to_dict() for r in bonus_recipes]
        return mdp_params

    def padded_mdp(self, mdp, display=False):
        """Returns a padded MDP from an MDP"""
        grid = Grid.from_mdp(mdp)
        padded_grid = self.embed_grid(grid)

        start_positions = self.get_random_starting_positions(padded_grid)
        mdp_grid = self.padded_grid_to_layout_grid(padded_grid, start_positions, display=display)
        return OvercookedGridworld.from_grid(mdp_grid)

    def make_new_layout(self, mdp_gen_params):
        # Extraire tous les paramètres nécessaires
        layout_params = {
            'inner_shape': mdp_gen_params["inner_shape"],
            'prop_empty': mdp_gen_params["prop_empty"],
            'prop_features': mdp_gen_params["prop_feats"],
            'base_param': LayoutGenerator.create_base_params(mdp_gen_params),
            'feature_types': mdp_gen_params["feature_types"],
            'display': mdp_gen_params["display"],
            # Nouveaux paramètres pour les nombres minimum
            'min_pots': mdp_gen_params.get("min_pots", 1),
            'min_onion_dispensers': mdp_gen_params.get("min_onion_dispensers", 1),
            'min_tomato_dispensers': mdp_gen_params.get("min_tomato_dispensers", 0),
            'min_dish_dispensers': mdp_gen_params.get("min_dish_dispensers", 1),
            'min_serving_locations': mdp_gen_params.get("min_serving_locations", 1),
            # Paramètre de type de layout
            'layout_type': mdp_gen_params.get("layout_type", "symetrique"),
            # Paramètre de complexité
            'complexity': mdp_gen_params.get("complexity", False)
        }
        return self.make_disjoint_sets_layout(**layout_params)      

    def make_disjoint_sets_layout(self, inner_shape, prop_empty, prop_features, base_param, feature_types=DEFAULT_FEATURE_TYPES, display=True, **kwargs):        
        # 1. Créer une grille pleine de comptoirs
        grid = Grid(inner_shape)
        
        # Récupérer le type de layout
        layout_type = kwargs.get('layout_type', 'symetrique')
        complexity = kwargs.get('complexity', False)
        
        if layout_type == "complementaire":
            # 2. Pour layout complémentaire: créer un mur central et creuser chaque côté séparément
            self.create_complementary_layout(grid, prop_empty, layout_type)
        else:
            # 2. Pour layout symétrique: creuser des espaces vides connectés
            if complexity:
                # Layout symétrique complexe avec structure labyrinthique centrale
                self.dig_complex_symmetric_layout(grid, prop_empty)
            else:
                # Layout symétrique simple (comportement normal)
                self.dig_space_with_disjoint_sets(grid, prop_empty)
        
        # 3. Ajouter les fonctionnalités (casseroles, distributeurs, etc.)
        # Extraire les paramètres de nombre minimum depuis kwargs
        min_params = {
            'min_pots': kwargs.get('min_pots', 1),
            'min_onion_dispensers': kwargs.get('min_onion_dispensers', 1),
            'min_tomato_dispensers': kwargs.get('min_tomato_dispensers', 0),
            'min_dish_dispensers': kwargs.get('min_dish_dispensers', 1),
            'min_serving_locations': kwargs.get('min_serving_locations', 1)
        }
        
        if layout_type == "complementaire":
            self.add_features_complementary(grid, prop_features, feature_types, **min_params)
        elif layout_type == "symetrique" and complexity:
            self.add_features_complex_symmetric(grid, prop_features, feature_types, **min_params)
        else:
            self.add_features(grid, prop_features, feature_types, **min_params)
        
        # 4. Emballer dans une grille plus grande
        padded_grid = self.embed_grid(grid)
        
        # 5. Placer les positions de départ des joueurs selon le type de layout
        if layout_type == "complementaire":
            start_positions = self.get_complementary_starting_positions(padded_grid)
        else:
            start_positions = self.get_random_starting_positions(padded_grid)
        
        # 6. Convertir en format OvercookedGridworld avec le type de layout
        mdp_grid = self.padded_grid_to_layout_grid(padded_grid, start_positions, display=display)
        
        # Ajouter le type de layout aux paramètres de base
        base_param_with_layout_type = base_param.copy()
        base_param_with_layout_type["layout_type"] = layout_type
        
        return OvercookedGridworld.from_grid(mdp_grid, base_param_with_layout_type)

    def padded_grid_to_layout_grid(self, padded_grid, start_positions, display=False):
        if display:
            print("Generated layout")
            print(padded_grid)

        # Start formatting to actual OvercookedGridworld input type
        mdp_grid = padded_grid.convert_to_string()

        for i, pos in enumerate(start_positions):
            x, y = pos
            mdp_grid[y][x] = str(i + 1)

        return mdp_grid

    def embed_grid(self, grid):
        """Randomly embeds a smaller grid in a grid of size self.outer_shape"""
        # Check that smaller grid fits
        assert all(grid.shape <= self.outer_shape)

        padded_grid = Grid(self.outer_shape)
        x_leeway, y_leeway = self.outer_shape - grid.shape
        starting_x = np.random.randint(0, x_leeway) if x_leeway else 0
        starting_y = np.random.randint(0, y_leeway) if y_leeway else 0

        for x in range(grid.shape[0]):
            for y in range(grid.shape[1]):
                item = grid.terrain_at_loc((x, y))
                # Abstraction violation
                padded_grid.mtx[x + starting_x][y + starting_y] = item

        return padded_grid

    def dig_space_with_disjoint_sets(self, grid, prop_empty):
        dsets = DisjointSets([])    # Structure de données pour connectivité
        # Continue jusqu'à avoir assez d'espace vide ET tout connecté
        while not (grid.proportion_empty() > prop_empty and dsets.num_sets == 1):
            # Trouve un emplacement valide à creuser
            valid_dig_location = False
            while not valid_dig_location:
                loc = grid.get_random_interior_location()   # Position aléatoire interne
                valid_dig_location = grid.is_valid_dig_location(loc)
            # Creuse l'emplacement
            grid.dig(loc)
            dsets.add_singleton(loc)    # Ajoute aux ensembles disjoints
            # Connecte avec les voisins vides
            for neighbour in grid.get_near_locations(loc):
                if dsets.contains(neighbour):
                    dsets.union(neighbour, loc) # Fusionne les ensembles

    def create_complementary_layout(self, grid, prop_empty, layout_type):
        """
        Crée un layout complémentaire avec un mur central séparant deux zones distinctes
        """
        # Déterminer la direction du mur central (vertical ou horizontal)
        width, height = grid.shape
        
        # Choisir la direction selon les dimensions
        if width >= height:
            # Mur vertical au centre
            wall_x = width // 2
            self.create_vertical_separation(grid, wall_x)
            # Creuser chaque côté séparément
            self.dig_complementary_sides_vertical(grid, wall_x, prop_empty)
        else:
            # Mur horizontal au centre
            wall_y = height // 2
            self.create_horizontal_separation(grid, wall_y)
            # Creuser chaque côté séparément
            self.dig_complementary_sides_horizontal(grid, wall_y, prop_empty)

    def create_vertical_separation(self, grid, wall_x):
        """Crée une séparation verticale avec des ouvertures pour les échanges"""
        # Créer le mur complet d'abord
        for y in range(grid.shape[1]):
            grid.mtx[wall_x][y] = TYPE_TO_CODE[COUNTER]
        
        # Ajouter 1-2 ouvertures dans le mur pour permettre les échanges
        height = grid.shape[1]
        if height >= 5:  # Assez de hauteur pour des ouvertures
            # Calculer les positions d'ouvertures (éviter les bords)
            available_positions = list(range(2, height - 2))  # Éviter les 2 cases du bord
            
            if len(available_positions) >= 2:
                # 2 ouvertures pour des layouts plus grands
                opening_positions = np.random.choice(available_positions, size=2, replace=False)
            elif len(available_positions) >= 1:
                # 1 ouverture pour des layouts moyens
                opening_positions = np.random.choice(available_positions, size=1, replace=False)
            else:
                # Aucune ouverture possible (layout trop petit)
                opening_positions = []
            
            # Créer les ouvertures
            for y_opening in opening_positions:
                grid.mtx[wall_x][y_opening] = TYPE_TO_CODE[EMPTY]
            
            print(f"🔧 Mur vertical créé à x={wall_x} avec {len(opening_positions)} ouverture(s) à y={list(opening_positions)}")
        else:
            print(f"🔧 Mur vertical créé à x={wall_x} (pas d'ouverture - layout trop petit)")

    def create_horizontal_separation(self, grid, wall_y):
        """Crée une séparation horizontale avec des ouvertures pour les échanges"""
        # Créer le mur complet d'abord
        for x in range(grid.shape[0]):
            grid.mtx[x][wall_y] = TYPE_TO_CODE[COUNTER]
        
        # Ajouter 1-2 ouvertures dans le mur pour permettre les échanges
        width = grid.shape[0]
        if width >= 5:  # Assez de largeur pour des ouvertures
            # Calculer les positions d'ouvertures (éviter les bords)
            available_positions = list(range(2, width - 2))  # Éviter les 2 cases du bord
            
            if len(available_positions) >= 2:
                # 2 ouvertures pour des layouts plus grands
                opening_positions = np.random.choice(available_positions, size=2, replace=False)
            elif len(available_positions) >= 1:
                # 1 ouverture pour des layouts moyens
                opening_positions = np.random.choice(available_positions, size=1, replace=False)
            else:
                # Aucune ouverture possible (layout trop petit)
                opening_positions = []
            
            # Créer les ouvertures
            for x_opening in opening_positions:
                grid.mtx[x_opening][wall_y] = TYPE_TO_CODE[EMPTY]
            
            print(f"🔧 Mur horizontal créé à y={wall_y} avec {len(opening_positions)} ouverture(s) à x={list(opening_positions)}")
        else:
            print(f"🔧 Mur horizontal créé à y={wall_y} (pas d'ouverture - layout trop petit)")

    def dig_complementary_sides_vertical(self, grid, wall_x, prop_empty):
        """Creuse les deux côtés d'un layout avec mur vertical"""
        # Côté gauche (x < wall_x)
        self.dig_side_with_disjoint_sets(grid, 1, wall_x, 1, grid.shape[1] - 1, prop_empty)
        # Côté droit (x > wall_x)
        self.dig_side_with_disjoint_sets(grid, wall_x + 1, grid.shape[0] - 1, 1, grid.shape[1] - 1, prop_empty)

    def dig_complementary_sides_horizontal(self, grid, wall_y, prop_empty):
        """Creuse les deux côtés d'un layout avec mur horizontal"""
        # Côté haut (y < wall_y)
        self.dig_side_with_disjoint_sets(grid, 1, grid.shape[0] - 1, 1, wall_y, prop_empty)
        # Côté bas (y > wall_y)
        self.dig_side_with_disjoint_sets(grid, 1, grid.shape[0] - 1, wall_y + 1, grid.shape[1] - 1, prop_empty)

    def dig_side_with_disjoint_sets(self, grid, min_x, max_x, min_y, max_y, prop_empty):
        """
        Creuse une zone spécifique avec l'algorithme des ensembles disjoints
        Respecte les limites strictes de la zone pour maintenir la séparation
        """
        dsets = DisjointSets([])
        
        # Calculer la taille de la zone (en excluant les bords)
        zone_width = max_x - min_x - 1  # -1 pour exclure les bords
        zone_height = max_y - min_y - 1
        zone_interior_size = max(1, zone_width * zone_height)
        target_empty = max(1, int(zone_interior_size * prop_empty))
        current_empty = 0
        
        print(f"🏗️  Creusage zone: x[{min_x}-{max_x}], y[{min_y}-{max_y}], target={target_empty} espaces")
        
        while current_empty < target_empty or (len(dsets.parents) > 0 and dsets.num_sets > 1):
            # Trouve un emplacement valide à creuser dans cette zone (exclut les bords)
            valid_dig_location = False
            attempts = 0
            while not valid_dig_location and attempts < 200:
                x = np.random.randint(min_x + 1, max_x)  # +1/-1 pour éviter les bords
                y = np.random.randint(min_y + 1, max_y)
                loc = (x, y)
                
                # Vérifier que c'est dans la zone autorisée ET que c'est creusable
                valid_dig_location = (min_x < x < max_x and 
                                    min_y < y < max_y and 
                                    grid.is_valid_dig_location(loc))
                attempts += 1
            
            if not valid_dig_location:
                if current_empty < target_empty // 2:  # Si on n'a pas assez creusé
                    print(f"⚠️  Impossible de creuser plus dans la zone, {current_empty}/{target_empty} espaces creusés")
                break
            
            # Creuse l'emplacement
            grid.dig(loc)
            current_empty += 1
            dsets.add_singleton(loc)
            
            # Connecte avec les voisins vides dans la même zone UNIQUEMENT
            for neighbour in grid.get_near_locations(loc):
                nx, ny = neighbour
                # Vérifier que le voisin est dans la même zone ET qu'il existe dans dsets
                if (min_x < nx < max_x and min_y < ny < max_y and 
                    dsets.contains(neighbour) and grid.location_is_empty(neighbour)):
                    dsets.union(neighbour, loc)
        
        print(f"✅ Zone creusée: {current_empty} espaces, {dsets.num_sets} composantes connectées")

    def dig_complex_symmetric_layout(self, grid, prop_empty):
        """
        Crée un layout symétrique complexe avec une grande structure centrale
        qui augmente les distances de déplacement tout en maintenant la connectivité globale
        """
        width, height = grid.shape
        
        # Phase 1: Créer une grande structure centrale (obstacle)
        self.create_central_obstacle(grid)
        
        # Phase 2: Creuser autour de la structure pour créer des chemins longs
        self.dig_around_central_obstacle(grid, prop_empty)
        
        # Phase 3: Ajouter des obstacles supplémentaires dispersés
        self.add_scattered_obstacles(grid)
        
        # Phase 4: S'assurer que tout reste connecté (pas de séparation en deux)
        self.ensure_global_connectivity(grid)
        
        print(f"🏗️  Layout symétrique complexe créé avec grande structure centrale")

    def create_central_obstacle(self, grid):
        """
        Crée une grande structure centrale qui peut toucher un bord
        mais ne sépare jamais le layout en deux zones
        """
        width, height = grid.shape
        
        # Définir la taille de la structure centrale (environ 50-70% de chaque dimension pour plus d'obstacles)
        obstacle_width = max(3, int(width * 0.5) + random.randint(0, int(width * 0.2)))
        obstacle_height = max(3, int(height * 0.5) + random.randint(0, int(height * 0.2)))
        
        # Choisir la position de l'obstacle (peut toucher un bord)
        # Position aléatoire qui permet à l'obstacle de toucher les bords
        start_x = random.randint(0, width - obstacle_width)
        start_y = random.randint(0, height - obstacle_height)
        
        # S'assurer qu'on ne crée pas une séparation complète
        # L'obstacle ne doit jamais faire toute la largeur OU toute la hauteur
        if obstacle_width >= width - 1:
            obstacle_width = width - 2  # Laisser au moins 1 case de chaque côté
        if obstacle_height >= height - 1:
            obstacle_height = height - 2  # Laisser au moins 1 case de chaque côté
        
        # Créer la structure centrale (reste des comptoirs)
        for x in range(start_x, min(start_x + obstacle_width, width)):
            for y in range(start_y, min(start_y + obstacle_height, height)):
                # Garder comme comptoir (ne pas creuser)
                pass  # Les comptoirs sont déjà là par défaut
        
        # Ajouter quelques extensions aléatoires pour rendre la forme plus complexe
        self.add_obstacle_extensions(grid, start_x, start_y, obstacle_width, obstacle_height)
        
        print(f"🏗️  Structure centrale créée: {obstacle_width}x{obstacle_height} à position ({start_x}, {start_y})")

    def add_obstacle_extensions(self, grid, base_x, base_y, base_width, base_height):
        """
        Ajoute des extensions à la structure centrale pour la rendre plus complexe
        """
        width, height = grid.shape
        
        # Ajouter 1-3 extensions aléatoires
        num_extensions = random.randint(1, 3)
        
        for _ in range(num_extensions):
            # Choisir un côté de la structure de base pour l'extension
            side = random.choice(['top', 'bottom', 'left', 'right'])
            
            if side == 'top' and base_y > 1:
                # Extension vers le haut
                ext_width = random.randint(2, max(2, base_width // 2))
                ext_height = random.randint(1, base_y)
                ext_x = base_x + random.randint(0, max(0, base_width - ext_width))
                ext_y = base_y - ext_height
                self.create_extension(grid, ext_x, ext_y, ext_width, ext_height)
                
            elif side == 'bottom' and base_y + base_height < height - 1:
                # Extension vers le bas
                ext_width = random.randint(2, max(2, base_width // 2))
                ext_height = random.randint(1, height - (base_y + base_height))
                ext_x = base_x + random.randint(0, max(0, base_width - ext_width))
                ext_y = base_y + base_height
                self.create_extension(grid, ext_x, ext_y, ext_width, ext_height)
                
            elif side == 'left' and base_x > 1:
                # Extension vers la gauche
                ext_width = random.randint(1, base_x)
                ext_height = random.randint(2, max(2, base_height // 2))
                ext_x = base_x - ext_width
                ext_y = base_y + random.randint(0, max(0, base_height - ext_height))
                self.create_extension(grid, ext_x, ext_y, ext_width, ext_height)
                
            elif side == 'right' and base_x + base_width < width - 1:
                # Extension vers la droite
                ext_width = random.randint(1, width - (base_x + base_width))
                ext_height = random.randint(2, max(2, base_height // 2))
                ext_x = base_x + base_width
                ext_y = base_y + random.randint(0, max(0, base_height - ext_height))
                self.create_extension(grid, ext_x, ext_y, ext_width, ext_height)

    def create_extension(self, grid, start_x, start_y, ext_width, ext_height):
        """
        Crée une extension de la structure centrale
        """
        width, height = grid.shape
        
        for x in range(start_x, min(start_x + ext_width, width)):
            for y in range(start_y, min(start_y + ext_height, height)):
                if 0 <= x < width and 0 <= y < height:
                    # Garder comme comptoir (obstacle)
                    pass

    def dig_around_central_obstacle(self, grid, prop_empty):
        """
        Creuse des espaces autour de la structure centrale pour créer des chemins longs
        Réduit la proportion d'espaces vides pour les layouts complexes
        """
        dsets = DisjointSets([])
        
        # Pour les layouts complexes, réduire la proportion d'espaces vides
        # pour avoir plus de comptoirs et des chemins plus tortueux
        complex_prop_empty = min(prop_empty * 0.6, 0.4)  # Réduire à 60% de la proportion normale, max 40%
        
        # Phase 1: Créer des espaces autour de l'obstacle de manière stratégique
        self.create_perimeter_spaces(grid, dsets)
        
        # Phase 2: Continuer à creuser pour atteindre la proportion d'espace vide réduite
        target_empty_ratio = complex_prop_empty
        attempts_without_progress = 0
        
        while grid.proportion_empty() < target_empty_ratio and attempts_without_progress < 50:
            # Trouver une position valide à creuser qui maintient la connectivité
            valid_dig_location = False
            attempts = 0
            
            while not valid_dig_location and attempts < 100:
                loc = grid.get_random_interior_location()
                valid_dig_location = grid.is_valid_dig_location(loc)
                attempts += 1
            
            if not valid_dig_location:
                attempts_without_progress += 1
                continue  # Essayer encore
            
            # Creuser et maintenir la connectivité
            grid.dig(loc)
            dsets.add_singleton(loc)
            attempts_without_progress = 0  # Reset le compteur
            
            # Connecter avec les voisins vides
            for neighbour in grid.get_near_locations(loc):
                if dsets.contains(neighbour) and grid.location_is_empty(neighbour):
                    dsets.union(neighbour, loc)
        
        print(f"🏗️  Layout complexe: {grid.proportion_empty():.2%} d'espaces vides (cible: {target_empty_ratio:.2%})")

    def add_scattered_obstacles(self, grid):
        """
        Ajoute des obstacles (comptoirs) dispersés pour complexifier davantage le layout
        """
        width, height = grid.shape
        
        # Calculer le nombre d'obstacles à ajouter (environ 10-20% des espaces vides)
        empty_count = sum(1 for x in range(width) for y in range(height) if grid.location_is_empty((x, y)))
        num_obstacles = random.randint(max(1, empty_count // 10), max(2, empty_count // 5))
        
        obstacles_added = 0
        attempts = 0
        max_attempts = num_obstacles * 5
        
        while obstacles_added < num_obstacles and attempts < max_attempts:
            # Choisir une position aléatoire
            x = random.randint(1, width - 2)
            y = random.randint(1, height - 2)
            loc = (x, y)
            
            # Vérifier que c'est un espace vide et qu'on peut y placer un obstacle
            if (grid.location_is_empty(loc) and 
                self.can_place_obstacle_safely(grid, loc)):
                
                # Placer l'obstacle (remettre un comptoir)
                grid.change_location(loc, COUNTER)
                obstacles_added += 1
            
            attempts += 1
        
        print(f"🏗️  {obstacles_added} obstacles dispersés ajoutés")

    def can_place_obstacle_safely(self, grid, loc):
        """
        Vérifie si on peut placer un obstacle à cette position sans couper la connectivité
        """
        x, y = loc
        
        # Vérifier qu'il y a au moins 2 voisins vides pour maintenir un chemin
        empty_neighbors = []
        for neighbor in grid.get_near_locations(loc):
            if grid.location_is_empty(neighbor):
                empty_neighbors.append(neighbor)
        
        # S'il y a moins de 2 voisins vides, on risque de créer une impasse
        if len(empty_neighbors) < 2:
            return False
        
        # Vérifier qu'on ne crée pas une séparation totale
        # Simple heuristique: s'assurer qu'il y a au moins un chemin horizontal OU vertical
        horizontal_path = (
            (x > 0 and grid.location_is_empty((x-1, y))) and 
            (x < grid.shape[0]-1 and grid.location_is_empty((x+1, y)))
        )
        vertical_path = (
            (y > 0 and grid.location_is_empty((x, y-1))) and 
            (y < grid.shape[1]-1 and grid.location_is_empty((x, y+1)))
        )
        
        # Ne pas placer d'obstacle si cela coupe tous les chemins directs
        if not horizontal_path and not vertical_path:
            return False
        
        return True

    def create_perimeter_spaces(self, grid, dsets):
        """
        Crée des espaces autour de la structure centrale pour forcer des chemins longs
        """
        width, height = grid.shape
        
        # Créer des couloirs autour de la structure centrale
        # Stratégie: creuser des chemins qui contournent l'obstacle
        
        # 1. Créer des espaces près des bords pour assurer l'accessibilité
        self.dig_perimeter_corridors(grid, dsets)
        
        # 2. Créer des espaces stratégiques qui forcent le contournement
        self.dig_bypass_corridors(grid, dsets)

    def dig_perimeter_corridors(self, grid, dsets):
        """
        Creuse des couloirs le long des bords pour maintenir l'accessibilité
        Réduit la probabilité de creusage pour garder plus de comptoirs
        """
        width, height = grid.shape
        
        # Réduire la probabilité de creusage pour avoir plus de comptoirs
        dig_probability = 0.4  # Réduit de 0.7 à 0.4
        
        # Couloir le long du bord haut
        for x in range(1, width - 1):
            y = 1
            if grid.is_valid_dig_location((x, y)) and random.random() < dig_probability:
                grid.dig((x, y))
                dsets.add_singleton((x, y))
        
        # Couloir le long du bord bas
        for x in range(1, width - 1):
            y = height - 2
            if grid.is_valid_dig_location((x, y)) and random.random() < dig_probability:
                grid.dig((x, y))
                dsets.add_singleton((x, y))
        
        # Couloir le long du bord gauche
        for y in range(1, height - 1):
            x = 1
            if grid.is_valid_dig_location((x, y)) and random.random() < dig_probability:
                grid.dig((x, y))
                dsets.add_singleton((x, y))
        
        # Couloir le long du bord droit
        for y in range(1, height - 1):
            x = width - 2
            if grid.is_valid_dig_location((x, y)) and random.random() < dig_probability:
                grid.dig((x, y))
                dsets.add_singleton((x, y))
        
        # Connecter les espaces creusés
        self.connect_dug_spaces(grid, dsets)

    def dig_bypass_corridors(self, grid, dsets):
        """
        Crée des couloirs qui permettent de contourner la structure centrale
        Réduit la densité pour garder plus de comptoirs
        """
        width, height = grid.shape
        
        # Identifier les zones autour de la structure centrale
        # et créer des chemins de contournement
        
        # Créer des espaces dans les coins pour faciliter le contournement
        corner_size = min(width, height) // 4
        corner_dig_probability = 0.3  # Réduit de 0.6 à 0.3
        
        # Coin haut-gauche
        for x in range(1, min(corner_size + 1, width - 1)):
            for y in range(1, min(corner_size + 1, height - 1)):
                if grid.is_valid_dig_location((x, y)) and random.random() < corner_dig_probability:
                    grid.dig((x, y))
                    dsets.add_singleton((x, y))
        
        # Coin bas-droite
        for x in range(max(width - corner_size - 1, 1), width - 1):
            for y in range(max(height - corner_size - 1, 1), height - 1):
                if grid.is_valid_dig_location((x, y)) and random.random() < corner_dig_probability:
                    grid.dig((x, y))
                    dsets.add_singleton((x, y))
        
        # Connecter les nouveaux espaces
        self.connect_dug_spaces(grid, dsets)

    def connect_dug_spaces(self, grid, dsets):
        """
        Connecte tous les espaces creusés pour maintenir la connectivité
        """
        # Connecter les espaces adjacents
        for x in range(grid.shape[0]):
            for y in range(grid.shape[1]):
                if grid.location_is_empty((x, y)):
                    if not dsets.contains((x, y)):
                        dsets.add_singleton((x, y))
                    
                    # Connecter avec les voisins vides
                    for neighbour in grid.get_near_locations((x, y)):
                        if grid.location_is_empty(neighbour):
                            if not dsets.contains(neighbour):
                                dsets.add_singleton(neighbour)
                            dsets.union(neighbour, (x, y))

    def create_player_zones(self, grid, prop_empty):
        """
        Crée des zones spacieuses dans les coins pour chaque joueur
        """
        width, height = grid.shape
        
        # Zone joueur 1 (coin haut-gauche)
        zone1_width = width // 3
        zone1_height = height // 3
        self.dig_rectangular_zone(grid, 1, zone1_width, 1, zone1_height, density=0.8)
        
        # Zone joueur 2 (coin bas-droite) 
        zone2_start_x = width - zone1_width - 1
        zone2_start_y = height - zone1_height - 1
        self.dig_rectangular_zone(grid, zone2_start_x, width - 1, zone2_start_y, height - 1, density=0.8)
        
        # Zones intermédiaires plus petites (pour équipements partagés)
        if width >= 7 and height >= 7:
            # Zone haut-droite (moins dense)
            self.dig_rectangular_zone(grid, zone2_start_x, width - 1, 1, zone1_height, density=0.4)
            # Zone bas-gauche (moins dense)
            self.dig_rectangular_zone(grid, 1, zone1_width, zone2_start_y, height - 1, density=0.4)

    def dig_rectangular_zone(self, grid, min_x, max_x, min_y, max_y, density=0.6):
        """
        Creuse une zone rectangulaire avec une densité donnée
        """
        for x in range(min_x, max_x):
            for y in range(min_y, max_y):
                if np.random.random() < density and grid.is_valid_dig_location((x, y)):
                    grid.dig((x, y))

    def create_central_maze(self, grid):
        """
        Crée un labyrinthe dans la zone centrale pour rallonger les chemins
        """
        width, height = grid.shape
        
        # Définir la zone centrale (tiers central de chaque dimension)
        center_x_start = width // 3
        center_x_end = 2 * width // 3
        center_y_start = height // 3  
        center_y_end = 2 * height // 3
        
        # Créer des chemins tortueux dans le centre
        # Stratégie: créer des "îlots" de comptoirs pour forcer des détours
        for x in range(center_x_start, center_x_end):
            for y in range(center_y_start, center_y_end):
                # Probabilité de garder un comptoir pour créer des obstacles
                if (x + y) % 3 == 0 and np.random.random() < 0.4:
                    # Laisser le comptoir (ne pas creuser)
                    continue
                # Sinon, probabilité de creuser selon un pattern
                elif (x % 2 == 0 and y % 2 == 1) or (x % 2 == 1 and y % 2 == 0):
                    if np.random.random() < 0.7 and grid.is_valid_dig_location((x, y)):
                        grid.dig((x, y))
        
        # Ajouter quelques chemins forcés pour éviter les impasses totales
        self.add_forced_paths(grid, center_x_start, center_x_end, center_y_start, center_y_end)

    def add_forced_paths(self, grid, x_start, x_end, y_start, y_end):
        """
        Ajoute des chemins forcés pour garantir la connectivité dans le labyrinthe
        """
        # Chemin horizontal central
        center_y = (y_start + y_end) // 2
        for x in range(x_start, x_end):
            if grid.is_valid_dig_location((x, center_y)):
                grid.dig((x, center_y))
        
        # Chemin vertical central  
        center_x = (x_start + x_end) // 2
        for y in range(y_start, y_end):
            if grid.is_valid_dig_location((center_x, y)):
                grid.dig((center_x, y))

    def ensure_global_connectivity(self, grid):
        """
        S'assure que toutes les zones creusées restent connectées
        """
        dsets = DisjointSets([])
        
        # Identifier toutes les positions vides
        for x in range(grid.shape[0]):
            for y in range(grid.shape[1]):
                if grid.location_is_empty((x, y)):
                    dsets.add_singleton((x, y))
                    # Connecter avec les voisins vides
                    for neighbour in grid.get_near_locations((x, y)):
                        if dsets.contains(neighbour) and grid.location_is_empty(neighbour):
                            dsets.union(neighbour, (x, y))
        
        # Si il y a plus d'une composante connectée, créer des ponts
        max_attempts = 50
        while dsets.num_sets > 1 and max_attempts > 0:
            # Trouver une position pour créer un pont
            bridge_location = grid.get_random_interior_location()
            if grid.is_valid_dig_location(bridge_location):
                grid.dig(bridge_location)
                dsets.add_singleton(bridge_location)
                # Reconnecter
                for neighbour in grid.get_near_locations(bridge_location):
                    if dsets.contains(neighbour) and grid.location_is_empty(neighbour):
                        dsets.union(neighbour, bridge_location)
            max_attempts -= 1
        
        print(f"🔗 Connectivité assurée: {dsets.num_sets} composante(s) connectée(s)")

    def add_features_complex_symmetric(self, grid, prop_features=0, feature_types=DEFAULT_FEATURE_TYPES,
                                     min_pots=1, min_onion_dispensers=1, min_tomato_dispensers=0,
                                     min_dish_dispensers=1, min_serving_locations=1):
        """
        Place les fonctionnalités de manière stratégique dans un layout complexe
        pour maximiser la nécessité d'échanges entre joueurs en les éloignant de la structure centrale
        """
        valid_locations = grid.valid_feature_locations()
        np.random.shuffle(valid_locations)
        
        width, height = grid.shape
        
        # Identifier les zones éloignées de la structure centrale
        # Privilégier les bords et coins pour forcer les longs déplacements
        edge_locations = [(x, y) for x, y in valid_locations 
                         if x <= 2 or x >= width-3 or y <= 2 or y >= height-3]  # Près des bords
        corner_locations = [(x, y) for x, y in valid_locations 
                           if (x <= 2 and y <= 2) or (x >= width-3 and y >= height-3) or 
                              (x <= 2 and y >= height-3) or (x >= width-3 and y <= 2)]  # Coins
        center_locations = [(x, y) for x, y in valid_locations 
                           if (x, y) not in edge_locations]  # Le reste (près du centre)
        
        features_placed = 0
        
        # Stratégie: placer les équipements essentiels loin les uns des autres
        # pour maximiser les distances de déplacement
        
        # 1. Placer les distributeurs d'ingrédients dans des coins opposés si possible
        if len(corner_locations) >= 2:
            # Distribuer dans des coins opposés
            if min_onion_dispensers > 0:
                for loc in corner_locations:
                    if grid.is_valid_feature_location(loc):
                        grid.add_feature(loc, ONION_DISPENSER)
                        features_placed += 1
                        min_onion_dispensers -= 1
                        break
            
            if min_tomato_dispensers > 0 and len(corner_locations) > 1:
                # Choisir un coin éloigné du premier
                remaining_corners = [loc for loc in corner_locations[1:] if grid.is_valid_feature_location(loc)]
                if remaining_corners:
                    opposite_corner = self.find_opposite_corner(corner_locations[0], remaining_corners)
                    grid.add_feature(opposite_corner, TOMATO_DISPENSER)
                    features_placed += 1
                    min_tomato_dispensers -= 1
        
        # 2. Placer les casseroles et zones de service loin des distributeurs
        remaining_edge = [loc for loc in edge_locations if loc not in corner_locations[:2]]
        
        if remaining_edge and min_pots > 0:
            # Vérifier que l'emplacement est valide avant de placer
            for loc in remaining_edge:
                if grid.is_valid_feature_location(loc):
                    grid.add_feature(loc, POT)
                    features_placed += 1
                    min_pots -= 1
                    break
        
        if len(remaining_edge) > 1 and min_serving_locations > 0:
            # Vérifier que l'emplacement est valide avant de placer
            for loc in remaining_edge[1:]:
                if grid.is_valid_feature_location(loc):
                    grid.add_feature(loc, SERVING_LOC)
                    features_placed += 1
                    min_serving_locations -= 1
                    break
        
        # 3. Distribuer le reste en privilégiant les emplacements éloignés
        min_requirements = {
            POT: min_pots,
            ONION_DISPENSER: min_onion_dispensers,
            TOMATO_DISPENSER: min_tomato_dispensers,
            DISH_DISPENSER: min_dish_dispensers,
            SERVING_LOC: min_serving_locations
        }
        
        # Utiliser d'abord les emplacements de bord, puis le centre si nécessaire
        all_remaining = (remaining_edge[2:] if len(remaining_edge) > 2 else []) + center_locations
        idx = 0
        
        # Placer les exigences minimales restantes
        for feature_type, min_count in min_requirements.items():
            for _ in range(min_count):
                if idx < len(all_remaining):
                    # Vérifier que l'emplacement est valide avant de placer
                    while idx < len(all_remaining) and not grid.is_valid_feature_location(all_remaining[idx]):
                        idx += 1
                    
                    if idx < len(all_remaining):
                        grid.add_feature(all_remaining[idx], feature_type)
                        idx += 1
                        features_placed += 1
        
        # Ajouter des fonctionnalités aléatoires selon la proportion
        while idx < len(all_remaining):
            current_prop = features_placed / len(valid_locations)
            if current_prop >= prop_features:
                break
            
            # Vérifier que l'emplacement est valide avant de placer
            while idx < len(all_remaining) and not grid.is_valid_feature_location(all_remaining[idx]):
                idx += 1
            
            if idx < len(all_remaining):
                random_feature = np.random.choice(feature_types)
                grid.add_feature(all_remaining[idx], random_feature)
                idx += 1
                features_placed += 1

    def find_opposite_corner(self, reference_corner, candidate_corners):
        """
        Trouve le coin le plus éloigné du coin de référence
        """
        ref_x, ref_y = reference_corner
        max_distance = 0
        opposite_corner = candidate_corners[0]
        
        for corner in candidate_corners:
            corner_x, corner_y = corner
            distance = abs(corner_x - ref_x) + abs(corner_y - ref_y)  # Distance Manhattan
            if distance > max_distance:
                max_distance = distance
                opposite_corner = corner
        
        return opposite_corner

    def add_features_complementary(self, grid, prop_features=0, feature_types=DEFAULT_FEATURE_TYPES, 
                                 min_pots=1, min_onion_dispensers=1, min_tomato_dispensers=0, 
                                 min_dish_dispensers=1, min_serving_locations=1):
        """
        Ajoute des fonctionnalités avec accès exclusif aléatoire pour chaque joueur dans un layout complémentaire
        Chaque joueur aura un accès exclusif à certains assets selon une distribution aléatoire
        """
        valid_locations = grid.valid_feature_locations()
        np.random.shuffle(valid_locations)
        
        # Séparer les emplacements par côté
        width = grid.shape[0]
        height = grid.shape[1]
        
        if width >= height:
            # Mur vertical
            wall_x = width // 2
            left_locations = [(x, y) for x, y in valid_locations if x < wall_x]
            right_locations = [(x, y) for x, y in valid_locations if x > wall_x]
        else:
            # Mur horizontal
            wall_y = height // 2
            left_locations = [(x, y) for x, y in valid_locations if y < wall_y]
            right_locations = [(x, y) for x, y in valid_locations if y > wall_y]
        
        # Distribuer les assets de manière exclusive aléatoire
        # Chaque joueur aura un accès exclusif à certains types d'assets
        
        # Assets disponibles à distribuer exclusivement
        exclusive_assets = []
        shared_assets = []
        
        # Ajouter les distributeurs d'ingrédients pour distribution exclusive
        for _ in range(min_onion_dispensers):
            exclusive_assets.append(ONION_DISPENSER)
        for _ in range(min_tomato_dispensers):
            exclusive_assets.append(TOMATO_DISPENSER)
        for _ in range(min_dish_dispensers):
            exclusive_assets.append(DISH_DISPENSER)
        
        # Les casseroles et zones de service restent partagées (une de chaque côté minimum)
        for _ in range(min_pots):
            shared_assets.append(POT)
        for _ in range(min_serving_locations):
            shared_assets.append(SERVING_LOC)
        
        # Mélanger les assets exclusifs pour une distribution aléatoire
        np.random.shuffle(exclusive_assets)
        
        # Distribution aléatoire des assets exclusifs
        left_exclusive = []
        right_exclusive = []
        
        for i, asset in enumerate(exclusive_assets):
            if i % 2 == 0:
                left_exclusive.append(asset)
            else:
                right_exclusive.append(asset)
        
        # Optionnel: redistribution aléatoire pour plus de variété
        if len(exclusive_assets) > 2:
            # Parfois donner plus d'assets à un côté de manière aléatoire
            if np.random.random() < 0.3:  # 30% de chance de redistribution
                # Transférer 1 asset aléatoirement
                if left_exclusive and np.random.random() < 0.5:
                    asset_to_move = left_exclusive.pop()
                    right_exclusive.append(asset_to_move)
                elif right_exclusive:
                    asset_to_move = right_exclusive.pop()
                    left_exclusive.append(asset_to_move)
        
        # Placer les assets exclusifs
        left_idx = 0
        right_idx = 0
        
        # Côté gauche/haut - assets exclusifs
        for asset in left_exclusive:
            if left_idx < len(left_locations):
                grid.add_feature(left_locations[left_idx], asset)
                left_idx += 1
        
        # Côté droit/bas - assets exclusifs
        for asset in right_exclusive:
            if right_idx < len(right_locations):
                grid.add_feature(right_locations[right_idx], asset)
                right_idx += 1
        
        # Placer les assets partagés (alternativement)
        for i, asset in enumerate(shared_assets):
            if i % 2 == 0 and left_idx < len(left_locations):
                # Placer du côté gauche/haut
                grid.add_feature(left_locations[left_idx], asset)
                left_idx += 1
            elif right_idx < len(right_locations):
                # Placer du côté droit/bas
                grid.add_feature(right_locations[right_idx], asset)
                right_idx += 1
            elif left_idx < len(left_locations):
                # Si plus d'emplacements à droite, utiliser la gauche
                grid.add_feature(left_locations[left_idx], asset)
                left_idx += 1
        
        # Ajouter des fonctionnalités aléatoires selon la proportion
        all_remaining = left_locations[left_idx:] + right_locations[right_idx:]
        features_placed = left_idx + right_idx
        
        for loc in all_remaining:
            current_prop = features_placed / len(valid_locations)
            if current_prop >= prop_features:
                break
            
            random_feature = np.random.choice(feature_types)
            grid.add_feature(loc, random_feature)
            features_placed += 1
        
        # Log de la distribution pour debug
        print(f"🎯 Distribution complémentaire:")
        print(f"   Côté gauche/haut exclusif: {[f.__name__ if hasattr(f, '__name__') else f for f in left_exclusive]}")
        print(f"   Côté droit/bas exclusif: {[f.__name__ if hasattr(f, '__name__') else f for f in right_exclusive]}")
        print(f"   Assets partagés: {[f.__name__ if hasattr(f, '__name__') else f for f in shared_assets]}")

    def get_complementary_starting_positions(self, grid):
        """
        Place les joueurs dans des zones séparées pour un layout complémentaire
        """
        # Identifier les deux zones
        width = grid.shape[0]
        height = grid.shape[1]
        
        if width >= height:
            # Mur vertical
            wall_x = width // 2
            # Joueur 1 à gauche, joueur 2 à droite
            pos0 = self.get_random_empty_location_in_zone(grid, 0, wall_x, 0, height)
            pos1 = self.get_random_empty_location_in_zone(grid, wall_x + 1, width, 0, height)
        else:
            # Mur horizontal
            wall_y = height // 2
            # Joueur 1 en haut, joueur 2 en bas
            pos0 = self.get_random_empty_location_in_zone(grid, 0, width, 0, wall_y)
            pos1 = self.get_random_empty_location_in_zone(grid, 0, width, wall_y + 1, height)
        
        return pos0, pos1

    def get_random_empty_location_in_zone(self, grid, min_x, max_x, min_y, max_y):
        """
        Trouve une position vide aléatoire dans une zone spécifique
        """
        attempts = 0
        while attempts < 1000:  # Éviter les boucles infinies
            x = np.random.randint(min_x, max_x)
            y = np.random.randint(min_y, max_y)
            loc = (x, y)
            if grid.location_is_empty(loc):
                return loc
            attempts += 1
        
        # Si aucune position vide trouvée, retourner le centre de la zone
        return ((min_x + max_x) // 2, (min_y + max_y) // 2)

    def make_fringe_expansion_layout(self, shape, prop_empty=0.1):
        grid = Grid(shape)
        self.dig_space_with_fringe_expansion(grid, prop_empty)
        self.add_features(grid)
        # print(grid)

    def dig_space_with_fringe_expansion(self, grid, prop_empty=0.1):
        starting_location = grid.get_random_interior_location()
        fringe = Fringe(grid)
        fringe.add(starting_location)

        while grid.proportion_empty() < prop_empty:
            curr_location = fringe.pop()
            grid.dig(curr_location)

            for location in grid.get_near_locations(curr_location):
                if grid.is_valid_dig_location(location):
                    fringe.add(location)

    def add_features(self, grid, prop_features=0, feature_types=DEFAULT_FEATURE_TYPES, 
                     min_pots=1, min_onion_dispensers=1, min_tomato_dispensers=0, 
                     min_dish_dispensers=1, min_serving_locations=1):
        """
        Places features according to minimum requirements and then adds random features 
        until prop_features of valid locations are filled
        """

        valid_locations = grid.valid_feature_locations()    # Emplacements valides
        np.random.shuffle(valid_locations)  # Mélange aléatoire
        
        # Dictionnaire pour mapper les types aux nombres minimum requis
        min_requirements = {
            POT: min_pots,
            ONION_DISPENSER: min_onion_dispensers,
            TOMATO_DISPENSER: min_tomato_dispensers,
            DISH_DISPENSER: min_dish_dispensers,
            SERVING_LOC: min_serving_locations
        }
        
        # Vérifier qu'il y a assez d'emplacements pour satisfaire les exigences minimales
        total_min_required = sum(min_requirements.values())
        assert len(valid_locations) >= total_min_required, f"Pas assez d'emplacements valides ({len(valid_locations)}) pour satisfaire les exigences minimales ({total_min_required})"

        num_features_placed = 0
        location_idx = 0
        
        # Phase 1: Placer le nombre minimum requis de chaque type
        for feature_type in [POT, ONION_DISPENSER, TOMATO_DISPENSER, DISH_DISPENSER, SERVING_LOC]:
            min_count = min_requirements.get(feature_type, 0)
            for _ in range(min_count):
                if location_idx < len(valid_locations):
                    grid.add_feature(valid_locations[location_idx], feature_type)
                    location_idx += 1
                    num_features_placed += 1
        
        # Phase 2: Ajouter des fonctionnalités aléatoires selon la proportion demandée
        while location_idx < len(valid_locations):
            current_prop = num_features_placed / len(valid_locations)
            if current_prop >= prop_features:
                break
            
            # Choisir un type aléatoire parmi les types disponibles
            random_feature = np.random.choice(feature_types)
            grid.add_feature(valid_locations[location_idx], random_feature)
            location_idx += 1
            num_features_placed += 1

    def get_random_starting_positions(self, grid, divider_x=None):
        pos0 = grid.get_random_empty_location()
        pos1 = grid.get_random_empty_location()
        # NOTE: Assuming more than 1 empty location, hacky code
        while pos0 == pos1:
            pos0 = grid.get_random_empty_location()
        return pos0, pos1


class Grid(object):

    def __init__(self, shape):
        # Matrice numpy remplie de comptoirs (code 1)
        assert len(shape) == 2, "Grid must be 2 dimensional"
        grid = (np.ones(shape) * TYPE_TO_CODE[COUNTER]).astype(int)
        self.mtx = grid
        self.shape = np.array(shape)
        self.width = shape[0]
        self.height = shape[1]

    @staticmethod
    def from_mdp(mdp):
        terrain_matrix = np.array(mdp.terrain_mtx)
        mdp_grid = Grid((terrain_matrix.shape[1], terrain_matrix.shape[0]))
        for y in range(terrain_matrix.shape[0]):
            for x in range(terrain_matrix.shape[1]):
                feature = terrain_matrix[y][x]
                mdp_grid.mtx[x][y] = TYPE_TO_CODE[feature]
        return mdp_grid

    def terrain_at_loc(self, location):
        x, y = location
        return self.mtx[x][y]

    def dig(self, location):
        assert self.is_valid_dig_location(location)
        self.change_location(location, EMPTY)

    def add_feature(self, location, feature_string):
        assert self.is_valid_feature_location(location)
        self.change_location(location, feature_string)

    def change_location(self, location, feature_string):
        x, y = location
        self.mtx[x][y] = TYPE_TO_CODE[feature_string]

    def proportion_empty(self):
        flattened_grid = self.mtx.flatten()
        # Exclut les bords (murs obligatoires)
        num_eligible = len(flattened_grid) - 2 * sum(self.shape) + 4
        num_empty = sum([1 for x in flattened_grid if x == TYPE_TO_CODE[EMPTY]])
        return float(num_empty) / num_eligible

    def get_near_locations(self, location):
        """Get neighbouring locations to the passed in location"""
        near_locations = []
        for d in Direction.ALL_DIRECTIONS:
            new_location = Action.move_in_direction(location, d)
            if self.is_in_bounds(new_location):
                near_locations.append(new_location)
        return near_locations

    def is_in_bounds(self, location):
        x, y = location
        return x >= 0 and y >= 0 and x < self.shape[0] and y < self.shape[1]

    def is_valid_dig_location(self, location):
        x, y = location

        # If already empty
        # Ne peut pas creuser si déjà vide
        if self.location_is_empty(location):
            return False

        # If one of the edges of the map, or outside the map
        # Ne peut pas creuser sur les bords (garde les murs extérieurs)
        if x <= 0 or y <= 0 or x >= self.shape[0] - 1 or y >= self.shape[1] - 1:
            return False
        return True

    def valid_feature_locations(self):
        valid_locations = []
        for x in range(self.shape[0]):
            for y in range(self.shape[1]):
                location = (x, y)
                if self.is_valid_feature_location(location):
                    valid_locations.append(location)
        return np.array(valid_locations)

    def is_valid_feature_location(self, location):
        x, y = location

        # If is empty or has a feature on it
        # Doit être un comptoir
        if not self.mtx[x][y] == TYPE_TO_CODE[COUNTER]:
            return False

        # If outside the map
        if not self.is_in_bounds(location):
            return False

        # If location is next to at least one empty square
        # Doit être adjacent à au moins un espace vide
        if any([loc for loc in self.get_near_locations(location) if CODE_TO_TYPE[self.terrain_at_loc(loc)] == EMPTY]):
            return True
        else:
            return False

    def location_is_empty(self, location):
        x, y = location
        return self.mtx[x][y] == TYPE_TO_CODE[EMPTY]

    def get_random_interior_location(self):
        rand_x = np.random.randint(low=1, high=self.shape[0] - 1)
        rand_y = np.random.randint(low=1, high=self.shape[1] - 1)
        return rand_x, rand_y

    def get_random_empty_location(self):
        is_empty = False
        while not is_empty:
            loc = self.get_random_interior_location()
            is_empty = self.location_is_empty(loc)
        return loc

    def convert_to_string(self):
        rows = []
        for y in range(self.shape[1]):
            column = []
            for x in range(self.shape[0]):
                column.append(CODE_TO_TYPE[self.mtx[x][y]])
            rows.append(column)
        string_grid = np.array(rows)
        assert np.array_equal(string_grid.T.shape, self.shape), "{} vs {}".format(string_grid.shape, self.shape)
        return string_grid

    def __repr__(self):
        s = ""
        for y in range(self.shape[1]):
            for x in range(self.shape[0]):
                s += CODE_TO_TYPE[self.mtx[x][y]]
                s += " "
            s += "\n"
        return s


class Fringe(object):

    def __init__(self, grid):
        self.fringe_list = []   # Liste des emplacements de frange
        self.distribution = []  # Distribution de probabilités
        self.grid = grid

    def add(self, item):
        if item not in self.fringe_list:
            self.fringe_list.append(item)
            self.update_probs() # Recalcule les probabilités

    def pop(self):
        # Sélection probabiliste
        assert len(self.fringe_list) > 0
        choice_idx = np.random.choice(len(self.fringe_list), p=self.distribution)
        removed_pos = self.fringe_list.pop(choice_idx)
        self.update_probs()
        return removed_pos

    def update_probs(self):
        self.distribution = np.ones(len(self.fringe_list)) / len(self.fringe_list)


class DisjointSets(object):
    """A simple implementation of the Disjoint Sets data structure.

    Implements path compression but not union-by-rank.

    Taken from https://github.com/HumanCompatibleAI/planner-inference
    """

    def __init__(self, elements):
        self.num_elements = len(elements)
        self.num_sets = len(elements)
        # Chaque élément est son propre parent
        self.parents = {element: element for element in elements}

    def is_connected(self):
        return self.num_sets == 1

    def get_num_elements(self):
        return self.num_elements

    def contains(self, element):
        return element in self.parents

    def add_singleton(self, element):
        assert not self.contains(element)
        self.num_elements += 1
        self.num_sets += 1
        self.parents[element] = element

    def find(self, element):
        # Compression de chemin pour optimisation
        parent = self.parents[element]
        if element == parent:
            return parent

        result = self.find(parent)
        self.parents[element] = result  # Compression
        return result

    def union(self, e1, e2):
        # Fusionne deux ensembles
        p1, p2 = map(self.find, (e1, e2))
        if p1 != p2:
            self.num_sets -= 1
            self.parents[p1] = p2


def main():
    """
    Fonction principale pour générer différents types de layouts avec paramètres configurables.
    Crée des layouts dans des dossiers séparés selon leur type.
    """
    
    # Configuration des layouts symétriques
    symmetric_count = 0
    symmetric_width = 7
    symmetric_height = 7
    symmetric_prop_empty = 0.95
    symmetric_min_pots = 1
    symmetric_min_onion = 1
    symmetric_min_tomato = 1
    symmetric_min_dish = 1
    symmetric_min_serving = 1
    
    # Configuration des layouts complémentaires
    complementary_count = 0
    complementary_width = 7
    complementary_height = 7
    complementary_prop_empty = 0.85
    complementary_min_pots = 1
    complementary_min_onion = 1
    complementary_min_tomato = 1
    complementary_min_dish = 1
    complementary_min_serving = 1
    
    # Configuration des layouts symétriques complexes
    complex_count = 200
    complex_width = 7
    complex_height = 7
    complex_prop_empty = 0.60
    complex_min_pots = 1
    complex_min_onion = 1
    complex_min_tomato = 1
    complex_min_dish = 1
    complex_min_serving = 1
    
    output_base_dir = "./overcooked_ai_py/data/layouts/generation_cesar"
    
    configs = {
        "symmetric": {
            "count": symmetric_count,
            "inner_shape": (symmetric_width, symmetric_height),
            "prop_empty": symmetric_prop_empty,
            "layout_type": "symetrique",
            "complexity": False,
            "folder": "symmetric",
            "min_pots": symmetric_min_pots,
            "min_onion_dispensers": symmetric_min_onion,
            "min_tomato_dispensers": symmetric_min_tomato,
            "min_dish_dispensers": symmetric_min_dish,
            "min_serving_locations": symmetric_min_serving
        },
        "complementary": {
            "count": complementary_count,
            "inner_shape": (complementary_width, complementary_height),
            "prop_empty": complementary_prop_empty,
            "layout_type": "complementaire",
            "complexity": False,
            "folder": "complementary",
            "min_pots": complementary_min_pots,
            "min_onion_dispensers": complementary_min_onion,
            "min_tomato_dispensers": complementary_min_tomato,
            "min_dish_dispensers": complementary_min_dish,
            "min_serving_locations": complementary_min_serving
        },
        "symmetric_complex": {
            "count": complex_count,
            "inner_shape": (complex_width, complex_height),
            "prop_empty": complex_prop_empty,
            "layout_type": "symetrique",
            "complexity": True,
            "folder": "symmetric_complex",
            "min_pots": complex_min_pots,
            "min_onion_dispensers": complex_min_onion,
            "min_tomato_dispensers": complex_min_tomato,
            "min_dish_dispensers": complex_min_dish,
            "min_serving_locations": complex_min_serving
        }
    }
    
    if not os.path.exists(output_base_dir):
        os.makedirs(output_base_dir)
    
    for layout_type, config in configs.items():
        if config["count"] <= 0:
            continue
            
        layout_output_dir = os.path.join(output_base_dir, config["folder"])
        if not os.path.exists(layout_output_dir):
            os.makedirs(layout_output_dir)
        
        mdp_gen_params = {
            "inner_shape": config["inner_shape"],
            "prop_empty": config["prop_empty"],
            "prop_feats": 0.1,
            "start_all_orders": [{"ingredients": ["onion", "onion", "onion"]}],
            "feature_types": DEFAULT_FEATURE_TYPES,
            "min_pots": config["min_pots"],
            "min_onion_dispensers": config["min_onion_dispensers"],
            "min_tomato_dispensers": config["min_tomato_dispensers"],
            "min_dish_dispensers": config["min_dish_dispensers"],
            "min_serving_locations": config["min_serving_locations"],
            "num_layouts_to_generate": config["count"],
            "recipe_values": [20],
            "recipe_times": [20],
            "display": False,
            "intentions_sharing": True,
            "use_recipe_file": True,
            "recipe_file_path": "ensemble_recettes.json",
            "recipe_sampling": "without_replacement",
            "layout_type": config["layout_type"],
            "complexity": config["complexity"]
        }
        
        for i in range(config["count"]):
            mdp_param_generator = MDPParamsGenerator(lambda _: mdp_gen_params)
            layout_generator = LayoutGenerator(mdp_param_generator, config["inner_shape"])
            layout = layout_generator.make_new_layout(mdp_gen_params)
            
            filename = f"layout_{config['folder']}_{i}.layout"
            filepath = os.path.join(layout_output_dir, filename)
            layout.to_layout_file(filepath)


if __name__ == "__main__":
    main()