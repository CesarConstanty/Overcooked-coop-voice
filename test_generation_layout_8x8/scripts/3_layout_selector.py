#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sélecteur de Layouts Overcooked
Sélectionne les meilleurs layouts basés sur les métriques d'évaluation et les convertit au format requis

Fonctionnalités:
1. Charge les résultats d'évaluation de tous les batches
2. Calcule des scores pondérés pour chaque layout
3. Sélectionne les N meilleurs layouts selon les critères de configuration
4. Convertit au format .layout standard du projet Overcooked
5. Sauvegarde dans le dossier layouts_finaux

Critères de sélection:
- Bénéfice de coopération (solo_steps vs duo_steps)
- Efficacité (nombre d'étapes duo)
- Potentiel d'échanges
- Diversité des layouts

Author: Assistant AI Expert
Date: Septembre 2025
"""

import json
import gzip
import base64
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
import argparse
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('layout_selection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class LayoutMetrics:
    """Métriques d'évaluation pour un layout"""
    layout_id: str
    layout_hash: str
    recipe_group_id: int
    solo_steps: int
    duo_steps: int
    exchanges_count: int
    optimal_y_positions: List[Tuple[int, int]]  # Nouvellement ajouté
    improvement_ratio: float
    evaluation_time: float
    recipe_hash: str
    
    def cooperation_benefit(self) -> float:
        """Calcule le bénéfice de la coopération (0-1, plus c'est haut, mieux c'est)"""
        if self.solo_steps <= 0:
            return 0.0
        return max(0, (self.solo_steps - self.duo_steps) / self.solo_steps)
    
    def efficiency_score(self) -> float:
        """Score d'efficacité basé sur le nombre d'étapes duo (0-1, plus c'est haut, mieux c'est)"""
        # Normaliser entre 50 et 500 étapes (gamme typique)
        min_steps, max_steps = 50, 500
        normalized = max(0, min(1, (max_steps - self.duo_steps) / (max_steps - min_steps)))
        return normalized
    
    def exchange_score(self) -> float:
        """Score d'échanges normalisé (0-1)"""
        # Normaliser entre 0 et 10 échanges
        max_exchanges = 10
        return min(1.0, self.exchanges_count / max_exchanges) if max_exchanges > 0 else 0

@dataclass
class LayoutCandidate:
    """Candidat layout avec ses métriques agrégées"""
    layout_id: str
    layout_hash: str
    grid: List[List[str]]
    object_positions: Dict[str, Tuple[int, int]]
    metrics_by_recipe: Dict[int, LayoutMetrics]
    
    def calculate_weighted_score(self, weights: Dict[str, float]) -> float:
        """Calcule le score pondéré global du layout"""
        if not self.metrics_by_recipe:
            return 0.0
        
        total_score = 0.0
        for metrics in self.metrics_by_recipe.values():
            cooperation = metrics.cooperation_benefit()
            efficiency = metrics.efficiency_score()
            exchanges = metrics.exchange_score()
            
            score = (cooperation * weights.get('cooperation', 0.4) +
                    efficiency * weights.get('efficiency', 0.35) +
                    exchanges * weights.get('exchanges', 0.25))
            
            total_score += score
        
        # Moyenne des scores par recette
        return total_score / len(self.metrics_by_recipe)
    
    def get_optimal_y_positions(self) -> List[Tuple[int, int]]:
        """Retourne les positions Y optimales consolidées de toutes les évaluations"""
        all_y_positions = []
        y_counts = {}
        
        # Compter les occurrences de chaque position Y
        for metrics in self.metrics_by_recipe.values():
            for pos in metrics.optimal_y_positions:
                pos_tuple = tuple(pos) if isinstance(pos, list) else pos
                y_counts[pos_tuple] = y_counts.get(pos_tuple, 0) + 1
        
        # Retourner les positions les plus fréquentes (top 2)
        sorted_positions = sorted(y_counts.items(), key=lambda x: x[1], reverse=True)
        return [pos for pos, count in sorted_positions[:2] if count > 0]
    
    def get_primary_recipe_group(self) -> int:
        """Retourne l'ID du groupe de recettes avec le meilleur score"""
        if not self.metrics_by_recipe:
            return 1
        
        # Trouver le groupe avec le meilleur ratio d'amélioration
        best_group = max(self.metrics_by_recipe.items(), 
                        key=lambda x: x[1].improvement_ratio)
        return best_group[0]
    
    def get_grid_with_y_positions(self) -> List[List[str]]:
        """Retourne la grille avec les positions Y optimales appliquées"""
        # Faire une copie de la grille originale
        grid_with_y = [row[:] for row in self.grid]
        
        # Appliquer les positions Y optimales
        y_positions = self.get_optimal_y_positions()
        for y, x in y_positions:
            if 0 <= y < len(grid_with_y) and 0 <= x < len(grid_with_y[0]):
                # Remplacer les murs intérieurs X par des zones d'échange Y
                if grid_with_y[y][x] == 'X':
                    grid_with_y[y][x] = 'Y'
        
        return grid_with_y
    
    def get_optimal_y_positions(self) -> List[Tuple[int, int]]:
        """Retourne les positions Y optimales consolidées de toutes les évaluations"""
        all_y_positions = []
        y_counts = {}
        
        # Compter les occurrences de chaque position Y
        for metrics in self.metrics_by_recipe.values():
            for pos in metrics.optimal_y_positions:
                pos_tuple = tuple(pos) if isinstance(pos, list) else pos
                y_counts[pos_tuple] = y_counts.get(pos_tuple, 0) + 1
        
        # Retourner les positions les plus fréquentes (top 2)
        sorted_positions = sorted(y_counts.items(), key=lambda x: x[1], reverse=True)
        return [pos for pos, count in sorted_positions[:2]]
    
    def get_grid_with_y_positions(self) -> List[List[str]]:
        """Retourne la grille avec les positions Y optimales appliquées"""
        # Copier la grille originale
        grid_with_y = [row[:] for row in self.grid]
        
        # Appliquer les positions Y optimales
        for pos in self.get_optimal_y_positions():
            y, x = pos
            if 0 <= y < len(grid_with_y) and 0 <= x < len(grid_with_y[0]):
                grid_with_y[y][x] = 'Y'
        
        return grid_with_y
    
    def average_cooperation_benefit(self) -> float:
        """Bénéfice de coopération moyen sur toutes les recettes"""
        if not self.metrics_by_recipe:
            return 0.0
        return sum(m.cooperation_benefit() for m in self.metrics_by_recipe.values()) / len(self.metrics_by_recipe)
    
    def average_duo_steps(self) -> float:
        """Nombre moyen d'étapes en mode duo"""
        if not self.metrics_by_recipe:
            return float('inf')
        return sum(m.duo_steps for m in self.metrics_by_recipe.values()) / len(self.metrics_by_recipe)

class LayoutDecompressor:
    """Décompresse les layouts stockés"""
    
    def decode_grid_from_base64(self, encoded_grid: str) -> List[List[str]]:
        """Décode une grille depuis base64"""
        grid_str = base64.b64decode(encoded_grid.encode('ascii')).decode('utf-8')
        lines = grid_str.strip().split('\n')
        return [list(line) for line in lines]
    
    def decompress_layout(self, compressed_layout: Dict) -> Dict:
        """Décompresse un layout"""
        grid = self.decode_grid_from_base64(compressed_layout['g'])
        
        return {
            'grid': grid,
            'hash': compressed_layout['h'],
            'object_positions': compressed_layout.get('op', {})
        }

class LayoutSelector:
    """Sélecteur principal de layouts"""
    
    def __init__(self, config_file: str = "config/pipeline_config.json"):
        """Initialise le sélecteur avec la configuration"""
        self.base_dir = Path(__file__).parent.parent
        self.config_file = self.base_dir / config_file
        self.config = self.load_config()
        
        # Configuration de sélection
        selection_config = self.config["pipeline_config"]["selection"]
        evaluation_config = self.config["pipeline_config"]["evaluation"]
        
        self.final_count = selection_config["final_count"]
        self.selection_method = selection_config["selection_method"]
        self.diversity_weight = selection_config["diversity_weight"]
        self.performance_weight = selection_config["performance_weight"]
        
        # Seuils de qualité
        self.quality_thresholds = selection_config["quality_thresholds"]
        
        # Poids pour le calcul des scores
        self.metric_weights = evaluation_config["metrics"]
        
        # Répertoires
        self.evaluation_dir = self.base_dir / "outputs" / evaluation_config["results_dir"]
        self.layouts_dir = self.base_dir / "outputs" / self.config["pipeline_config"]["output"]["layouts_generated_dir"]
        self.output_dir = self.base_dir / "outputs" / "layouts_finaux"
        
        # Décompresseur
        self.decompressor = LayoutDecompressor()
        
        logger.info(f"🎯 Sélecteur initialisé - Target: {self.final_count} layouts")
        logger.info(f"📁 Évaluations: {self.evaluation_dir}")
        logger.info(f"📁 Layouts: {self.layouts_dir}")
        logger.info(f"💾 Sortie: {self.output_dir}")
    
    def load_config(self) -> Dict:
        """Charge la configuration du pipeline"""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration non trouvée: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_evaluation_results(self) -> Dict[str, LayoutMetrics]:
        """Charge tous les résultats d'évaluation"""
        logger.info("📊 Chargement des résultats d'évaluation...")
        
        metrics_files = list(self.evaluation_dir.glob("evaluation_metrics_batch_*.json"))
        
        if not metrics_files:
            raise FileNotFoundError(f"Aucun fichier de métriques trouvé dans {self.evaluation_dir}")
        
        all_metrics = {}
        total_evaluations = 0
        
        for metrics_file in metrics_files:
            with open(metrics_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                for metric_data in data.get('metrics', []):
                    evaluation_id = metric_data['evaluation_id']
                    
                    metrics = LayoutMetrics(
                        layout_id=metric_data['layout_id'],
                        layout_hash=metric_data['layout_hash'],
                        recipe_group_id=metric_data['recipe_group_id'],
                        solo_steps=metric_data['solo_steps'],
                        duo_steps=metric_data['duo_steps'],
                        exchanges_count=metric_data['exchanges_count'],
                        optimal_y_positions=metric_data.get('optimal_y_positions', []),  # Nouvellement ajouté
                        improvement_ratio=metric_data['improvement_ratio'],
                        evaluation_time=metric_data['evaluation_time'],
                        recipe_hash=metric_data['recipe_hash']
                    )
                    
                    all_metrics[evaluation_id] = metrics
                    total_evaluations += 1
        
        logger.info(f"✅ {total_evaluations} évaluations chargées depuis {len(metrics_files)} fichiers")
        return all_metrics
    
    def load_layout_data(self) -> Dict[str, Dict]:
        """Charge les données des layouts depuis les fichiers compressés"""
        logger.info("📁 Chargement des données de layouts...")
        
        layout_files = list(self.layouts_dir.glob("layout_batch_*.jsonl.gz"))
        
        if not layout_files:
            raise FileNotFoundError(f"Aucun fichier de layout trouvé dans {self.layouts_dir}")
        
        layout_data = {}
        
        for layout_file in layout_files:
            try:
                with gzip.open(layout_file, 'rt', encoding='utf-8') as f:
                    for line in f:
                        compressed_layout = json.loads(line.strip())
                        layout_hash = compressed_layout['h']
                        
                        # Décompresser
                        decompressed = self.decompressor.decompress_layout(compressed_layout)
                        # Ajouter le hash original
                        decompressed['hash'] = layout_hash
                        layout_data[layout_hash] = decompressed
                        
            except Exception as e:
                logger.error(f"Erreur lors du chargement de {layout_file}: {e}")
        
        logger.info(f"✅ {len(layout_data)} layouts chargés")
        return layout_data
    
    def group_metrics_by_layout(self, all_metrics: Dict[str, LayoutMetrics]) -> Dict[str, LayoutCandidate]:
        """Groupe les métriques par layout"""
        logger.info("🔄 Groupement des métriques par layout...")
        
        layout_groups = defaultdict(lambda: defaultdict(list))
        
        # Grouper par layout_hash
        for evaluation_id, metrics in all_metrics.items():
            layout_groups[metrics.layout_hash][metrics.recipe_group_id].append(metrics)
        
        # Créer les candidats
        candidates = {}
        layout_data = self.load_layout_data()
        
        for layout_hash, recipe_groups in layout_groups.items():
            if layout_hash not in layout_data:
                logger.warning(f"Données manquantes pour layout {layout_hash}")
                continue
            
            # Prendre la meilleure métrique par groupe de recettes
            metrics_by_recipe = {}
            for recipe_group_id, metrics_list in recipe_groups.items():
                # Prendre la métrique avec le meilleur ratio d'amélioration
                best_metric = max(metrics_list, key=lambda m: m.improvement_ratio)
                metrics_by_recipe[recipe_group_id] = best_metric
            
            # Créer le candidat
            layout = layout_data[layout_hash]
            candidate = LayoutCandidate(
                layout_id=layout_hash,
                layout_hash=layout_hash,
                grid=layout['grid'],
                object_positions=layout.get('object_positions', {}),
                metrics_by_recipe=metrics_by_recipe
            )
            
            candidates[layout_hash] = candidate
        
        logger.info(f"✅ {len(candidates)} candidats créés")
        return candidates
    
    def filter_candidates(self, candidates: Dict[str, LayoutCandidate]) -> Dict[str, LayoutCandidate]:
        """Filtre les candidats selon les seuils de qualité"""
        logger.info("🔍 Filtrage des candidats selon les seuils de qualité...")
        
        filtered = {}
        
        for layout_hash, candidate in candidates.items():
            # Calculer le score pondéré
            weights = {k: v.get('weight', 0) for k, v in self.metric_weights.items()}
            score = candidate.calculate_weighted_score(weights)
            
            # Vérifier les seuils
            avg_cooperation = candidate.average_cooperation_benefit()
            avg_steps = candidate.average_duo_steps()
            
            if (score >= self.quality_thresholds["min_final_score"] and
                avg_cooperation >= self.quality_thresholds["min_cooperation_benefit"] and
                avg_steps < float('inf')):  # Remplacer max_complexity par une vérification simple
                
                filtered[layout_hash] = candidate
        
        logger.info(f"✅ {len(filtered)} candidats passent les filtres de qualité")
        return filtered
    
    def select_best_layouts(self, candidates: Dict[str, LayoutCandidate]) -> List[LayoutCandidate]:
        """Sélectionne les meilleurs layouts selon la méthode configurée"""
        logger.info(f"🎯 Sélection des {self.final_count} meilleurs layouts...")
        
        if self.selection_method == "best_per_recipe":
            return self._select_best_per_recipe(candidates)
        elif self.selection_method == "global_best":
            return self._select_global_best(candidates)
        else:
            logger.warning(f"Méthode de sélection inconnue: {self.selection_method}, utilisation de 'global_best'")
            return self._select_global_best(candidates)
    
    def _select_global_best(self, candidates: Dict[str, LayoutCandidate]) -> List[LayoutCandidate]:
        """Sélectionne les meilleurs layouts globalement"""
        weights = {k: v.get('weight', 0) for k, v in self.metric_weights.items()}
        
        # Calculer les scores et trier
        scored_candidates = []
        for candidate in candidates.values():
            score = candidate.calculate_weighted_score(weights)
            scored_candidates.append((score, candidate))
        
        # Trier par score décroissant
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        # Prendre les N meilleurs
        return [candidate for _, candidate in scored_candidates[:self.final_count]]
    
    def _select_best_per_recipe(self, candidates: Dict[str, LayoutCandidate]) -> List[LayoutCandidate]:
        """Sélectionne les meilleurs layouts en essayant de couvrir différents groupes de recettes"""
        weights = {k: v.get('weight', 0) for k, v in self.metric_weights.items()}
        
        # Grouper par groupes de recettes couverts
        recipe_coverage = defaultdict(list)
        
        for candidate in candidates.values():
            recipe_groups = tuple(sorted(candidate.metrics_by_recipe.keys()))
            score = candidate.calculate_weighted_score(weights)
            recipe_coverage[recipe_groups].append((score, candidate))
        
        # Sélectionner le meilleur de chaque groupe de recettes
        selected = []
        for recipe_groups, group_candidates in recipe_coverage.items():
            # Trier par score décroissant et prendre le meilleur
            group_candidates.sort(key=lambda x: x[0], reverse=True)
            selected.extend([candidate for _, candidate in group_candidates[:1]])
        
        # Si pas assez, compléter avec les meilleurs globalement
        if len(selected) < self.final_count:
            all_candidates = list(candidates.values())
            scored_candidates = [(candidate.calculate_weighted_score(weights), candidate) 
                               for candidate in all_candidates]
            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            
            selected_hashes = {c.layout_hash for c in selected}
            for _, candidate in scored_candidates:
                if len(selected) >= self.final_count:
                    break
                if candidate.layout_hash not in selected_hashes:
                    selected.append(candidate)
                    selected_hashes.add(candidate.layout_hash)
        
        return selected[:self.final_count]
    
    def convert_to_layout_format(self, candidate: LayoutCandidate, index: int) -> Dict:
        """Convertit un candidat au format .layout requis"""
        # Utiliser la grille avec les positions Y optimales
        grid = candidate.get_grid_with_y_positions()
        
        # Convertir la grille en string avec formatage spécial
        grid_lines = []
        for row in grid:
            line = ''.join(row)
            grid_lines.append(line)
        
        # Formatage avec indentation comme dans l'exemple
        grid_str = '"""' + grid_lines[0] + '\n'
        for line in grid_lines[1:]:
            grid_str += '                ' + line + '\n'
        grid_str = grid_str.rstrip('\n') + '"""'
        
        # Recettes par défaut basées sur la configuration
        start_all_orders = [
            {"ingredients": ["onion"]},
            {"ingredients": ["onion", "tomato"]}, 
            {"ingredients": ["tomato", "tomato"]},
            {"ingredients": ["onion", "onion", "tomato"]},
            {"ingredients": ["onion", "tomato", "tomato"]},
            {"ingredients": ["tomato", "tomato", "tomato"]}
        ]
        
        # Valeurs depuis la configuration
        recipe_config = self.config["pipeline_config"]["recipe_config"]
        base_values = recipe_config["base_values"]
        
        layout_dict = {
            "grid": grid_str,
            "start_all_orders": start_all_orders,
            "counter_goals": [],
            "onion_value": base_values["onion_value"],
            "tomato_value": base_values["tomato_value"],
            "onion_time": 9,
            "tomato_time": 6
        }
        
        return layout_dict
    
    def save_selected_layouts(self, selected_layouts: List[LayoutCandidate]):
        """Sauvegarde les layouts sélectionnés au format requis"""
        logger.info(f"💾 Sauvegarde des {len(selected_layouts)} layouts sélectionnés...")
        
        # Créer le répertoire de sortie
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Sauvegarder chaque layout
        for i, candidate in enumerate(selected_layouts):
            # Déterminer le groupe de recettes principal (celui avec le meilleur score)
            best_recipe_group = max(candidate.metrics_by_recipe.items(), 
                                  key=lambda x: x[1].improvement_ratio)[0]
            
            # Nom de fichier avec index, groupe de recettes et hash partiel
            filename = f"L{i+1:02d}_G{best_recipe_group:02d}_{candidate.layout_hash[:8]}.layout"
            filepath = self.output_dir / filename
            
            # Convertir au format requis
            layout_data = self.convert_to_layout_format(candidate, i)
            
            # Générer le contenu du fichier avec le bon formatage
            content = "{\n"
            content += f'    "grid":  {layout_data["grid"]},\n'
            content += f'    "start_all_orders": {json.dumps(layout_data["start_all_orders"])},\n'
            content += f'    "counter_goals":{json.dumps(layout_data["counter_goals"])},\n'
            content += f'    "onion_value" : {layout_data["onion_value"]},\n'
            content += f'    "tomato_value" : {layout_data["tomato_value"]},\n'
            content += f'    "onion_time" : {layout_data["onion_time"]},\n'
            content += f'    "tomato_time" : {layout_data["tomato_time"]}\n'
            content += "}"
            
            # Sauvegarder
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Calculer quelques statistiques pour le log
            weights = {k: v.get('weight', 0) for k, v in self.metric_weights.items()}
            score = candidate.calculate_weighted_score(weights)
            avg_coop = candidate.average_cooperation_benefit()
            avg_steps = candidate.average_duo_steps()
            
            logger.info(f"  ✅ {filename}: score={score:.3f}, coop={avg_coop:.3f}, steps={avg_steps:.1f}")
        
        # Sauvegarder un résumé de la sélection
        summary = {
            "selection_timestamp": time.time(),
            "total_selected": len(selected_layouts),
            "selection_method": self.selection_method,
            "final_count_target": self.final_count,
            "quality_thresholds": self.quality_thresholds,
            "layouts": []
        }
        
        for i, candidate in enumerate(selected_layouts):
            weights = {k: v.get('weight', 0) for k, v in self.metric_weights.items()}
            layout_summary = {
                "index": i + 1,
                "filename": f"L{i+1:02d}_{candidate.layout_hash[:8]}.layout",
                "layout_hash": candidate.layout_hash,
                "weighted_score": candidate.calculate_weighted_score(weights),
                "cooperation_benefit": candidate.average_cooperation_benefit(),
                "average_duo_steps": candidate.average_duo_steps(),
                "recipe_groups_covered": len(candidate.metrics_by_recipe),
                "total_evaluations": len(candidate.metrics_by_recipe)
            }
            summary["layouts"].append(layout_summary)
        
        summary_file = self.output_dir / "selection_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📊 Résumé sauvegardé: {summary_file}")
    
    def run_selection(self) -> bool:
        """Lance le processus de sélection complet"""
        start_time = time.time()
        
        try:
            # 1. Charger les résultats d'évaluation
            all_metrics = self.load_evaluation_results()
            
            # 2. Grouper par layout
            candidates = self.group_metrics_by_layout(all_metrics)
            
            # 3. Filtrer selon les critères de qualité
            filtered_candidates = self.filter_candidates(candidates)
            
            if len(filtered_candidates) == 0:
                logger.error("❌ Aucun candidat ne passe les filtres de qualité")
                return False
            
            # 4. Sélectionner les meilleurs
            selected_layouts = self.select_best_layouts(filtered_candidates)
            
            # 5. Sauvegarder
            self.save_selected_layouts(selected_layouts)
            
            selection_time = time.time() - start_time
            
            # Rapport final
            logger.info(f"✅ Sélection terminée en {selection_time:.1f}s")
            logger.info(f"📊 Résultats:")
            logger.info(f"   • {len(all_metrics)} évaluations analysées")
            logger.info(f"   • {len(candidates)} layouts candidats")
            logger.info(f"   • {len(filtered_candidates)} candidats qualifiés")
            logger.info(f"   • {len(selected_layouts)} layouts finaux sélectionnés")
            logger.info(f"💾 Layouts sauvegardés dans: {self.output_dir}")
            
            return True
            
        except Exception as e:
            logger.error(f"💥 Erreur lors de la sélection: {e}", exc_info=True)
            return False

def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(description="Sélecteur de layouts Overcooked")
    parser.add_argument("--config", default="config/pipeline_config.json",
                       help="Fichier de configuration")
    parser.add_argument("--count", type=int,
                       help="Nombre de layouts à sélectionner (override config)")
    
    args = parser.parse_args()
    
    try:
        selector = LayoutSelector(args.config)
        
        # Override du nombre si spécifié
        if args.count:
            selector.final_count = args.count
            logger.info(f"🎯 Nombre overridé: {args.count} layouts")
        
        success = selector.run_selection()
        
        if success:
            logger.info("🎉 Sélection réussie!")
            return 0
        else:
            logger.error("❌ Échec de la sélection")
            return 1
    
    except Exception as e:
        logger.error(f"💥 Erreur critique: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    import time
    exit(main())
