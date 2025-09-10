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
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logs_dir / 'layout_selection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class LayoutMetrics:
    """Métriques simplifiées pour un layout - 3 métriques seulement"""
    layout_id: str
    layout_hash: str
    recipe_group_id: int
    solo_steps: int
    duo_steps: int
    exchanges_count: int
    recipe_hash: str
    
    def step_reduction_percentage(self) -> float:
        """Facteur 1: Pourcentage de gain en nombre d'étapes (duo vs solo)"""
        if self.solo_steps <= 0:
            return 0.0
        reduction = max(0, self.solo_steps - self.duo_steps)
        return (reduction / self.solo_steps) * 100.0  # Pourcentage de 0 à 100
    
    def exchanges_count_raw(self) -> int:
        """Facteur 2: Nombre d'échanges réalisés dans la version duo"""
        return self.exchanges_count
    
    def duo_steps_total(self) -> int:
        """Facteur 3: Nombre total d'étapes nécessaires en duo"""
        return self.duo_steps

@dataclass
class LayoutCandidate:
    """Candidat layout avec ses métriques agrégées"""
    layout_id: str
    layout_hash: str
    grid: List[List[str]]
    object_positions: Dict[str, Tuple[int, int]]
    metrics_by_recipe: Dict[int, LayoutMetrics]
    
    def calculate_weighted_score(self, weights: Dict[str, float]) -> float:
        """
        Calcule le score pondéré simplifié basé sur 3 métriques uniquement:
        1. step_reduction_weight: Pourcentage de gain d'étapes (duo vs solo)
        2. exchanges_weight: Nombre d'échanges réalisés en duo  
        3. duo_steps_weight: Nombre total d'étapes en duo (inversé - moins c'est mieux)
        """
        if not self.metrics_by_recipe:
            return 0.0
        
        total_score = 0.0
        for metrics in self.metrics_by_recipe.values():
            # Facteur 1: Pourcentage de réduction d'étapes (0-100%) - normalisé 0-1
            step_reduction_pct = metrics.step_reduction_percentage()
            step_reduction_score = min(1.0, step_reduction_pct / 100.0)
            
            # Facteur 2: Nombre d'échanges - normalisé 0-1 (max 20 échanges)
            exchanges_score = min(1.0, metrics.exchanges_count_raw() / 20.0)
            
            # Facteur 3: Étapes duo - normalisé 0-1 (moins = mieux, entre 50-500 étapes)
            min_steps, max_steps = 50, 500
            duo_steps = metrics.duo_steps_total()
            duo_steps_score = max(0.0, min(1.0, (max_steps - duo_steps) / (max_steps - min_steps)))
            
            # Score pondéré final
            score = (
                step_reduction_score * weights.get('step_reduction_weight', 0.4) +  # 40% par défaut
                exchanges_score * weights.get('exchanges_weight', 0.4) +           # 40% par défaut  
                duo_steps_score * weights.get('duo_steps_weight', 0.2)             # 20% par défaut
            )
            
            total_score += score
        
        # Moyenne des scores par recette
        return total_score / len(self.metrics_by_recipe)
    
    def get_primary_recipe_group(self) -> int:
        """Retourne l'ID du groupe de recettes avec le meilleur score simplifié"""
        if not self.metrics_by_recipe:
            return 1
        
        # Trouver le groupe avec le meilleur pourcentage de réduction d'étapes
        best_group = max(self.metrics_by_recipe.items(), 
                        key=lambda x: x[1].step_reduction_percentage())
        return best_group[0]
    
    def average_step_reduction_percentage(self) -> float:
        """Pourcentage moyen de réduction d'étapes (métrique principale)"""
        if not self.metrics_by_recipe:
            return 0.0
        return sum(m.step_reduction_percentage() for m in self.metrics_by_recipe.values()) / len(self.metrics_by_recipe)
    
    def average_exchanges_count(self) -> float:
        """Nombre moyen d'échanges (métrique principale)"""
        if not self.metrics_by_recipe:
            return 0.0
        return sum(m.exchanges_count_raw() for m in self.metrics_by_recipe.values()) / len(self.metrics_by_recipe)
    
    def average_duo_steps(self) -> float:
        """Nombre moyen d'étapes en mode duo (métrique principale)"""
        if not self.metrics_by_recipe:
            return float('inf')
        return sum(m.duo_steps_total() for m in self.metrics_by_recipe.values()) / len(self.metrics_by_recipe)

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
        
        # Seuils de qualité simplifiés
        self.quality_thresholds = selection_config["quality_thresholds"]
        
        # Poids pour le calcul des scores - 3 métriques uniquement (valeurs par défaut)
        self.scoring_weights = {
            "step_reduction_percentage": 0.4,  # Importance de l'amélioration duo vs solo
            "exchanges_count": 0.3,            # Nombre d'échanges détectés
            "duo_steps_total": 0.3             # Efficacité totale en mode duo
        }
        
        # Override avec la config si elle existe
        if "scoring_weights" in selection_config:
            self.scoring_weights.update(selection_config["scoring_weights"])
        
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
                # Prendre la métrique avec le meilleur pourcentage de réduction d'étapes
                best_metric = max(metrics_list, key=lambda m: m.step_reduction_percentage())
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
        debug_stats = {
            'step_reduction': [],
            'exchanges': [],
            'duo_steps': []
        }
        
        for layout_hash, candidate in candidates.items():
            # Calculer le score pondéré
            score = candidate.calculate_weighted_score(self.scoring_weights)
            
            # Vérifier les seuils simplifiés
            avg_step_reduction = candidate.average_step_reduction_percentage()
            avg_exchanges = candidate.average_exchanges_count()
            avg_duo_steps = candidate.average_duo_steps()
            
            # Collecter les stats pour debug
            debug_stats['step_reduction'].append(avg_step_reduction)
            debug_stats['exchanges'].append(avg_exchanges)
            debug_stats['duo_steps'].append(avg_duo_steps)
            
            if (avg_step_reduction >= self.quality_thresholds["min_step_reduction_percentage"] and
                avg_exchanges >= self.quality_thresholds["min_exchanges_count"] and
                avg_duo_steps <= self.quality_thresholds["max_duo_steps"]):
                
                filtered[layout_hash] = candidate
        
        # Logs de debug pour comprendre les valeurs
        if debug_stats['step_reduction']:
            step_red_stats = debug_stats['step_reduction']
            exch_stats = debug_stats['exchanges']
            duo_stats = debug_stats['duo_steps']
            
            logger.info(f"📊 STATS RÉDUCTION ÉTAPES: min={min(step_red_stats):.1f}%, max={max(step_red_stats):.1f}%, moy={sum(step_red_stats)/len(step_red_stats):.1f}% (seuil: {self.quality_thresholds['min_step_reduction_percentage']}%)")
            logger.info(f"📊 STATS ÉCHANGES: min={min(exch_stats):.1f}, max={max(exch_stats):.1f}, moy={sum(exch_stats)/len(exch_stats):.1f} (seuil: {self.quality_thresholds['min_exchanges_count']})")
            logger.info(f"📊 STATS ÉTAPES DUO: min={min(duo_stats):.0f}, max={max(duo_stats):.0f}, moy={sum(duo_stats)/len(duo_stats):.0f} (seuil: {self.quality_thresholds['max_duo_steps']})")
        
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
        """Sélectionne les meilleurs layouts globalement selon les 3 métriques simplifiées"""
        
        # Calculer les scores avec tri prioritaire
        scored_candidates = []
        for candidate in candidates.values():
            score = candidate.calculate_weighted_score(self.scoring_weights)
            avg_exchanges = candidate.average_exchanges_count()
            avg_step_reduction = candidate.average_step_reduction_percentage()
            avg_duo_steps = candidate.average_duo_steps()
            
            # Critère de tri multi-niveaux simplifié :
            # 1. Nombre d'échanges moyens (priorité 1)
            # 2. Réduction d'étapes en pourcentage (priorité 2)  
            # 3. Moins d'étapes duo = mieux (priorité 3, inversé)
            # 4. Score global
            sort_key = (avg_exchanges, avg_step_reduction, -avg_duo_steps, score)
            scored_candidates.append((sort_key, candidate))
        
        # Trier par critères prioritaires (décroissant sauf duo_steps)
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        # Log des meilleurs candidats pour debugging
        logger.info("🎯 TOP CANDIDATS (échanges → réduction% → duo_steps) :")
        for i, (sort_key, candidate) in enumerate(scored_candidates[:min(5, len(scored_candidates))]):
            exchanges, reduction, neg_duo_steps, score = sort_key
            duo_steps = -neg_duo_steps
            logger.info(f"  #{i+1}: Échanges={exchanges:.1f}, Réduction={reduction:.1f}%, DuoSteps={duo_steps:.0f}, Score={score:.3f}")
        
        # Prendre les N meilleurs
        return [candidate for _, candidate in scored_candidates[:self.final_count]]
    
    def _select_best_per_recipe(self, candidates: Dict[str, LayoutCandidate]) -> List[LayoutCandidate]:
        """Sélectionne les meilleurs layouts en essayant de couvrir différents groupes de recettes"""
        
        # Grouper par groupes de recettes couverts
        recipe_coverage = defaultdict(list)
        
        for candidate in candidates.values():
            recipe_groups = tuple(sorted(candidate.metrics_by_recipe.keys()))
            score = candidate.calculate_weighted_score(self.scoring_weights)
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
            scored_candidates = [(candidate.calculate_weighted_score(self.scoring_weights), candidate) 
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
        # Utiliser la grille du candidat
        grid = candidate.grid
        
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
                                  key=lambda x: x[1].step_reduction_percentage())[0]
            
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
            score = candidate.calculate_weighted_score(self.scoring_weights)
            avg_step_reduction = candidate.average_step_reduction_percentage()
            avg_exchanges = candidate.average_exchanges_count()
            avg_duo_steps = candidate.average_duo_steps()
            
            logger.info(f"  ✅ {filename}: score={score:.3f}, réduction={avg_step_reduction:.1f}%, échanges={avg_exchanges:.1f}, steps={avg_duo_steps:.0f}")
        
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
            layout_summary = {
                "index": i + 1,
                "filename": f"L{i+1:02d}_{candidate.layout_hash[:8]}.layout",
                "layout_hash": candidate.layout_hash,
                "weighted_score": candidate.calculate_weighted_score(self.scoring_weights),
                "step_reduction_percentage": candidate.average_step_reduction_percentage(),
                "exchanges_count": candidate.average_exchanges_count(),
                "duo_steps": candidate.average_duo_steps(),
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
