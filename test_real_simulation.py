#!/usr/bin/env python3
"""
Test de simulation réelle GreedyAgent - Version simplifiée pour debugging
"""

import os
import sys
import re
import time
import numpy as np

# Ajouter le chemin vers overcooked_ai_py
sys.path.append('/home/cesar/python-projects/Overcooked-coop-voice/overcooked_ai_py')

from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld, Recipe
from overcooked_ai_py.mdp.overcooked_env import OvercookedEnv
from overcooked_ai_py.agents.agent import GreedyAgent, RandomAgent, AgentPair


def load_layout(layout_path):
    """Charge un layout César et retourne le MDP."""
    print(f"📥 Chargement: {layout_path}")
    
    try:
        # Lire le fichier
        with open(layout_path, 'r') as f:
            content = f.read()
        
        # Extraire la grille avec regex
        grid_match = re.search(r'"""(.+?)"""', content, re.DOTALL)
        if not grid_match:
            print("❌ Grille non trouvée")
            return None
        
        grid_str = grid_match.group(1).strip()
        
        # Nettoyer les lignes
        grid_lines = []
        for line in grid_str.split('\n'):
            clean_line = line.strip().replace('\t', '')
            if clean_line:
                grid_lines.append(clean_line)
        
        clean_grid = '\n'.join(grid_lines)
        print(f"🔲 Grille ({len(grid_lines)} lignes):")
        for i, line in enumerate(grid_lines):
            print(f"   {i}: '{line}'")
        
        # Vérifier et corriger les bordures
        print("🔧 Vérification des bordures...")
        corrected_lines = []
        max_width = max(len(line) for line in grid_lines)
        
        for i, line in enumerate(grid_lines):
            # Assurer que toutes les lignes ont la même largeur
            padded_line = line.ljust(max_width)
            
            # Première et dernière ligne : remplacer tout par X sauf les éléments spéciaux
            if i == 0 or i == len(grid_lines) - 1:
                corrected_line = ""
                for char in padded_line:
                    if char in ['S', 'P', 'O', 'D', 'T']:  # Éléments spéciaux à préserver
                        corrected_line += char
                    else:
                        corrected_line += 'X'
            else:
                # Lignes du milieu : assurer bordures gauche/droite sont X
                corrected_line = padded_line
                if corrected_line[0] not in ['X']:
                    corrected_line = 'X' + corrected_line[1:]
                if corrected_line[-1] not in ['X']:
                    corrected_line = corrected_line[:-1] + 'X'
            
            corrected_lines.append(corrected_line)
        
        corrected_grid = '\n'.join(corrected_lines)
        
        print(f"🔧 Grille corrigée:")
        for i, line in enumerate(corrected_lines):
            print(f"   {i}: '{line}'")
        
        # Créer le MDP
        mdp = OvercookedGridworld.from_grid(corrected_grid)
        print(f"✅ MDP créé: {mdp.width}x{mdp.height}")
        
        # Ajouter commande 3 oignons
        if 'onion' in content:
            recipe = Recipe(['onion', 'onion', 'onion'])
            mdp.start_all_orders = [recipe]
            print("✅ Commande 3 oignons ajoutée")
        
        return mdp
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None


