#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sélecteur final professionnel de layouts Overcooked
- Sélection basée sur 3 critères spécifiques avec pondération configurable
- Critère 1: Nombre d'étapes nécessaires en mode duo (minimiser)
- Critère 2: Pourcentage de gain coopération duo vs solo (maximiser)
- Critère 3: Nombre d'échanges utilisés (optimiser dans range cible)
- Visualisations graphiques des 3 critères
- Génération de trajectoires détaillées pour layouts sélectionnés
"""

import json
import time
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional, Any
import argparse
import shutil
from datetime import datetime
import warnings

# Supprimer les warnings de matplotlib
warnings.filterwarnings('ignore')

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('final_selection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SelectionCriteria:
    """Classe pour gérer les critères de sélection."""
    
    def __init__(self, config: Dict):
        self.criteria_config = config["pipeline_config"]["selection"]["criteria"]
        self.filtering_config = config["pipeline_config"]["selection"].get("filtering", {})
        self.max_layouts = config["pipeline_config"]["selection"]["final_layouts_count"]
        
        # Extraire les poids
        self.cooperation_gain_weight = self.criteria_config["cooperation_gain"]["weight"]
        self.efficiency_weight = self.criteria_config["efficiency"]["weight"]
        self.exchanges_weight = self.criteria_config["exchanges"]["weight"]
        
        # Vérifier que les poids somment à 1
        total_weight = self.cooperation_gain_weight + self.efficiency_weight + self.exchanges_weight
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"⚠️ Les poids ne somment pas à 1.0 (total: {total_weight:.3f})")
        
        logger.info(f"🎯 Critères de sélection configurés:")
        logger.info(f"  • Efficacité: {self.efficiency_weight:.2f}")
        logger.info(f"  • Gain coopération: {self.cooperation_gain_weight:.2f}")
        logger.info(f"  • Échanges utilisés: {self.exchanges_weight:.2f}")
    
    def extract_criteria_values(self, evaluation: Dict) -> Optional[Dict]:
        """Extrait les valeurs des 3 critères d'une évaluation."""
        metrics = evaluation.get('summary_metrics', {})
        
        # Vérifier les filtres de base
        if metrics.get('success_rate', 0) < self.filtering_config.get('min_success_rate', 0.8) * 100:
            return None
        
        if metrics.get('avg_cooperation_gain', 0) < self.filtering_config.get('min_cooperation_gain', 10.0):
            return None
        
        if metrics.get('total_duo_steps', float('inf')) > self.filtering_config.get('max_duo_steps', 200):
            return None
        
        # Extraire les valeurs des critères
        duo_steps = metrics.get('total_duo_steps', float('inf'))
        cooperation_gain = metrics.get('avg_cooperation_gain', 0)
        exchanges_used = metrics.get('total_exchanges_used', 0)
        
        if duo_steps == float('inf'):
            return None
        
        return {
            'layout_id': evaluation.get('layout_id', 'unknown'),
            'recipe_group_id': evaluation.get('recipe_group_id', 'unknown'),
            'duo_steps': duo_steps,
            'cooperation_gain_percent': cooperation_gain,
            'exchanges_used': exchanges_used,
            'raw_metrics': metrics
        }
    
    def normalize_criteria(self, criteria_data: List[Dict]) -> List[Dict]:
        """Normalise les critères selon min-max."""
        if not criteria_data:
            return []
        
        # Extraire les valeurs
        duo_steps_values = [d['duo_steps'] for d in criteria_data]
        cooperation_values = [d['cooperation_gain_percent'] for d in criteria_data]
        exchanges_values = [d['exchanges_used'] for d in criteria_data]
        
        # Calculer min/max pour normalisation
        duo_steps_min, duo_steps_max = min(duo_steps_values), max(duo_steps_values)
        coop_min, coop_max = min(cooperation_values), max(cooperation_values)
        exchanges_min, exchanges_max = min(exchanges_values), max(exchanges_values)
        
        logger.info(f"📊 Ranges des critères:")
        logger.info(f"  • Steps duo: {duo_steps_min:.1f} - {duo_steps_max:.1f}")
        logger.info(f"  • Gain coopération: {coop_min:.1f}% - {coop_max:.1f}%")
        logger.info(f"  • Échanges: {exchanges_min} - {exchanges_max}")
        
        # Normaliser et calculer les scores
        for data in criteria_data:
            # Normalisation min-max [0, 1]
            if duo_steps_max > duo_steps_min:
                normalized_duo_steps = 1 - (data['duo_steps'] - duo_steps_min) / (duo_steps_max - duo_steps_min)  # Inverser car on veut minimiser
            else:
                normalized_duo_steps = 1.0
            
            if coop_max > coop_min:
                normalized_cooperation = (data['cooperation_gain_percent'] - coop_min) / (coop_max - coop_min)
            else:
                normalized_cooperation = 1.0
            
            # Pour les échanges, on optimise vers la target_range
            target_min, target_max = self.criteria_config["exchanges"].get("target_range", [1, 3])
            exchanges_val = data['exchanges_used']
            
            if target_min <= exchanges_val <= target_max:
                normalized_exchanges = 1.0  # Optimal
            elif exchanges_val < target_min:
                normalized_exchanges = exchanges_val / target_min if target_min > 0 else 0
            else:  # exchanges_val > target_max
                # Pénaliser progressivement au-delà du max
                normalized_exchanges = max(0, 1 - (exchanges_val - target_max) / target_max)
            
            # Calculer le score composite
            composite_score = (normalized_duo_steps * self.efficiency_weight +
                             normalized_cooperation * self.cooperation_gain_weight +
                             normalized_exchanges * self.exchanges_weight)
            
            # Ajouter les valeurs normalisées
            data.update({
                'normalized_duo_steps': normalized_duo_steps,
                'normalized_cooperation': normalized_cooperation,
                'normalized_exchanges': normalized_exchanges,
                'composite_score': composite_score
            })
        
        return criteria_data

