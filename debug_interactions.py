#!/usr/bin/env python3
"""
debug_interactions.py

Script pour analyser en détail les interactions d'un GreedyAgent
et comprendre pourquoi il fait plus d'interactions que nécessaire.
"""

import os
import time
from collections import defaultdict

from overcooked_ai_py.agents.agent import GreedyAgent
from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.mdp.actions import Action


class InteractionDebugger:
    """Débugger qui trace toutes les interactions et états."""
    
    def __init__(self):
        self.interaction_log = []
        self.state_log = []
    
    def debug_single_game(self, layout_name: str, max_steps: int = 200):
        """Debug une partie en mode agent seul avec traces détaillées."""
        print(f"🔍 DEBUG: {layout_name}")
        print("=" * 50)
        
        try:
            # Charger le MDP
            full_layout_path = f"generation_cesar/{layout_name}"
            mdp = OvercookedGridworld.from_layout_name(full_layout_path)
            
            # Créer l'agent
            os.makedirs("./overcooked_ai_py/data/planners/generation_cesar/", exist_ok=True)
            agent = GreedyAgent(auto_unstuck=True)
            agent.set_mdp(mdp)
            agent.set_agent_index(0)
            
            # État initial
            state = mdp.get_standard_start_state()
            initial_orders = len(state.all_orders)
            
            print(f"📋 Commandes initiales: {initial_orders}")
            print(f"🎯 Objectif: Compléter toutes les commandes")
            
            # Variables de suivi
            interaction_count = 0
            step_count = 0
            
            print(f"\n🎮 DÉBUT SIMULATION DÉTAILLÉE")
            print("-" * 50)
            
            # Simulation avec debug
            for step in range(max_steps):
                # État avant action
                player = state.players[0]
                player_obj = player.held_object.name if player.held_object else "rien"
                
                # Action de l'agent
                action, info = agent.action(state)
                
                # Trace de l'action
                if action == Action.INTERACT:
                    interaction_count += 1
                    print(f"Step {step:3d}: INTERACT #{interaction_count:2d} - "
                          f"Position: {player.position}, "
                          f"Tient: {player_obj}")
                    
                    # Analyser ce qui est à cette position
                    x, y = player.position
                    terrain = mdp.terrain_mtx[y][x] if 0 <= x < mdp.width and 0 <= y < mdp.height else "?"
                    
                    # Vérifier les objets environnants
                    objects_here = []
                    for obj in state.all_objects_list:
                        if hasattr(obj, 'position') and obj.position == player.position:
                            objects_here.append(obj.name if hasattr(obj, 'name') else str(type(obj)))
                    
                    print(f"            Terrain: {terrain}, Objets: {objects_here}")
                else:
                    action_name = {
                        Action.STAY: "STAY",
                        (0, 1): "BAS",
                        (0, -1): "HAUT", 
                        (1, 0): "DROITE",
                        (-1, 0): "GAUCHE"
                    }.get(action, str(action))
                    
                    if step % 10 == 0:  # Afficher position tous les 10 steps
                        print(f"Step {step:3d}: {action_name:8s} - Position: {player.position}, Tient: {player_obj}")
                
                # Exécuter l'action
                joint_action = [action, Action.STAY]  # Agent seul + agent inactif
                next_state, info = mdp.get_state_transition(state, joint_action)
                
                # Vérifier si quelque chose a changé
                reward = sum(info['sparse_reward_by_agent'])
                if reward > 0:
                    print(f"            ✅ RÉCOMPENSE: +{reward} (commande livrée!)")
                
                # Vérifier si fini
                if len(next_state.all_orders) == 0:
                    step_count = step + 1
                    print(f"\n🏁 TERMINÉ en {step_count} steps!")
                    break
                
                state = next_state
                step_count = step + 1
            
            print(f"\n📊 RÉSUMÉ:")
            print(f"   Total interactions: {interaction_count}")
            print(f"   Total steps: {step_count}")
            print(f"   Ratio interactions/steps: {interaction_count/step_count:.2f}")
            
            # Analyse des interactions théoriques nécessaires
            print(f"\n🔍 ANALYSE THÉORIQUE:")
            print(f"   Interactions minimum pour 1 soupe:")
            print(f"   1. Prendre tomate (distributeur)")
            print(f"   2. Déposer tomate (pot)")
            print(f"   3. Prendre oignon (distributeur)")
            print(f"   4. Déposer oignon (pot)")
            print(f"   5. Cuisiner la soupe (pot)")
            print(f"   6. Prendre assiette (distributeur)")
            print(f"   7. Servir la soupe (pot → assiette)")
            print(f"   8. Livrer (zone de service)")
            print(f"   = 8 interactions minimum")
            print(f"   Interactions observées: {interaction_count}")
            print(f"   Surplus: {interaction_count - 8} (+{((interaction_count-8)/8*100):.0f}%)")
            
            return {
                'interactions': interaction_count,
                'steps': step_count,
                'completed': len(next_state.all_orders) == 0
            }
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return None


def main():
    """Test de debug des interactions."""
    print("🔍 DEBUGGER D'INTERACTIONS OVERCOOKED")
    print("🤖 Analyse du comportement GreedyAgent")
    print("=" * 50)
    
    debugger = InteractionDebugger()
    
    # Tester le layout césar 0
    result = debugger.debug_single_game("layout_cesar_0", max_steps=200)
    
    if result:
        print(f"\n✅ Debug terminé avec succès!")
    else:
        print(f"\n❌ Échec du debug")


if __name__ == "__main__":
    main()
