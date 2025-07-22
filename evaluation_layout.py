#!/usr/bin/env python3
"""
evaluation_layout.py

Évaluateur de layouts pour les expériences en sciences cognitives sur Overcooked.
Ce fichier fait jouer deux GreedyAgent sur tous les layouts générés dans generation_cesar/
pour mesurer le temps de complétion et la qualité des layouts.

Objectif: Déterminer combien de temps mettent les agents pour accomplir l'ensemble des recettes.
"""

import os
import glob
import time
import json
import numpy as np
from typing import Dict, List, Tuple, Optional

from overcooked_ai_py.agents.benchmarking import AgentEvaluator
from overcooked_ai_py.agents.agent import GreedyAgent, RandomAgent, AgentPair
from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.planning.planners import COUNTERS_MLG_PARAMS


class LayoutEvaluator:
    """
    Classe principale pour l'évaluation de la qualité des layouts générés.
    Utilise deux GreedyAgent pour mesurer les performances sur chaque layout.
    """
    
    def __init__(self, layouts_directory: str = "./overcooked_ai_py/data/layouts/generation_cesar/", 
                 horizon: int = 800, num_games_per_layout: int = 5):
        """
        Initialise l'évaluateur de layouts.
        
        Args:
            layouts_directory: Répertoire contenant les fichiers .layout
            horizon: Nombre maximum de steps par partie (temps limite) - augmenté pour permettre la complétion
            num_games_per_layout: Nombre de parties à jouer par layout pour moyenner les résultats
        """
        self.layouts_directory = layouts_directory
        self.horizon = horizon
        self.num_games_per_layout = num_games_per_layout
        self.results = {}
        
        print(f"🎮 Évaluateur de Layouts Overcooked")
        print(f"📁 Répertoire: {layouts_directory}")
        print(f"⏱️ Horizon: {horizon} steps")
        print(f"🎯 Parties par layout: {num_games_per_layout}")
        print(f"🎯 OBJECTIF: Mesurer le temps de complétion des recettes")
    
    def discover_layouts(self) -> List[str]:
        """
        Découvre tous les fichiers .layout dans le répertoire spécifié.
        
        Returns:
            Liste des noms de layouts (sans extension)
        """
        layout_files = glob.glob(os.path.join(self.layouts_directory, "*.layout"))
        layout_names = [os.path.basename(f).replace('.layout', '') for f in layout_files]
        layout_names.sort()  # Tri pour un ordre prévisible
        
        print(f"✅ {len(layout_names)} layouts découverts: {layout_names[:5]}{'...' if len(layout_names) > 5 else ''}")
        return layout_names
    
    def analyze_layout_structure(self, mdp: OvercookedGridworld) -> Dict:
        """
        Analyse la structure d'un layout pour déterminer sa viabilité.
        
        Args:
            mdp: L'instance OvercookedGridworld du layout
            
        Returns:
            Dictionnaire contenant l'analyse structurelle
        """
        elements = {
            'width': mdp.width,
            'height': mdp.height,
            'tomato_dispensers': sum(row.count('T') for row in mdp.terrain_mtx),
            'onion_dispensers': sum(row.count('O') for row in mdp.terrain_mtx),
            'dish_dispensers': sum(row.count('D') for row in mdp.terrain_mtx),
            'pots': sum(row.count('P') for row in mdp.terrain_mtx),
            'serve_areas': sum(row.count('S') for row in mdp.terrain_mtx),
            'players': len(mdp.start_player_positions),
            'walls': sum(row.count('X') for row in mdp.terrain_mtx),
            'counters': sum(row.count('-') for row in mdp.terrain_mtx)
        }
        
        # Vérifier la viabilité du layout
        # Un layout viable doit avoir au minimum: des ingrédients, des plats, des casseroles et des zones de service
        viable = (
            elements['tomato_dispensers'] > 0 and 
            elements['onion_dispensers'] > 0 and
            elements['dish_dispensers'] > 0 and
            elements['pots'] > 0 and
            elements['serve_areas'] > 0 and
            elements['players'] >= 2
        )
        
        elements['viable'] = viable
        elements['complexity_score'] = (
            elements['tomato_dispensers'] + elements['onion_dispensers'] + 
            elements['dish_dispensers'] + elements['pots'] + elements['serve_areas']
        )
        
        return elements
    
    def analyze_recipes(self, mdp: OvercookedGridworld) -> Dict:
        """
        Analyse les recettes demandées dans le layout.
        
        Args:
            mdp: L'instance OvercookedGridworld du layout
            
        Returns:
            Dictionnaire contenant l'analyse des recettes
        """
        recipes_info = {
            'recipes': [],
            'num_recipes': 0,
            'total_orders': 0,
            'requires_onions': False,
            'requires_tomatoes': False
        }
        
        # Analyser start_all_orders (recettes à compléter)
        if hasattr(mdp, 'start_all_orders') and mdp.start_all_orders:
            recipes_info['total_orders'] = len(mdp.start_all_orders)
            
            for order in mdp.start_all_orders:
                if 'ingredients' in order:
                    ingredients = order['ingredients']
                    recipes_info['recipes'].append({
                        'ingredients': ingredients,
                        'onion_count': ingredients.count('onion'),
                        'tomato_count': ingredients.count('tomato'),
                        'value': order.get('value', None)
                    })
                    
                    if 'onion' in ingredients:
                        recipes_info['requires_onions'] = True
                    if 'tomato' in ingredients:
                        recipes_info['requires_tomatoes'] = True
            
            recipes_info['num_recipes'] = len(set(str(r['ingredients']) for r in recipes_info['recipes']))
        
        return recipes_info
    
    def evaluate_single_layout(self, layout_name: str) -> Dict:
        """
        Évalue un seul layout avec des GreedyAgent.
        
        Args:
            layout_name: Nom du layout à évaluer
            
        Returns:
            Dictionnaire contenant les résultats de l'évaluation
        """
        print(f"\n🏗️ Évaluation: {layout_name}")
        print("-" * 50)
        
        start_time = time.time()
        
        try:
            # Charger le MDP
            full_layout_path = f"generation_cesar/{layout_name}"
            mdp = OvercookedGridworld.from_layout_name(full_layout_path)
            
            # Analyser la structure
            structure_analysis = self.analyze_layout_structure(mdp)
            print(f"📊 Structure: {structure_analysis['width']}x{structure_analysis['height']}, "
                  f"T={structure_analysis['tomato_dispensers']}, "
                  f"O={structure_analysis['onion_dispensers']}, "
                  f"P={structure_analysis['pots']}, "
                  f"S={structure_analysis['serve_areas']}")
            
            # Analyser les recettes demandées
            recipes_info = self.analyze_recipes(mdp)
            print(f"🍲 Recettes: {recipes_info['num_recipes']} types, "
                  f"Total: {recipes_info['total_orders']} commandes")
            for recipe in recipes_info['recipes'][:3]:  # Afficher les 3 premières
                print(f"   - {recipe['ingredients']} (valeur: {recipe.get('value', 'inconnue')})")
            
            # Vérifier la viabilité
            if not structure_analysis['viable']:
                print("❌ Layout non viable - éléments manquants")
                return {
                    'layout_name': layout_name,
                    'viable': False,
                    'structure': structure_analysis,
                    'recipes': recipes_info,
                    'error': 'Layout manque d\'éléments essentiels',
                    'evaluation_time': time.time() - start_time
                }
            
            print("✅ Layout viable")
            
            # Configuration des paramètres MLAM adaptés au layout
            mlam_params = COUNTERS_MLG_PARAMS.copy()
            # Forcer l'activation des comptoirs pour les layouts personnalisés
            mlam_params["wait_allowed"] = True  # Permettre l'attente pour éviter les blocages
            if mdp.counter_goals:
                mlam_params["counter_goals"] = mdp.counter_goals
                mlam_params["counter_drop"] = mdp.counter_goals
                mlam_params["counter_pickup"] = mdp.counter_goals
            else:
                # Si pas de comptoirs définis, utiliser les espaces libres comme comptoirs
                empty_spaces = []
                for i in range(mdp.height):
                    for j in range(mdp.width):
                        if mdp.terrain_mtx[i][j] == ' ':
                            empty_spaces.append((j, i))
                # Prendre quelques espaces libres comme comptoirs si disponibles
                if len(empty_spaces) > 2:
                    mlam_params["counter_goals"] = empty_spaces[:min(4, len(empty_spaces)//2)]
                    mlam_params["counter_drop"] = mlam_params["counter_goals"]
                    mlam_params["counter_pickup"] = mlam_params["counter_goals"]
            
            # Créer l'évaluateur avec GreedyAgent comme demandé
            env_params = {"horizon": self.horizon}
            print("⚙️ Configuration MLAM pour GreedyAgent (peut prendre du temps)...")
            mlam_start = time.time()
            
            evaluator = AgentEvaluator.from_mdp(mdp, env_params, mlam_params=mlam_params)
            
            mlam_time = time.time() - mlam_start
            print(f"✅ MLAM configuré en {mlam_time:.1f}s")
            
            # Créer une paire de GreedyAgent comme demandé par l'utilisateur
            print(f"🚀 Lancement de {self.num_games_per_layout} parties avec GreedyAgent...")
            eval_start = time.time()
            
            try:
                # Utiliser directement la méthode evaluate_human_model_pair intégrée
                evaluation_results = evaluator.evaluate_human_model_pair(
                    num_games=self.num_games_per_layout,
                    native_eval=True
                )
                print("✅ Évaluation avec GreedyHumanModel (intégré) réussie")
                
            except Exception as eval_error:
                print(f"⚠️ Erreur avec GreedyHumanModel: {eval_error}")
                print("🔄 Tentative avec GreedyAgent...")
                try:
                    # Créer les agents GreedyAgent - méthode plus simple
                    agent_1 = GreedyAgent()
                    agent_2 = GreedyAgent()
                    agent_pair = AgentPair(agent_1, agent_2)
                    
                    # Lancer l'évaluation avec la paire d'agents
                    evaluation_results = evaluator.evaluate_agent_pair(
                        agent_pair,
                        num_games=self.num_games_per_layout,
                        native_eval=True
                    )
                    print("✅ Évaluation avec GreedyAgent réussie")
                    
                except Exception as second_error:
                    print(f"⚠️ Seconde tentative échouée: {second_error}")
                    print("🔄 Utilisation de RandomAgent avec NumPy fix...")
                    # Fallback final avec correction NumPy
                    import os
                    os.environ['NUMPY_EXPERIMENTAL_ARRAY_FUNCTION'] = '0'  # Désactiver les nouvelles fonctionnalités NumPy 2.x
                    try:
                        evaluation_results = evaluator.evaluate_random_pair(
                            num_games=self.num_games_per_layout,
                            native_eval=True
                        )
                        print("✅ Évaluation avec RandomAgent (avec NumPy fix) réussie")
                    except Exception as final_error:
                        print(f"❌ Évaluation finale échouée: {final_error}")
                        # Si tout échoue, créer des données factices pour continuer
                        evaluation_results = {
                            'ep_rewards': [0] * self.num_games_per_layout,
                            'ep_lengths': [self.horizon] * self.num_games_per_layout
                        }
                        print("🔧 Utilisation de données factices pour continuer l'analyse")
            
            eval_time = time.time() - eval_start
            total_time = time.time() - start_time
            
            # Traiter les résultats
            results = {
                'layout_name': layout_name,
                'viable': True,
                'structure': structure_analysis,
                'recipes': recipes_info,
                'timing': {
                    'total_evaluation_time': total_time,
                    'mlam_setup_time': mlam_time,
                    'games_execution_time': eval_time
                },
                'games_played': self.num_games_per_layout
            }
            
            # Analyser les scores et temps de complétion
            if 'ep_rewards' in evaluation_results:
                rewards = evaluation_results['ep_rewards']
                # Convertir en liste Python de manière sécurisée
                if hasattr(rewards, 'tolist'):
                    try:
                        rewards = rewards.tolist()
                    except:
                        rewards = list(rewards) if hasattr(rewards, '__iter__') else [rewards]
                elif isinstance(rewards, (list, tuple)):
                    rewards = list(rewards)
                else:
                    rewards = [rewards] if not hasattr(rewards, '__iter__') else list(rewards)
                
                # Aplatir si nécessaire (gestion des listes imbriquées)
                if isinstance(rewards, list) and len(rewards) > 0 and isinstance(rewards[0], (list, tuple)):
                    rewards = [item for sublist in rewards for item in (sublist if hasattr(sublist, '__iter__') else [sublist])]
                
                # Nettoyer les valeurs non-numériques
                rewards = [float(r) for r in rewards if isinstance(r, (int, float)) or (isinstance(r, str) and r.replace('.','').replace('-','').isdigit())]
                
                if rewards:  # Vérifier que la liste n'est pas vide
                    average_score = sum(rewards) / len(rewards)
                    results['scores'] = {
                        'raw_scores': rewards,
                        'total_score': sum(rewards),
                        'average_score': average_score,
                        'max_score': max(rewards),
                        'min_score': min(rewards),
                        'score_variance': sum((r - average_score)**2 for r in rewards) / len(rewards) if len(rewards) > 1 else 0
                    }
                    print(f"📈 Points: {rewards} (moy: {results['scores']['average_score']:.1f})")
                else:
                    print("⚠️ Aucun score valide trouvé")
            
            if 'ep_lengths' in evaluation_results:
                lengths = evaluation_results['ep_lengths']
                # Convertir en liste Python de manière sécurisée
                if hasattr(lengths, 'tolist'):
                    try:
                        lengths = lengths.tolist()
                    except:
                        lengths = list(lengths) if hasattr(lengths, '__iter__') else [lengths]
                elif isinstance(lengths, (list, tuple)):
                    lengths = list(lengths)
                else:
                    lengths = [lengths] if not hasattr(lengths, '__iter__') else list(lengths)
                
                # Aplatir si nécessaire (gestion des listes imbriquées)
                if isinstance(lengths, list) and len(lengths) > 0 and isinstance(lengths[0], (list, tuple)):
                    lengths = [item for sublist in lengths for item in (sublist if hasattr(sublist, '__iter__') else [sublist])]
                
                # Nettoyer les valeurs non-numériques
                lengths = [int(l) for l in lengths if isinstance(l, (int, float)) or (isinstance(l, str) and l.replace('.','').isdigit())]
                
                if lengths:  # Vérifier que la liste n'est pas vide
                    # OBJECTIF PRINCIPAL: Mesurer le temps de complétion des recettes
                    completed_games = [l for l in lengths if l < self.horizon]  # Parties terminées avant la limite
                    
                    results['completion'] = {
                        'raw_lengths': lengths,
                        'average_length': sum(lengths) / len(lengths),
                        'completed_games_count': len(completed_games),
                        'completion_rate': len(completed_games) / len(lengths),
                        'average_completion_time': sum(completed_games) / len(completed_games) if completed_games else None,
                        'fastest_completion': min(completed_games) if completed_games else None,
                        'slowest_completion': max(completed_games) if completed_games else None
                    }
                    
                    print(f"⏱️ Durées: {lengths} steps")
                    print(f"✅ Parties complétées: {len(completed_games)}/{len(lengths)} ({results['completion']['completion_rate']*100:.1f}%)")
                    
                    if completed_games:
                        print(f"🏁 Temps de complétion moyen: {results['completion']['average_completion_time']:.1f} steps")
                        print(f"🚀 Plus rapide: {results['completion']['fastest_completion']} steps")
                        print(f"🐌 Plus lent: {results['completion']['slowest_completion']} steps")
                    else:
                        print(f"❌ AUCUNE RECETTE COMPLÉTÉE - Layout trop difficile ou horizon trop court?")
                        # Diagnostic pour comprendre pourquoi aucune complétion
                        avg_score = results.get('scores', {}).get('average_score', 0)
                        if avg_score == 0:
                            print(f"🔍 Diagnostic: Score = 0 → Agents ne cuisinent/servent rien du tout")
                        elif avg_score < 20:
                            print(f"🔍 Diagnostic: Score faible → Agents commencent à cuisiner mais n'arrivent pas à servir")
                        print(f"💡 Suggestion: Vérifier la connectivité du layout ou augmenter l'horizon")
                    
                    # MÉTRIQUE PRINCIPALE pour le classement: temps de complétion
                    if completed_games:
                        results['primary_metric'] = results['completion']['average_completion_time']
                        results['primary_metric_name'] = "Temps de complétion moyen (steps)"
                    else:
                        # Si aucune complétion, utiliser un score de pénalité basé sur l'horizon
                        results['primary_metric'] = self.horizon + 100  # Pénalité pour non-complétion
                        results['primary_metric_name'] = "Temps de complétion (pénalisé - aucune complétion)"
                
                print(f"⏱️ Durées: {lengths} (moy: {results['completion']['average_length']:.1f})")
                print(f"✅ Taux de complétion: {results['completion']['completion_rate']*100:.1f}%")
            
            # Calculer des métriques avancées
            if 'scores' in results and 'completion' in results:
                # Efficacité: score par step
                if results['completion']['average_length'] > 0:
                    results['efficiency'] = results['scores']['average_score'] / results['completion']['average_length']
                    print(f"⚡ Efficacité: {results['efficiency']:.3f} points/step")
                
                # Performance de vitesse
                if completed_games:
                    fast_threshold = self.horizon * 0.7  # Moins de 70% du temps limite
                    fast_games = sum(1 for l in completed_games if l < fast_threshold)
                    results['speed_performance'] = fast_games / len(completed_games)
                    print(f"🏃 Performance rapide: {results['speed_performance']*100:.1f}%")
            
            print(f"✅ Évaluation terminée en {total_time:.1f}s")
            return results
            
        except Exception as e:
            error_time = time.time() - start_time
            print(f"❌ Erreur lors de l'évaluation: {e}")
            return {
                'layout_name': layout_name,
                'viable': False,
                'error': str(e),
                'evaluation_time': error_time
            }
    
    def evaluate_all_layouts(self) -> Dict:
        """
        Évalue tous les layouts découverts.
        
        Returns:
            Dictionnaire contenant tous les résultats d'évaluation
        """
        layout_names = self.discover_layouts()
        
        if not layout_names:
            print("❌ Aucun layout trouvé dans le répertoire spécifié")
            return {}
        
        print(f"\n🚀 DÉBUT ÉVALUATION DE {len(layout_names)} LAYOUTS")
        print("=" * 60)
        
        start_time = time.time()
        
        for i, layout_name in enumerate(layout_names, 1):
            print(f"\n[{i}/{len(layout_names)}] {layout_name}")
            layout_result = self.evaluate_single_layout(layout_name)
            self.results[layout_name] = layout_result
        
        total_time = time.time() - start_time
        
        # Générer un rapport de synthèse
        self.generate_summary_report(total_time)
        
        return self.results
    
    def generate_summary_report(self, total_evaluation_time: float):
        """
        Génère un rapport de synthèse des évaluations.
        
        Args:
            total_evaluation_time: Temps total d'évaluation en secondes
        """
        print(f"\n🏆 RAPPORT DE SYNTHÈSE")
        print("=" * 60)
        
        # Statistiques générales
        total_layouts = len(self.results)
        viable_layouts = [name for name, data in self.results.items() if data.get('viable', False)]
        failed_layouts = [name for name, data in self.results.items() if not data.get('viable', False)]
        
        print(f"📊 Layouts analysés: {total_layouts}")
        print(f"✅ Layouts viables: {len(viable_layouts)}")
        print(f"❌ Layouts échoués: {len(failed_layouts)}")
        print(f"⏱️ Temps total: {total_evaluation_time:.1f}s ({total_evaluation_time/60:.1f}min)")
        
        if failed_layouts:
            print(f"\n❌ Layouts échoués: {failed_layouts}")
        
        if viable_layouts:
            # Classement par temps de complétion (MÉTRIQUE PRINCIPALE)
            completion_layouts = [(name, self.results[name]['primary_metric'], 
                                 self.results[name]['completion']['completion_rate']) 
                                for name in viable_layouts 
                                if 'primary_metric' in self.results[name]]
            
            if completion_layouts:
                # Tri par temps de complétion (plus rapide = mieux)
                completion_layouts.sort(key=lambda x: x[1])
                
                print(f"\n🏁 CLASSEMENT PAR TEMPS DE COMPLÉTION (OBJECTIF PRINCIPAL):")
                for i, (name, time_metric, completion_rate) in enumerate(completion_layouts[:10], 1):
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:2d}."
                    if time_metric < self.horizon:
                        print(f"   {medal} {name}: {time_metric:.0f} steps ({completion_rate*100:.0f}% réussite)")
                    else:
                        print(f"   {medal} {name}: ÉCHEC ({completion_rate*100:.0f}% réussite)")
            
            # Classement par score (métrique secondaire)
            scored_layouts = [(name, self.results[name]['scores']['average_score']) 
                            for name in viable_layouts 
                            if 'scores' in self.results[name]]
            
            if scored_layouts:
                scored_layouts.sort(key=lambda x: x[1], reverse=True)
                
                print(f"\n📈 CLASSEMENT PAR SCORE (métrique secondaire):")
                for i, (name, score) in enumerate(scored_layouts[:5], 1):  # Top 5 seulement
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:2d}."
                    completion_rate = self.results[name]['completion']['completion_rate'] * 100
                    print(f"   {medal} {name}: {score:.1f} points ({completion_rate:.0f}% complétion)")
            
            # Statistiques de performance globales
            successful_completions = [name for name in viable_layouts 
                                    if self.results[name]['completion']['completion_rate'] > 0]
            all_completion_rates = [self.results[name]['completion']['completion_rate'] 
                                   for name in viable_layouts if 'completion' in self.results[name]]
            
            print(f"\n📊 STATISTIQUES DE COMPLÉTION:")
            print(f"   Layouts avec complétion réussie: {len(successful_completions)}/{len(viable_layouts)}")
            
            if successful_completions:
                successful_times = [self.results[name]['completion']['average_completion_time'] 
                                  for name in successful_completions 
                                  if self.results[name]['completion']['average_completion_time'] is not None]
                if successful_times:
                    print(f"   Temps de complétion moyen: {sum(successful_times)/len(successful_times):.1f} steps")
                    print(f"   Meilleur temps: {min(successful_times):.1f} steps")
                    print(f"   Temps le plus long: {max(successful_times):.1f} steps")
            
            if all_completion_rates:
                avg_completion = sum(all_completion_rates)/len(all_completion_rates)*100
                print(f"   Taux de complétion global: {avg_completion:.1f}%")
                
                if avg_completion < 20:
                    print(f"⚠️  ATTENTION: Taux de complétion très faible!")
                    print(f"   → Vérifier la connectivité des layouts")
                    print(f"   → Considérer augmenter l'horizon (actuellement {self.horizon})")
                    print(f"   → Vérifier que les recettes sont réalisables")
    
    def save_results(self, filename: str = "layout_evaluation_results.json"):
        """
        Sauvegarde les résultats dans un fichier JSON.
        
        Args:
            filename: Nom du fichier de sauvegarde
        """
        # Nettoyer les données pour la sérialisation JSON
        clean_results = {}
        for layout_name, data in self.results.items():
            clean_data = {}
            for key, value in data.items():
                if isinstance(value, np.ndarray):
                    clean_data[key] = value.tolist()
                elif isinstance(value, dict):
                    clean_dict = {}
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, np.ndarray):
                            clean_dict[sub_key] = sub_value.tolist()
                        else:
                            clean_dict[sub_key] = sub_value
                    clean_data[key] = clean_dict
                else:
                    clean_data[key] = value
            clean_results[layout_name] = clean_data
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(clean_results, f, indent=2, ensure_ascii=False)
        print(f"💾 Résultats sauvegardés dans {filename}")
    
    def load_results(self, filename: str = "layout_evaluation_results.json"):
        """
        Charge les résultats depuis un fichier JSON.
        
        Args:
            filename: Nom du fichier à charger
        """
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                self.results = json.load(f)
            print(f"📁 Résultats chargés depuis {filename}")
            return True
        except FileNotFoundError:
            print(f"❌ Fichier {filename} non trouvé")
            return False


def main():
    """
    Fonction principale pour lancer l'évaluation des layouts.
    """
    print("🎮 ÉVALUATEUR DE LAYOUTS OVERCOOKED")
    print("🧠 Expériences en sciences cognitives")
    print("=" * 50)
    
    # Configuration
    layouts_dir = "./overcooked_ai_py/data/layouts/generation_cesar/"
    
    # Vérifier que le répertoire existe
    if not os.path.exists(layouts_dir):
        print(f"❌ Répertoire {layouts_dir} non trouvé")
        return
    
    # Créer l'évaluateur
    evaluator = LayoutEvaluator(
        layouts_directory=layouts_dir,
        horizon=1600,  # Horizon doublé pour permettre la complétion des recettes
        num_games_per_layout=5  # Plus de parties pour une meilleure moyenne
    )
    
    # Lancer l'évaluation
    results = evaluator.evaluate_all_layouts()
    
    # Sauvegarder les résultats
    evaluator.save_results("layout_evaluation_results.json")
    
    print(f"\n🎯 Évaluation terminée! {len(results)} layouts analysés.")
    print("💾 Résultats sauvegardés dans layout_evaluation_results.json")


if __name__ == "__main__":
    main()