class LayoutVisualizer:
    """Classe pour générer les visualisations des critères de sélection."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.plots_dir = output_dir / "selection_plots"
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration des plots
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
    
    def generate_all_visualizations(self, criteria_data: List[Dict], selected_data: List[Dict]):
        """Génère toutes les visualisations requises."""
        logger.info("📊 Génération des visualisations des critères...")
        
        try:
            # 1. Scatter plot 3D des 3 critères
            self.plot_3d_criteria_scatter(criteria_data, selected_data)
            
            # 2. Matrice de corrélation
            self.plot_correlation_matrix(criteria_data)
            
            # 3. Distribution des critères pour layouts sélectionnés
            self.plot_selection_distribution(criteria_data, selected_data)
            
            # 4. Box plots des critères
            self.plot_criteria_boxplots(criteria_data, selected_data)
            
            # 5. Score composite vs critères individuels
            self.plot_composite_score_analysis(criteria_data, selected_data)
            
            logger.info(f"✅ Visualisations sauvegardées dans {self.plots_dir}")
            
        except Exception as e:
            logger.error(f"❌ Erreur génération visualisations: {e}", exc_info=True)
    
    def plot_3d_criteria_scatter(self, criteria_data: List[Dict], selected_data: List[Dict]):
        """Scatter plot 3D des 3 critères."""
        fig = plt.figure(figsize=(12, 9))
        ax = fig.add_subplot(111, projection='3d')
        
        # Extraire les données
        x_all = [d['duo_steps'] for d in criteria_data]
        y_all = [d['cooperation_gain_percent'] for d in criteria_data]
        z_all = [d['exchanges_used'] for d in criteria_data]
        
        x_selected = [d['duo_steps'] for d in selected_data]
        y_selected = [d['cooperation_gain_percent'] for d in selected_data]
        z_selected = [d['exchanges_used'] for d in selected_data]
        
        # Plot tous les layouts (gris)
        ax.scatter(x_all, y_all, z_all, c='lightgray', alpha=0.6, s=20, label='Tous les layouts')
        
        # Plot layouts sélectionnés (coloré par score composite)
        if selected_data:
            scores = [d['composite_score'] for d in selected_data]
            scatter = ax.scatter(x_selected, y_selected, z_selected, 
                               c=scores, cmap='viridis', s=50, alpha=0.8, 
                               label='Layouts sélectionnés')
            plt.colorbar(scatter, shrink=0.8, label='Score composite')
        
        ax.set_xlabel('Steps Duo')
        ax.set_ylabel('Gain Coopération (%)')
        ax.set_zlabel('Échanges Utilisés')
        ax.set_title('Distribution 3D des Critères de Sélection')
        ax.legend()
        
        plt.savefig(self.plots_dir / 'criteria_3d_scatter.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_correlation_matrix(self, criteria_data: List[Dict]):
        """Matrice de corrélation des critères."""
        # Créer DataFrame
        df = pd.DataFrame([
            {
                'Steps Duo': d['duo_steps'],
                'Gain Coopération (%)': d['cooperation_gain_percent'],
                'Échanges Utilisés': d['exchanges_used'],
                'Score Composite': d['composite_score']
            }
            for d in criteria_data
        ])
        
        # Calculer corrélations
        corr_matrix = df.corr()
        
        # Plot
        plt.figure(figsize=(10, 8))
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
        sns.heatmap(corr_matrix, mask=mask, annot=True, cmap='RdBu_r', center=0,
                   square=True, linewidths=0.5, cbar_kws={"shrink": .8})
        plt.title('Matrice de Corrélation des Critères de Sélection')
        plt.tight_layout()
        plt.savefig(self.plots_dir / 'correlation_matrix.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_selection_distribution(self, criteria_data: List[Dict], selected_data: List[Dict]):
        """Distribution des critères pour les layouts sélectionnés vs tous."""
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Distribution des Critères: Tous vs Sélectionnés', fontsize=16)
        
        criteria_names = [
            ('duo_steps', 'Steps Duo'),
            ('cooperation_gain_percent', 'Gain Coopération (%)'),
            ('exchanges_used', 'Échanges Utilisés'),
            ('composite_score', 'Score Composite')
        ]
        
        for idx, (field, title) in enumerate(criteria_names):
            ax = axes[idx // 2, idx % 2]
            
            all_values = [d[field] for d in criteria_data]
            selected_values = [d[field] for d in selected_data]
            
            # Histogrammes
            ax.hist(all_values, bins=20, alpha=0.6, label='Tous', color='lightblue', density=True)
            if selected_values:
                ax.hist(selected_values, bins=15, alpha=0.8, label='Sélectionnés', color='orange', density=True)
            
            ax.set_title(title)
            ax.set_ylabel('Densité')
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.plots_dir / 'selection_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_criteria_boxplots(self, criteria_data: List[Dict], selected_data: List[Dict]):
        """Box plots comparatifs des critères."""
        # Préparer les données
        all_df = pd.DataFrame([
            {
                'Steps Duo': d['duo_steps'],
                'Gain Coopération': d['cooperation_gain_percent'],
                'Échanges': d['exchanges_used'],
                'Type': 'Tous'
            }
            for d in criteria_data
        ])
        
        selected_df = pd.DataFrame([
            {
                'Steps Duo': d['duo_steps'],
                'Gain Coopération': d['cooperation_gain_percent'],
                'Échanges': d['exchanges_used'],
                'Type': 'Sélectionnés'
            }
            for d in selected_data
        ])
        
        combined_df = pd.concat([all_df, selected_df], ignore_index=True)
        
        # Plot
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle('Comparaison Boxplots: Tous vs Sélectionnés', fontsize=16)
        
        criteria = ['Steps Duo', 'Gain Coopération', 'Échanges']
        
        for idx, criterion in enumerate(criteria):
            sns.boxplot(data=combined_df, x='Type', y=criterion, ax=axes[idx])
            axes[idx].set_title(f'{criterion}')
            axes[idx].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.plots_dir / 'criteria_boxplots.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_composite_score_analysis(self, criteria_data: List[Dict], selected_data: List[Dict]):
        """Analyse du score composite vs critères individuels."""
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Analyse du Score Composite', fontsize=16)
        
        # Score composite vs chaque critère
        criteria_fields = [
            ('duo_steps', 'Steps Duo'),
            ('cooperation_gain_percent', 'Gain Coopération (%)'),
            ('exchanges_used', 'Échanges Utilisés')
        ]
        
        for idx, (field, title) in enumerate(criteria_fields):
            ax = axes[idx // 2, idx % 2]
            
            x_all = [d[field] for d in criteria_data]
            y_all = [d['composite_score'] for d in criteria_data]
            
            x_selected = [d[field] for d in selected_data]
            y_selected = [d['composite_score'] for d in selected_data]
            
            # Scatter plot
            ax.scatter(x_all, y_all, alpha=0.6, s=20, color='lightgray', label='Tous')
            if selected_data:
                ax.scatter(x_selected, y_selected, alpha=0.8, s=50, color='red', label='Sélectionnés')
            
            ax.set_xlabel(title)
            ax.set_ylabel('Score Composite')
            ax.set_title(f'Score Composite vs {title}')
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        # Histogramme des scores composites
        ax = axes[1, 1]
        scores_all = [d['composite_score'] for d in criteria_data]
        scores_selected = [d['composite_score'] for d in selected_data]
        
        ax.hist(scores_all, bins=20, alpha=0.6, label='Tous', color='lightblue', density=True)
        if scores_selected:
            ax.hist(scores_selected, bins=15, alpha=0.8, label='Sélectionnés', color='orange', density=True)
        
        ax.set_xlabel('Score Composite')
        ax.set_ylabel('Densité')
        ax.set_title('Distribution des Scores Composites')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.plots_dir / 'composite_score_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()

class ProfessionalFinalSelector:
    """Sélecteur final professionnel basé sur 3 critères spécifiques."""
    
    def __init__(self, config_file: str = "config/pipeline_config.json"):
        """Initialise le sélecteur avec la configuration."""
        self.base_dir = Path(__file__).parent.parent
        self.config_file = self.base_dir / config_file
        self.config = self.load_config()
        
        # Dossiers
        self.evaluation_dir = self.base_dir / "outputs" / "detailed_evaluation"
        self.layouts_generated_dir = self.base_dir / "outputs" / self.config["pipeline_config"]["output"]["layouts_generated_dir"]
        self.layouts_selected_dir = self.base_dir / "outputs" / self.config["pipeline_config"]["output"]["layouts_selected_dir"]
        self.trajectories_dir = self.base_dir / "outputs" / self.config["pipeline_config"]["output"]["trajectories_dir"]
        self.selection_analysis_dir = self.base_dir / "outputs" / "selection_analysis"
        
        # Créer les dossiers
        self.layouts_selected_dir.mkdir(parents=True, exist_ok=True)
        self.selection_analysis_dir.mkdir(parents=True, exist_ok=True)
        
        # Modules
        self.criteria = SelectionCriteria(self.config)
        self.visualizer = LayoutVisualizer(self.selection_analysis_dir)
        
        logger.info(f"🎯 Sélecteur final initialisé")
        logger.info(f"📁 Évaluations: {self.evaluation_dir}")
        logger.info(f"📁 Layouts générés: {self.layouts_generated_dir}")
        logger.info(f"📁 Layouts sélectionnés: {self.layouts_selected_dir}")
        logger.info(f"📁 Analyse sélection: {self.selection_analysis_dir}")
    
    def load_config(self) -> Dict:
        """Charge la configuration du pipeline."""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration non trouvée: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_evaluation_results(self) -> List[Dict]:
        """Charge les résultats d'évaluation."""
        evaluation_files = list(self.evaluation_dir.glob("detailed_evaluation_*.json"))
        
        if not evaluation_files:
            raise FileNotFoundError(f"Aucun fichier d'évaluation trouvé dans {self.evaluation_dir}")
        
        # Utiliser le fichier le plus récent
        latest_file = max(evaluation_files, key=lambda f: f.stat().st_mtime)
        
        logger.info(f"📂 Chargement évaluations: {latest_file.name}")
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        evaluations = data.get('evaluations', [])
        
        logger.info(f"📊 {len(evaluations)} évaluations chargées")
        
        return evaluations
    
    def perform_final_selection(self) -> Dict:
        """Effectue la sélection finale basée sur les 3 critères."""
        start_time = time.time()
        
        try:
            # Charger les évaluations
            evaluations = self.load_evaluation_results()
            
            logger.info(f"🚀 Démarrage sélection finale")
            logger.info(f"🎯 Critères: Steps duo, Gain coopération, Échanges utilisés")
            
            # Extraire les critères de toutes les évaluations
            all_criteria_data = []
            for evaluation in evaluations:
                criteria_values = self.criteria.extract_criteria_values(evaluation)
                if criteria_values:
                    all_criteria_data.append(criteria_values)
            
            logger.info(f"📋 {len(all_criteria_data)} évaluations valides après filtrage")
            
            if not all_criteria_data:
                raise ValueError("Aucune évaluation ne satisfait les critères de base")
            
            # Normaliser et calculer scores composites
            normalized_data = self.criteria.normalize_criteria(all_criteria_data)
            
            # Trier par score composite (décroissant)
            sorted_data = sorted(normalized_data, key=lambda x: x['composite_score'], reverse=True)
            
            # Sélectionner le top N
            max_layouts = self.criteria.max_layouts
            selected_data = sorted_data[:max_layouts]
            
            logger.info(f"✅ {len(selected_data)} layouts sélectionnés (top {max_layouts})")
            
            # Afficher quelques statistiques
            self.print_selection_statistics(selected_data, all_criteria_data)
            
            # Générer les visualisations
            if self.config["pipeline_config"]["selection"].get("visualization", {}).get("generate_plots", False):
                self.visualizer.generate_all_visualizations(all_criteria_data, selected_data)
            
            # Copier les layouts sélectionnés
            selected_layout_ids = [d['layout_id'] for d in selected_data]
            self.copy_selected_layouts(selected_layout_ids)
            
            # Sauvegarder les résultats de sélection
            selection_results = {
                'selection_info': {
                    'timestamp': time.time(),
                    'selection_duration': time.time() - start_time,
                    'total_evaluations': len(evaluations),
                    'valid_evaluations': len(all_criteria_data),
                    'selected_layouts': len(selected_data),
                    'selection_rate': len(selected_data) / len(all_criteria_data) * 100
                },
                'criteria_weights': {
                    'efficiency': self.criteria.efficiency_weight,
                    'cooperation_gain': self.criteria.cooperation_gain_weight,
                    'exchanges_used': self.criteria.exchanges_weight
                },
                'selected_layouts': selected_data,
                'all_criteria_data': all_criteria_data  # Pour analyses ultérieures
            }
            
            self.save_selection_results(selection_results)
            
            selection_time = time.time() - start_time
            logger.info(f"🎉 Sélection terminée en {selection_time:.1f}s")
            
            return selection_results
            
        except Exception as e:
            logger.error(f"💥 Erreur durant la sélection: {e}", exc_info=True)
            raise
    
    def print_selection_statistics(self, selected_data: List[Dict], all_data: List[Dict]):
        """Affiche les statistiques de sélection."""
        logger.info(f"📊 Statistiques de sélection:")
        
        # Moyennes des sélectionnés vs tous
        selected_avg_steps = np.mean([d['duo_steps'] for d in selected_data])
        all_avg_steps = np.mean([d['duo_steps'] for d in all_data])
        
        selected_avg_coop = np.mean([d['cooperation_gain_percent'] for d in selected_data])
        all_avg_coop = np.mean([d['cooperation_gain_percent'] for d in all_data])
        
        selected_avg_exchanges = np.mean([d['exchanges_used'] for d in selected_data])
        all_avg_exchanges = np.mean([d['exchanges_used'] for d in all_data])
        
        selected_avg_score = np.mean([d['composite_score'] for d in selected_data])
        all_avg_score = np.mean([d['composite_score'] for d in all_data])
        
        logger.info(f"  • Steps duo: {selected_avg_steps:.1f} (sélectionnés) vs {all_avg_steps:.1f} (tous)")
        logger.info(f"  • Gain coopération: {selected_avg_coop:.1f}% (sélectionnés) vs {all_avg_coop:.1f}% (tous)")
        logger.info(f"  • Échanges: {selected_avg_exchanges:.1f} (sélectionnés) vs {all_avg_exchanges:.1f} (tous)")
        logger.info(f"  • Score composite: {selected_avg_score:.3f} (sélectionnés) vs {all_avg_score:.3f} (tous)")
        
        # Top 3 layouts
        logger.info(f"🏆 Top 3 layouts:")
        for i, layout in enumerate(selected_data[:3], 1):
            logger.info(f"  {i}. {layout['layout_id'][:12]}... - Score: {layout['composite_score']:.3f}")
    
    def copy_selected_layouts(self, layout_ids: List[str]):
        """Copie les layouts sélectionnés vers le dossier de sélection."""
        logger.info(f"📁 Copie de {len(layout_ids)} layouts sélectionnés...")
        
        copied_count = 0
        
        # Parcourir tous les fichiers de layouts générés
        for layout_file in self.layouts_generated_dir.glob("*.json"):
            try:
                with open(layout_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Filtrer les layouts sélectionnés
                if 'layouts' in data:
                    selected_layouts = [layout for layout in data['layouts'] 
                                      if layout.get('canonical_hash') in layout_ids]
                    
                    if selected_layouts:
                        # Générer les fichiers .layout individuels
                        for i, layout in enumerate(selected_layouts):
                            layout_id = layout.get('canonical_hash', f'layout_{copied_count + i}')
                            self.save_layout_file(layout, layout_id)
                            copied_count += 1
                
            except Exception as e:
                logger.warning(f"⚠️ Erreur copie {layout_file.name}: {e}")
        
        logger.info(f"✅ {copied_count} layouts copiés vers {self.layouts_selected_dir}")
    
    def save_layout_file(self, layout_data: Dict, layout_id: str):
        """Convertit et sauvegarde un layout au format .layout attendu."""
        try:
            # Extraire la grille et la formater correctement
            grid = layout_data.get('grid', '')
            
            # Format du grid avec indentation pour le fichier .layout
            formatted_grid = '"""' + grid.replace('\\n', '\n                ') + '"""'
            
            # Créer la structure .layout attendue
            layout_content = {
                "grid": formatted_grid,
                "start_all_orders": [
                    {"ingredients": ["onion"]}, 
                    {"ingredients": ["onion", "tomato"]}, 
                    {"ingredients": ["tomato", "tomato"]}, 
                    {"ingredients": ["onion", "onion", "tomato"]}, 
                    {"ingredients": ["onion", "tomato", "tomato"]}, 
                    {"ingredients": ["tomato", "tomato", "tomato"]}
                ],
                "counter_goals": [],
                "onion_value": 3,
                "tomato_value": 2,
                "onion_time": 9,
                "tomato_time": 6
            }
            
            # Sauvegarder le fichier .layout
            output_file = self.layouts_selected_dir / f"{layout_id}.layout"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                # Formater le fichier .layout avec la syntaxe attendue
                f.write("{\n")
                f.write(f'    "grid":  {formatted_grid},\n')
                f.write(f'    "start_all_orders": {json.dumps(layout_content["start_all_orders"])},\n')
                f.write(f'    "counter_goals": {json.dumps(layout_content["counter_goals"])},\n')
                f.write(f'    "onion_value": {layout_content["onion_value"]},\n')
                f.write(f'    "tomato_value": {layout_content["tomato_value"]},\n')
                f.write(f'    "onion_time": {layout_content["onion_time"]},\n')
                f.write(f'    "tomato_time": {layout_content["tomato_time"]}\n')
                f.write("}")
            
            logger.debug(f"  ✅ Layout {layout_id}.layout créé")
            
        except Exception as e:
            logger.error(f"❌ Erreur création {layout_id}.layout: {e}")
    
    def save_selection_results(self, results: Dict):
        """Sauvegarde les résultats de sélection."""
        timestamp = int(time.time())
        
        # Fichier JSON complet
        json_file = self.selection_analysis_dir / f"selection_results_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        # Rapport markdown
        markdown_file = self.selection_analysis_dir / f"selection_report_{timestamp}.md"
        self.generate_selection_report(results, markdown_file)
        
        # CSV des layouts sélectionnés
        csv_file = self.selection_analysis_dir / f"selected_layouts_{timestamp}.csv"
        self.export_selected_layouts_csv(results['selected_layouts'], csv_file)
        
        logger.info(f"💾 Résultats de sélection sauvegardés:")
        logger.info(f"  📄 JSON: {json_file.name}")
        logger.info(f"  📝 Rapport: {markdown_file.name}")
        logger.info(f"  📊 CSV: {csv_file.name}")
    
    def generate_selection_report(self, results: Dict, output_file: Path):
        """Génère un rapport markdown de la sélection."""
        selected = results['selected_layouts']
        info = results['selection_info']
        weights = results['criteria_weights']
        
        report_content = f"""# Rapport de Sélection Finale - Layouts Overcooked

Généré le: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 🎯 Critères de Sélection

Les layouts ont été sélectionnés selon **3 critères pondérés** :

1. **Efficacité** (poids: {weights['efficiency']:.0%}) - *À maximiser*
2. **Gain de coopération** (poids: {weights['cooperation_gain']:.0%}) - *À maximiser*  
3. **Échanges utilisés** (poids: {weights['exchanges_used']:.0%}) - *À optimiser*

## 📊 Résumé de la Sélection

- **Évaluations totales**: {info['total_evaluations']:,}
- **Évaluations valides**: {info['valid_evaluations']:,}
- **Layouts sélectionnés**: {info['selected_layouts']:,}
- **Taux de sélection**: {info['selection_rate']:.1f}%
- **Durée de sélection**: {info['selection_duration']:.1f}s

## 🏆 Top 10 Layouts Sélectionnés

| Rang | Layout ID | Score | Steps Duo | Gain Coop (%) | Échanges |
|------|-----------|-------|-----------|---------------|----------|
"""
        
        for i, layout in enumerate(selected[:10], 1):
            report_content += f"| {i} | `{layout['layout_id'][:12]}...` | {layout['composite_score']:.3f} | {layout['duo_steps']:.0f} | {layout['cooperation_gain_percent']:.1f}% | {layout['exchanges_used']} |\n"
        
        # Statistiques par critère
        steps_values = [d['duo_steps'] for d in selected]
        coop_values = [d['cooperation_gain_percent'] for d in selected]
        exchanges_values = [d['exchanges_used'] for d in selected]
        
        report_content += f"""

## 📈 Statistiques des Layouts Sélectionnés

### Steps en Mode Duo
- **Moyenne**: {np.mean(steps_values):.1f} steps
- **Médiane**: {np.median(steps_values):.1f} steps
- **Min-Max**: {np.min(steps_values):.0f} - {np.max(steps_values):.0f} steps

### Gain de Coopération
- **Moyenne**: {np.mean(coop_values):.1f}%
- **Médiane**: {np.median(coop_values):.1f}%
- **Min-Max**: {np.min(coop_values):.1f}% - {np.max(coop_values):.1f}%

### Échanges Utilisés
- **Moyenne**: {np.mean(exchanges_values):.1f} échanges
- **Médiane**: {np.median(exchanges_values):.1f} échanges
- **Min-Max**: {np.min(exchanges_values):.0f} - {np.max(exchanges_values):.0f} échanges

## 📊 Visualisations Générées

Les graphiques suivants ont été générés pour analyser la sélection :

1. **Scatter 3D** - Distribution des 3 critères dans l'espace
2. **Matrice de corrélation** - Relations entre les critères
3. **Distributions comparatives** - Sélectionnés vs tous les layouts
4. **Box plots** - Comparaison statistique des critères
5. **Analyse score composite** - Relation score vs critères individuels

## 🎯 Prochaines Étapes

1. Générer les **trajectoires détaillées** pour les {len(selected)} layouts sélectionnés
2. Effectuer des **tests de validation** sur un échantillon
3. **Intégrer** les layouts dans l'environnement de jeu
4. Analyser les **performances en conditions réelles**

---
*Rapport généré automatiquement par le sélecteur final professionnel*
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
    
    def export_selected_layouts_csv(self, selected_layouts: List[Dict], output_file: Path):
        """Exporte les layouts sélectionnés en CSV."""
        try:
            df = pd.DataFrame([
                {
                    'layout_id': d['layout_id'],
                    'recipe_group_id': d['recipe_group_id'],
                    'composite_score': d['composite_score'],
                    'duo_steps': d['duo_steps'],
                    'cooperation_gain_percent': d['cooperation_gain_percent'],
                    'exchanges_used': d['exchanges_used'],
                    'normalized_duo_steps': d['normalized_duo_steps'],
                    'normalized_cooperation': d['normalized_cooperation'],
                    'normalized_exchanges': d['normalized_exchanges']
                }
                for d in selected_layouts
            ])
            
            df.to_csv(output_file, index=False)
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur export CSV: {e}")

def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(description="Sélecteur final professionnel de layouts Overcooked")
    parser.add_argument("--config", default="config/pipeline_config.json", 
                       help="Fichier de configuration")
    parser.add_argument("--no-visualizations", action="store_true",
                       help="Désactiver la génération de visualisations")
    
    args = parser.parse_args()
    
    try:
        selector = ProfessionalFinalSelector(args.config)
        
        results = selector.perform_final_selection()
        
        selected_count = results['selection_info']['selected_layouts']
        selection_rate = results['selection_info']['selection_rate']
        
        logger.info("🎉 Sélection finale terminée avec succès!")
        logger.info(f"✅ {selected_count} layouts sélectionnés ({selection_rate:.1f}%)")
        logger.info("📊 Visualisations et rapports générés")
        
        return 0
    
    except Exception as e:
        logger.error(f"💥 Erreur critique: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main())