def test_real_simulation(mdp, num_games=2):
    """Test de simulation réelle avec GreedyAgent."""
    print(f"\n🎮 Test simulation réelle - {num_games} parties")
    
    try:
        # Créer les agents
        print("🤖 Création GreedyAgent...")
        try:
            agent1 = GreedyAgent()
            agent2 = GreedyAgent()
            agent_pair = AgentPair(agent1, agent2)
            agent_type = "GreedyAgent"
            print("✅ GreedyAgent créés")
        except Exception as e:
            print(f"⚠️ GreedyAgent échoué: {e}")
            print("🔄 Fallback RandomAgent...")
            agent1 = RandomAgent()
            agent2 = RandomAgent()
            agent_pair = AgentPair(agent1, agent2)
            agent_type = "RandomAgent"
            print("✅ RandomAgent créés")
        
        # Simuler les parties
        results = []
        for game in range(num_games):
            print(f"\n   🎯 Partie {game + 1}")
            
            try:
                # Créer environnement
                env = OvercookedEnv.from_mdp(mdp, horizon=500)
                
                # Configurer agents
                agent_pair.set_mdp(mdp)
                
                # Variables de suivi
                start_time = time.time()
                total_score = 0
                orders_completed = 0
                initial_orders = len(mdp.start_all_orders) if hasattr(mdp, 'start_all_orders') and mdp.start_all_orders else 1
                
                print(f"      📋 Commandes à compléter: {initial_orders}")
                
                # État initial
                state = env.reset()
                
                # Simulation step by step
                for step in range(500):
                    # Actions des agents
                    joint_action = agent_pair.joint_action(state)
                    
                    # Exécuter dans l'environnement
                    next_state, reward, done, info = env.step(joint_action)
                    
                    total_score += reward
                    if reward > 0:
                        orders_completed += 1
                        print(f"         ✅ Commande {orders_completed}/{initial_orders} complétée!")
                    
                    # Vérifier complétion
                    if orders_completed >= initial_orders:
                        print(f"         🏁 TOUTES COMPLÉTÉES en {step + 1} steps!")
                        break
                    
                    if done:
                        print(f"         ⏰ Terminé par environnement à {step + 1} steps")
                        break
                    
                    state = next_state
                
                end_time = time.time()
                
                result = {
                    'game': game + 1,
                    'steps': step + 1,
                    'score': total_score,
                    'completed': orders_completed >= initial_orders,
                    'orders_completed': orders_completed,
                    'total_orders': initial_orders,
                    'real_time': end_time - start_time,
                    'agent_type': agent_type
                }
                
                results.append(result)
                
                print(f"      📊 {step + 1} steps, score: {total_score}, "
                      f"complétion: {orders_completed}/{initial_orders}, "
                      f"temps: {end_time - start_time:.2f}s")
                
            except Exception as e:
                print(f"      ❌ Erreur partie {game + 1}: {e}")
                continue
        
        # Statistiques finales
        if results:
            print(f"\n📈 RÉSULTATS FINAUX ({len(results)} parties réussies):")
            
            times = [r['steps'] for r in results]
            scores = [r['score'] for r in results]
            completions = [r['completed'] for r in results]
            real_times = [r['real_time'] for r in results]
            
            print(f"   🕒 Temps moyen: {np.mean(times):.1f} ± {np.std(times):.1f} steps")
            print(f"   🎯 Score moyen: {np.mean(scores):.1f}")
            print(f"   ✅ Taux de complétion: {np.mean(completions)*100:.1f}%")
            print(f"   ⏱️ Temps réel moyen: {np.mean(real_times):.2f}s")
            print(f"   🤖 Type d'agent: {results[0]['agent_type']}")
            
            for i, result in enumerate(results):
                print(f"      Partie {i+1}: {result['steps']} steps, score {result['score']}, "
                      f"complétion: {result['completed']}")
        
        return results
        
    except Exception as e:
        print(f"❌ Erreur simulation: {e}")
        return []


def main():
    """Test principal."""
    print("🎮 TEST SIMULATION RÉELLE - GREEDYAGENT")
    print("=" * 50)
    
    # Chemins des layouts
    layouts_dir = "/home/cesar/python-projects/Overcooked-coop-voice/overcooked_ai_py/data/layouts/generation_cesar"
    
    for layout_file in ["layout_cesar_0.layout", "layout_cesar_1.layout"]:
        layout_path = os.path.join(layouts_dir, layout_file)
        
        print(f"\n🎯 TEST: {layout_file}")
        print("-" * 30)
        
        # Charger le layout
        mdp = load_layout(layout_path)
        if not mdp:
            print("❌ Impossible de charger le layout")
            continue
        
        # Tester la simulation
        results = test_real_simulation(mdp, num_games=3)
        
        if results:
            print(f"✅ Test réussi pour {layout_file}")
        else:
            print(f"❌ Test échoué pour {layout_file}")
    
    print(f"\n🎯 TESTS TERMINÉS")


if __name__ == "__main__":
    main()
