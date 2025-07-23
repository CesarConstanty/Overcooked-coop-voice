#!/usr/bin/env python3
"""
quick_layout_test.py

Script simplifié pour tester rapidement un layout avec deux GreedyAgent.
Affiche les métriques essentielles de manière concise.
"""

import sys
import os
import time
from collections import defaultdict

from overcooked_ai_py.agents.agent import GreedyAgent, AgentGroup
from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld

layout_name = "layout_cesar_1"

def test_layout(layout_name: str, num_games: int = 3, horizon: int = 400, verbose: bool = False):
    """
    Teste un layout spécifique avec des GreedyAgent.
    
    Args:
        layout_name: Nom du layout (ex: "layout_cesar_0")
        num_games: Nombre de parties à jouer
        horizon: Nombre maximum de steps par partie
        verbose: Affichage détaillé
    """
    print(f"🎮 Test rapide: {layout_name}")
    print("-" * 40)
    
    start_time = time.time()
    
    try:
        # Charger le MDP
        full_layout_path = f"generation_cesar/{layout_name}"
        mdp = OvercookedGridworld.from_layout_name(full_layout_path)
        
        # Créer les planners directory si nécessaire
        os.makedirs("./overcooked_ai_py/data/planners/generation_cesar/", exist_ok=True)
        
        # Créer les agents
        agent_0 = GreedyAgent(auto_unstuck=True)
        agent_1 = GreedyAgent(auto_unstuck=True)
        agent_group = AgentGroup(agent_0, agent_1)
        agent_group.set_mdp(mdp)
        
        print(f"🤖 2x GreedyAgent configurés")
        print(f"📊 Layout: {mdp.width}x{mdp.height}")
        
        # Statistiques globales
        all_results = []
        
        # Jouer plusieurs parties
        for game_num in range(1, num_games + 1):
            if verbose:
                print(f"\n🎮 Partie {game_num}:")
            
            # Reset des agents
            agent_group.reset()
            agent_group.set_mdp(mdp)
            
            # État initial
            state = mdp.get_standard_start_state()
            initial_orders = len(state.all_orders)
            
            # Variables de suivi
            step_count = 0
            total_reward = 0
            completed = False
            actions_count = [0, 0]  # Actions par agent
            
            # Simulation
            game_start = time.time()
            
            for step in range(horizon):
                # Actions des agents
                joint_action_and_infos = agent_group.joint_action(state)
                joint_action = [action_info[0] for action_info in joint_action_and_infos]
                
                # Compter les actions
                for i in range(2):
                    actions_count[i] += 1
                
                # Transition d'état
                next_state, info = mdp.get_state_transition(state, joint_action)
                
                # Récompense
                step_reward = sum(info['sparse_reward_by_agent'])
                total_reward += step_reward
                
                # Vérifier si terminé
                if len(next_state.all_orders) == 0:
                    completed = True
                    step_count = step + 1
                    if verbose:
                        print(f"   ✅ Terminé en {step_count} steps!")
                    break
                
                state = next_state
                step_count = step + 1
            
            game_time = time.time() - game_start
            fps = step_count / max(0.001, game_time)
            
            # Enregistrer les résultats
            result = {
                'steps': step_count,
                'completed': completed,
                'reward': total_reward,
                'time': game_time,
                'fps': fps,
                'actions_agent_0': actions_count[0],
                'actions_agent_1': actions_count[1],
                'orders_completed': initial_orders - len(state.all_orders)
            }
            all_results.append(result)
            
            if not verbose:
                status = "✅" if completed else "❌"
                print(f"   Partie {game_num}: {status} {step_count} steps, "
                      f"{fps:.1f} FPS, {result['orders_completed']}/{initial_orders} commandes")
        
        # Statistiques finales
        completed_games = [r for r in all_results if r['completed']]
        
        print(f"\n📊 RÉSULTATS FINAUX:")
        print(f"   Parties complétées: {len(completed_games)}/{num_games}")
        
        if completed_games:
            avg_steps = sum(r['steps'] for r in completed_games) / len(completed_games)
            min_steps = min(r['steps'] for r in completed_games)
            max_steps = max(r['steps'] for r in completed_games)
            avg_fps = sum(r['fps'] for r in completed_games) / len(completed_games)
            avg_reward = sum(r['reward'] for r in completed_games) / len(completed_games)
            
            print(f"   Temps moyen: {avg_steps:.1f} steps ({min_steps}-{max_steps})")
            print(f"   FPS moyen: {avg_fps:.1f}")
            print(f"   Score moyen: {avg_reward:.1f}")
            
            # Actions par agent
            total_actions_0 = sum(r['actions_agent_0'] for r in completed_games)
            total_actions_1 = sum(r['actions_agent_1'] for r in completed_games)
            total_steps = sum(r['steps'] for r in completed_games)
            
            print(f"   Actions/step: Agent0={total_actions_0/total_steps:.2f}, "
                  f"Agent1={total_actions_1/total_steps:.2f}")
        else:
            print(f"   ❌ Aucune partie complétée")
        
        total_time = time.time() - start_time
        print(f"   Temps total: {total_time:.1f}s")
        
        return completed_games
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return []


def main():
    """Fonction principale avec gestion des arguments."""
    
    if len(sys.argv) < 2:
        print("Usage: python quick_layout_test.py <layout_name> [num_games] [--verbose]")
        print("Exemple: python quick_layout_test.py layout_cesar_0 3 --verbose")
        return
    
    layout_name = sys.argv[1]
    num_games = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 3
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
    print(f"🎮 TEST RAPIDE LAYOUT OVERCOOKED")
    print(f"🤖 Avec 2x GreedyAgent")
    print("=" * 40)
    
    results = test_layout(layout_name, num_games, verbose=verbose)
    
    if results:
        print(f"\n🎯 Layout '{layout_name}' testé avec succès!")
    else:
        print(f"\n❌ Échec du test pour '{layout_name}'")


if __name__ == "__main__":
    main()
