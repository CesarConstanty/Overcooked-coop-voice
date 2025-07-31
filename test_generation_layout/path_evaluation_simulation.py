#!/usr/bin/env python3
"""
Path Frequency Analysis - Analyseur de Trajectoires Optimisé

Ce module analyse les trajectoires des agents dans les simulations Overcooked pour:
1. Identifier les trajectoires les plus fréquemment suivies
2. Visualiser la fréquence par gradient de couleur
3. Distinguer les agents par style de trait (continu/discontinu)
4. Mettre en évidence les zones d'interférence entre agents
5. Générer un fichier d'analyse par layout

Author: Assistant
Date: 2025
"""

import os
import json
import glob
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from datetime import datetime

class PathFrequencyAnalyzer:
    """Analyseur optimisé pour la fréquence des trajectoires"""
    
    def __init__(self):
        self.collision_distance = 1  # Distance pour détecter les interférences
        
    def load_simulation_data(self, layout_name: str) -> List[Dict]:
        """Charge toutes les données de simulation pour un layout"""
        simulation_dir = f"data_simulation/data_simu_{layout_name}"
        
        if not os.path.exists(simulation_dir):
            print(f"❌ Simulation directory not found: {simulation_dir}")
            return []
        
        simulation_files = glob.glob(os.path.join(simulation_dir, f"data_simu_{layout_name}_game_*.json"))
        simulation_data = []
        
        for file_path in simulation_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    simulation_data.append(data)
            except Exception as e:
                print(f"❌ Error loading {file_path}: {e}")
        
        return simulation_data
    
    def extract_trajectories_by_agent(self, simulation_data_list: List[Dict]) -> Dict[str, List[List[Tuple[int, int]]]]:
        """Extrait les trajectoires groupées par agent (agent_0, agent_1)"""
        agent_trajectories = {'agent_0': [], 'agent_1': []}
        
        for simulation_data in simulation_data_list:
            try:
                history_info = simulation_data['simulation_data']['history_info']
                
                for game_key, game_data in history_info.items():
                    if isinstance(game_data, list) and len(game_data) > 0:
                        agent_data = game_data[0]
                        
                        # Extraire trajectoire agent_0
                        if 'agent_0_history' in agent_data:
                            agent_history = agent_data['agent_0_history']
                            positions = self._extract_positions_from_history(agent_history)
                            if positions:
                                agent_trajectories['agent_0'].append(positions)
                        
                        # Extraire trajectoire agent_1
                        if 'agent_1_history' in agent_data:
                            agent_history = agent_data['agent_1_history']
                            positions = self._extract_positions_from_history(agent_history)
                            if positions:
                                agent_trajectories['agent_1'].append(positions)
            
            except Exception as e:
                print(f"❌ Error extracting from simulation: {e}")
        
        return agent_trajectories
    
    def _extract_positions_from_history(self, agent_history: Dict) -> List[Tuple[int, int]]:
        """Extrait les positions d'un historique d'agent"""
        positions = []
        step_keys = [k for k in agent_history.keys() if k.startswith('step_') and k.endswith('_position')]
        step_keys.sort(key=lambda x: int(x.split('_')[1]))
        
        for step_key in step_keys:
            pos = agent_history[step_key]
            if isinstance(pos, list) and len(pos) == 2:
                positions.append((pos[0], pos[1]))
        
        return positions
    
    def calculate_path_frequencies(self, trajectories: List[List[Tuple[int, int]]]) -> Dict[Tuple[int, int], int]:
        """Calcule la fréquence de passage pour chaque position"""
        position_counts = Counter()
        
        for trajectory in trajectories:
            for position in trajectory:
                position_counts[position] += 1
        
        return dict(position_counts)
    
    def detect_interference_zones(self, agent_0_trajectories: List[List[Tuple[int, int]]], 
                                 agent_1_trajectories: List[List[Tuple[int, int]]]) -> List[Tuple[int, int]]:
        """Détecte les zones où les agents interfèrent (positions proches simultanément)"""
        interference_positions = set()
        
        # Comparer chaque paire de trajectoires (une de chaque agent)
        min_games = min(len(agent_0_trajectories), len(agent_1_trajectories))
        
        for game_idx in range(min_games):
            traj_0 = agent_0_trajectories[game_idx]
            traj_1 = agent_1_trajectories[game_idx]
            
            min_steps = min(len(traj_0), len(traj_1))
            
            for step in range(min_steps):
                pos_0 = traj_0[step]
                pos_1 = traj_1[step]
                
                # Calculer distance Manhattan
                distance = abs(pos_0[0] - pos_1[0]) + abs(pos_0[1] - pos_1[1])
                
                if distance <= self.collision_distance:
                    interference_positions.add(pos_0)
                    interference_positions.add(pos_1)
        
        return list(interference_positions)
    
    def get_simulation_grid(self, simulation_data_list: List[Dict]) -> Optional[List[List[str]]]:
        """Récupère la grille de simulation si disponible"""
        if not simulation_data_list:
            return None
        
        try:
            sim_data = simulation_data_list[0]
            if 'grid' in sim_data:
                if isinstance(sim_data['grid'], str):
                    return [list(line) for line in sim_data['grid'].split('\n') if line.strip()]
                elif isinstance(sim_data['grid'], list):
                    return sim_data['grid']
            elif 'simulation_data' in sim_data and 'grid' in sim_data['simulation_data']:
                grid_val = sim_data['simulation_data']['grid']
                if isinstance(grid_val, str):
                    return [list(line) for line in grid_val.split('\n') if line.strip()]
                elif isinstance(grid_val, list):
                    return grid_val
        except Exception as e:
            print(f"⚠️  Could not extract simulation grid: {e}")
        
        return None
    
    def create_frequency_visualization(self, layout_name: str, 
                                     agent_0_trajectories: List[List[Tuple[int, int]]], 
                                     agent_1_trajectories: List[List[Tuple[int, int]]],
                                     simulation_grid: Optional[List[List[str]]] = None) -> str:
        """Crée la visualisation des fréquences de trajectoires"""
        
        # Calculer les fréquences pour chaque agent
        freq_0 = self.calculate_path_frequencies(agent_0_trajectories)
        freq_1 = self.calculate_path_frequencies(agent_1_trajectories)
        
        # Détecter les zones d'interférence
        interference_zones = self.detect_interference_zones(agent_0_trajectories, agent_1_trajectories)
        
        # Créer la figure avec plus d'espace pour les annotations
        plt.figure(figsize=(16, 12))
        
        # Afficher la grille de base si disponible (CORRECTION: retirer origin='lower')
        if simulation_grid:
            height = len(simulation_grid)
            width = len(simulation_grid[0])
            
            grid_array = np.zeros((height, width))
            char_map = {'X': 1, 'P': 2, 'O': 3, 'T': 4, 'D': 5, 'S': 6, ' ': 0}
            
            for y in range(height):
                for x in range(width):
                    char = simulation_grid[y][x]
                    grid_array[y, x] = char_map.get(char, 0)
            
            # CORRECTION: Supprimer origin='lower' pour éviter l'inversion
            plt.imshow(grid_array, cmap='tab10', alpha=0.3)
            
            # Annoter les éléments du décor sur la grille
            for y in range(height):
                for x in range(width):
                    char = simulation_grid[y][x]
                    if char in ['P', 'O', 'T', 'D', 'S', 'X']:
                        plt.text(x, y, char, ha='center', va='center', 
                               fontsize=10, fontweight='bold', color='black',
                               bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8))
        
        # Déterminer les échelles de fréquence
        max_freq_0 = max(freq_0.values()) if freq_0 else 1
        max_freq_1 = max(freq_1.values()) if freq_1 else 1
        
        # Calculer fréquences moyennes pour affichage
        avg_freq_0 = {pos: count / len(agent_0_trajectories) for pos, count in freq_0.items()} if agent_0_trajectories else {}
        avg_freq_1 = {pos: count / len(agent_1_trajectories) for pos, count in freq_1.items()} if agent_1_trajectories else {}
        
        # Visualiser les trajectoires de l'agent 0 avec fréquences moyennes
        for pos, count in freq_0.items():
            intensity = count / max_freq_0
            avg_freq = avg_freq_0[pos]
            plt.scatter(pos[0], pos[1], 
                       c='red', s=50 + intensity * 150, alpha=0.4 + intensity * 0.6,
                       marker='o', label='Agent 0 Paths' if pos == list(freq_0.keys())[0] else "")
            
            # Afficher la fréquence moyenne en chiffres
            if avg_freq >= 1.0:  # Seulement si fréquence significative
                plt.text(pos[0], pos[1], f'{avg_freq:.1f}', ha='center', va='center',
                        fontsize=8, color='darkred', fontweight='bold',
                        bbox=dict(boxstyle="round,pad=0.1", facecolor="white", alpha=0.9))
        
        # Visualiser les trajectoires de l'agent 1 avec fréquences moyennes
        for pos, count in freq_1.items():
            intensity = count / max_freq_1
            avg_freq = avg_freq_1[pos]
            # Décaler légèrement pour éviter chevauchement
            offset_x, offset_y = 0.1, 0.1
            plt.scatter(pos[0] + offset_x, pos[1] + offset_y, 
                       c='blue', s=50 + intensity * 150, alpha=0.4 + intensity * 0.6,
                       marker='^', label='Agent 1 Paths' if pos == list(freq_1.keys())[0] else "")
            
            # Afficher la fréquence moyenne en chiffres (décalée)
            if avg_freq >= 1.0:  # Seulement si fréquence significative
                plt.text(pos[0] + offset_x, pos[1] + offset_y, f'{avg_freq:.1f}', 
                        ha='center', va='center', fontsize=8, color='darkblue', fontweight='bold',
                        bbox=dict(boxstyle="round,pad=0.1", facecolor="lightblue", alpha=0.9))
        
        # Calculer les collisions fréquentes pour mise en avant
        collision_counts = Counter(interference_zones)
        frequent_collisions = [pos for pos, count in collision_counts.most_common(5)]
        
        # Marquer les zones d'interférence avec mise en avant des plus fréquentes
        if interference_zones:
            for idx, pos in enumerate(interference_zones):
                # Taille et couleur selon fréquence de collision
                is_frequent = pos in frequent_collisions
                size = 300 if is_frequent else 200
                color = 'red' if is_frequent else 'orange'
                
                plt.scatter(pos[0], pos[1], 
                           c=color, s=size, marker='X', alpha=0.9,
                           edgecolors='darkred', linewidth=3 if is_frequent else 2,
                           label='Frequent Collisions' if idx == 0 and is_frequent else 
                                 'Interference Zones' if idx == 0 and not is_frequent else "")
                
                # Afficher le nombre de collisions
                collision_count = collision_counts[pos]
                if collision_count > 1:  # Seulement si collision multiple
                    plt.text(pos[0], pos[1], str(collision_count), ha='center', va='center',
                            fontsize=10, color='white', fontweight='bold')
        
        # Mettre en avant les zones les plus visitées pour agent 0 (TOP 3)
        if freq_0:
            top_freq_0 = sorted(freq_0.items(), key=lambda x: x[1], reverse=True)[:3]
            for idx, (pos, count) in enumerate(top_freq_0):
                # Cercle de mise en avant
                plt.scatter(pos[0], pos[1], s=400, marker='o', 
                           facecolors='none', edgecolors='darkred', linewidth=4, alpha=0.8)
                
                # Annotation avec rang et fréquence
                plt.annotate(f'A0-#{idx+1}\n({count})', (pos[0], pos[1]), 
                           xytext=(15, 15), textcoords='offset points',
                           fontsize=10, color='darkred', weight='bold',
                           bbox=dict(boxstyle="round,pad=0.3", facecolor="mistyrose", alpha=0.9),
                           arrowprops=dict(arrowstyle='->', color='darkred'))
        
        # Mettre en avant les zones les plus visitées pour agent 1 (TOP 3)
        if freq_1:
            top_freq_1 = sorted(freq_1.items(), key=lambda x: x[1], reverse=True)[:3]
            for idx, (pos, count) in enumerate(top_freq_1):
                # Cercle de mise en avant
                plt.scatter(pos[0], pos[1], s=400, marker='^', 
                           facecolors='none', edgecolors='darkblue', linewidth=4, alpha=0.8)
                
                # Annotation avec rang et fréquence
                plt.annotate(f'A1-#{idx+1}\n({count})', (pos[0], pos[1]), 
                           xytext=(-15, -15), textcoords='offset points',
                           fontsize=10, color='darkblue', weight='bold',
                           bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.9),
                           arrowprops=dict(arrowstyle='->', color='darkblue'))
        
        # Configuration du graphique avec plus d'informations
        total_positions_0 = sum(freq_0.values()) if freq_0 else 0
        total_positions_1 = sum(freq_1.values()) if freq_1 else 0
        unique_positions_0 = len(freq_0) if freq_0 else 0
        unique_positions_1 = len(freq_1) if freq_1 else 0
        
        plt.title(f'MAP - Path Frequency Analysis: {layout_name}\n'
                 f'AGENTS - Agent 0: {len(agent_0_trajectories)} traj. ({total_positions_0} moves, {unique_positions_0} unique pos.) | '
                 f'Agent 1: {len(agent_1_trajectories)} traj. ({total_positions_1} moves, {unique_positions_1} unique pos.)\n'
                 f'WARNING - Interference Zones: {len(interference_zones)} detected', 
                 fontsize=12, fontweight='bold')
        
        plt.xlabel('X Position', fontsize=12)
        plt.ylabel('Y Position', fontsize=12)
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        
        # Informations détaillées sur les fréquences et hotspots
        info_lines = [
            f"STATS - ANALYSE DES FREQUENCES:",
            f"RED Agent 0 (o): Max = {max_freq_0} | Avg = {total_positions_0/unique_positions_0:.1f}" if unique_positions_0 > 0 else "RED Agent 0 (o): Aucune donnee",
            f"BLUE Agent 1 (^): Max = {max_freq_1} | Avg = {total_positions_1/unique_positions_1:.1f}" if unique_positions_1 > 0 else "BLUE Agent 1 (^): Aucune donnee",
            "",
            f"TARGET HOTSPOTS: A0-#1/A1-#1 = Positions les + visitees",
            f"ALERT COLLISIONS: X = Zones de conflit (nombre affiche)",
            f"MAP DECOR: P=Pot O=Oignon T=Tomate D=Livraison S=Service X=Mur",
            "",
            f"RULER Chiffres = Frequence moyenne | Taille proportionnelle Intensite"
        ]
        
        info_text = "\n".join(info_lines)
        plt.figtext(0.02, 0.02, info_text, fontsize=9,
                   bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow", alpha=0.95))
        
        plt.grid(True, alpha=0.3)
        plt.gca().set_aspect('equal')
        
        # CORRECTION: Supprimer l'inversion pour garder l'orientation originale du layout
        # plt.gca().invert_yaxis()  # Commenté pour éviter l'effet miroir
        
        # Sauvegarder
        output_path = f"analysis_plots/path_analysis_{layout_name}.png"
        os.makedirs("analysis_plots", exist_ok=True)
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def save_analysis_results(self, layout_name: str, 
                            agent_0_trajectories: List[List[Tuple[int, int]]], 
                            agent_1_trajectories: List[List[Tuple[int, int]]],
                            freq_0: Dict[Tuple[int, int], int],
                            freq_1: Dict[Tuple[int, int], int],
                            interference_zones: List[Tuple[int, int]]) -> str:
        """Sauvegarde les résultats détaillés de l'analyse en JSON"""
        
        # Calculer les statistiques
        total_positions_0 = sum(freq_0.values()) if freq_0 else 0
        total_positions_1 = sum(freq_1.values()) if freq_1 else 0
        unique_positions_0 = len(freq_0) if freq_0 else 0
        unique_positions_1 = len(freq_1) if freq_1 else 0
        
        # Top positions pour chaque agent
        top_freq_0 = sorted(freq_0.items(), key=lambda x: x[1], reverse=True)[:5] if freq_0 else []
        top_freq_1 = sorted(freq_1.items(), key=lambda x: x[1], reverse=True)[:5] if freq_1 else []
        
        # Créer le rapport détaillé
        results = {
            "layout_name": layout_name,
            "analysis_timestamp": datetime.now().isoformat(),
            "summary": {
                "total_trajectories": {
                    "agent_0": len(agent_0_trajectories),
                    "agent_1": len(agent_1_trajectories)
                },
                "total_movements": {
                    "agent_0": total_positions_0,
                    "agent_1": total_positions_1
                },
                "unique_positions": {
                    "agent_0": unique_positions_0,
                    "agent_1": unique_positions_1
                },
                "average_frequency": {
                    "agent_0": round(total_positions_0 / unique_positions_0, 2) if unique_positions_0 > 0 else 0,
                    "agent_1": round(total_positions_1 / unique_positions_1, 2) if unique_positions_1 > 0 else 0
                },
                "interference_zones": len(interference_zones)
            },
            "hotspots": {
                "agent_0_top_positions": [{"position": pos, "frequency": freq} for pos, freq in top_freq_0],
                "agent_1_top_positions": [{"position": pos, "frequency": freq} for pos, freq in top_freq_1]
            },
            "interference_analysis": {
                "total_interference_positions": len(interference_zones),
                "interference_positions": [{"position": pos} for pos in interference_zones[:10]]  # Top 10
            },
            "detailed_frequencies": {
                "agent_0": {f"{pos[0]}_{pos[1]}": freq for pos, freq in freq_0.items()},
                "agent_1": {f"{pos[0]}_{pos[1]}": freq for pos, freq in freq_1.items()}
            }
        }
        
        # Sauvegarder le fichier JSON
        output_path = f"analysis_plots/path_analysis_{layout_name}_detailed.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        return output_path

class LayoutPathEvaluator:
    """Évaluateur principal pour générer les analyses par layout"""
    
    def __init__(self):
        self.analyzer = PathFrequencyAnalyzer()
        
    def analyze_all_layouts(self) -> Dict[str, str]:
        """Analyse tous les layouts disponibles et génère les fichiers d'analyse"""
        
        data_simulation_dir = "data_simulation"
        if not os.path.exists(data_simulation_dir):
            print(f"❌ Directory not found: {data_simulation_dir}")
            return {}
        
        # Découvrir tous les layouts disponibles
        layout_dirs = [d for d in os.listdir(data_simulation_dir) 
                      if d.startswith("data_simu_") and os.path.isdir(os.path.join(data_simulation_dir, d))]
        
        layout_names = [d.replace("data_simu_", "") for d in layout_dirs]
        
        print(f"🔍 Found {len(layout_names)} layouts to analyze:")
        for name in layout_names:
            print(f"   - {name}")
        
        results = {}
        
        for layout_name in layout_names:
            print(f"\n📊 Analyzing layout: {layout_name}")
            
            # Charger les données
            simulation_data = self.analyzer.load_simulation_data(layout_name)
            if not simulation_data:
                print(f"❌ No simulation data for {layout_name}")
                continue
            
            print(f"✅ Loaded {len(simulation_data)} simulation files")
            
            # Extraire les trajectoires par agent
            trajectories = self.analyzer.extract_trajectories_by_agent(simulation_data)
            agent_0_count = len(trajectories['agent_0'])
            agent_1_count = len(trajectories['agent_1'])
            
            print(f"📈 Extracted trajectories: Agent 0: {agent_0_count}, Agent 1: {agent_1_count}")
            
            if agent_0_count == 0 and agent_1_count == 0:
                print(f"❌ No trajectories found for {layout_name}")
                continue
            
            # Obtenir la grille de simulation
            simulation_grid = self.analyzer.get_simulation_grid(simulation_data)
            
            # Calculer les fréquences et zones d'interférence  
            freq_0 = self.analyzer.calculate_path_frequencies(trajectories['agent_0'])
            freq_1 = self.analyzer.calculate_path_frequencies(trajectories['agent_1'])
            interference_zones = self.analyzer.detect_interference_zones(trajectories['agent_0'], trajectories['agent_1'])
            
            # Créer la visualisation
            output_path = self.analyzer.create_frequency_visualization(
                layout_name, 
                trajectories['agent_0'], 
                trajectories['agent_1'],
                simulation_grid
            )
            
            # Sauvegarder les résultats détaillés
            json_path = self.analyzer.save_analysis_results(
                layout_name, 
                trajectories['agent_0'], 
                trajectories['agent_1'],
                freq_0, freq_1, interference_zones
            )
            
            if output_path:
                results[layout_name] = {
                    'visualization': output_path,
                    'detailed_analysis': json_path
                }
                print(f"✅ Generated visualization: {output_path}")
                print(f"📊 Saved detailed analysis: {json_path}")
                self._print_layout_summary(layout_name, freq_0, freq_1, interference_zones, trajectories)
            else:
                print(f"❌ Failed to generate visualization for {layout_name}")
        
        return results
    
    def _print_layout_summary(self, layout_name: str, freq_0: Dict, freq_1: Dict, 
                             interference_zones: List, trajectories: Dict):
        """Affiche un résumé lisible de l'analyse pour un layout"""
        print(f"\n📋 === RÉSUMÉ DÉTAILLÉ: {layout_name} ===")
        
        # Statistiques générales
        total_0 = sum(freq_0.values()) if freq_0 else 0
        total_1 = sum(freq_1.values()) if freq_1 else 0
        unique_0 = len(freq_0) if freq_0 else 0
        unique_1 = len(freq_1) if freq_1 else 0
        
        print(f"📊 Mouvements totaux: Agent 0 = {total_0}, Agent 1 = {total_1}")
        print(f"🎯 Positions uniques: Agent 0 = {unique_0}, Agent 1 = {unique_1}")
        
        if unique_0 > 0:
            print(f"📈 Fréquence moyenne Agent 0: {total_0/unique_0:.2f} passages/position")
        if unique_1 > 0:
            print(f"📈 Fréquence moyenne Agent 1: {total_1/unique_1:.2f} passages/position")
        
        # Top 3 positions les plus visitées
        if freq_0:
            top_0 = sorted(freq_0.items(), key=lambda x: x[1], reverse=True)[:3]
            print(f"🔴 Top 3 positions Agent 0:")
            for i, (pos, count) in enumerate(top_0, 1):
                print(f"   {i}. Position {pos}: {count} passages")
        
        if freq_1:
            top_1 = sorted(freq_1.items(), key=lambda x: x[1], reverse=True)[:3]
            print(f"🔵 Top 3 positions Agent 1:")
            for i, (pos, count) in enumerate(top_1, 1):
                print(f"   {i}. Position {pos}: {count} passages")
        
        # Zones d'interférence
        if interference_zones:
            print(f"⚠️ Zones d'interférence détectées: {len(interference_zones)}")
            print(f"   Positions problématiques: {interference_zones[:5]}")  # 5 premières
        else:
            print(f"✅ Aucune zone d'interférence détectée")
        
        print(f"{'='*50}")
    
    def _print_final_summary(self, results: Dict):
        """Affiche le résumé final de tous les layouts"""
        print(f"\n🎉 === ANALYSE TERMINÉE ===")
        print(f"📊 {len(results)} layouts analysés avec succès")
        print(f"\n📁 Fichiers générés:")
        
        for layout_name, paths in results.items():
            if isinstance(paths, dict):
                print(f"   📈 {layout_name}:")
                print(f"      🖼️  Visualisation: {paths['visualization']}")
                print(f"      📋 Analyse détaillée: {paths['detailed_analysis']}")
            else:
                print(f"   📈 {layout_name}: {paths}")
        
        print(f"\n💾 Tous les fichiers sont sauvegardés dans analysis_plots/")
        print(f"⏰ Analyse terminée à {datetime.now().strftime('%H:%M:%S')}")

def main():
    """Fonction principale"""
    print("🚀 PATH FREQUENCY ANALYSIS")
    print("="*50)
    
    evaluator = LayoutPathEvaluator()
    results = evaluator.analyze_all_layouts()
    
    # Afficher le résumé final
    evaluator._print_final_summary(results)

if __name__ == "__main__":
    main()
