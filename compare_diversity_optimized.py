#!/usr/bin/env python3
"""
Version optimisée pour l'analyse de diversité avec de grandes tailles d'ensembles.

Cette version utilise un échantillonnage pour éviter les problèmes de mémoire
avec de grandes combinaisons.
"""

import sys
import os
import matplotlib.pyplot as plt
import numpy as np
import random
from itertools import combinations
sys.path.append(os.path.dirname(__file__))

from recipe_generator import RecipeGenerator

def estimate_diversity_distribution_sampled(generator, n_combinations, orders, sample_size=10000):
    """
    Estime la distribution de diversité en échantillonnant un sous-ensemble.
    
    Args:
        generator: Le générateur de recettes
        n_combinations: Nombre de combinaisons par ensemble
        orders: Liste des combinaisons disponibles
        sample_size: Nombre d'échantillons à évaluer
    
    Returns:
        Tuple[List[float], List[int]]: Scores de diversité et leurs fréquences estimées
    """
    if n_combinations > len(orders):
        raise ValueError(f"Cannot select {n_combinations} combinations from {len(orders)} available")
    
    print(f"Estimation par échantillonnage pour ensembles de {n_combinations} combinaisons...")
    print(f"Total combinaisons disponibles: {len(orders)}")
    
    # Calculer le nombre total théorique d'ensembles
    from math import comb
    total_theoretical = comb(len(orders), n_combinations)
    print(f"Total théorique d'ensembles possibles: {total_theoretical:,}")
    print(f"Échantillonnage de {sample_size:,} ensembles ({100*sample_size/total_theoretical:.4f}%)")
    
    # Calculate diversity matrix
    diversity_matrix = generator.calculate_diversity_matrix(orders)
    
    # Échantillonner des ensembles aléatoires
    diversity_scores = []
    
    for _ in range(sample_size):
        # Sélectionner aléatoirement n_combinations indices
        sampled_indices = random.sample(range(len(orders)), n_combinations)
        
        # Calculer la diversité totale pour cet ensemble
        total_diversity = 0
        for i in sampled_indices:
            for j in sampled_indices:
                if j > i:  # Éviter le double comptage
                    total_diversity += diversity_matrix[i, j]
        diversity_scores.append(total_diversity)
    
    # Calculer la distribution des fréquences
    unique_scores, counts = np.unique(diversity_scores, return_counts=True)
    
    # Extrapoler les fréquences au total théorique
    extrapolated_counts = [int(count * total_theoretical / sample_size) for count in counts]
    
    print(f"Scores de diversité range: {min(diversity_scores)} - {max(diversity_scores)}")
    print(f"Nombre de scores uniques trouvés: {len(unique_scores)}")
    
    return list(unique_scores), extrapolated_counts, total_theoretical

def compare_diversity_distributions_optimized():
    """Version optimisée de la comparaison des distributions."""
    
    print("=== COMPARAISON OPTIMISÉE DES DISTRIBUTIONS DE DIVERSITÉ ===\n")
    
    # Initialiser le générateur avec 6 recettes par combinaison comme demandé
    generator = RecipeGenerator(onion_value=3, tomato_value=2, onion_time=9, tomato_time=6)
    
    print("Génération des combinaisons de 6 recettes...")
    generator.generate_combinations(combination_size=6)
    
    all_orders = list(generator.combinations.keys())
    print(f"Total de combinaisons disponibles: {len(all_orders)}")
    
    # Tailles d'ensembles à comparer (comme demandé)
    ensemble_sizes = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    
    # Collecter les données pour chaque taille
    results = {}
    sample_size = 50000  # Échantillon plus grand pour plus de précision
    
    for size in ensemble_sizes:
        if size <= len(all_orders):
            print(f"\nAnalyse pour des ensembles de {size} combinaisons...")
            try:
                # Utiliser la méthode exacte pour les petites tailles, échantillonnage pour les grandes
                from math import comb
                total_theoretical = comb(len(all_orders), size)
                
                if total_theoretical <= 1000000:  # 1 million - limite raisonnable pour calcul exact
                    print("  Calcul exact (nombre d'ensembles gérable)")
                    diversity_scores, frequencies = generator.calculate_set_diversity_distribution(
                        n_combinations=size,
                        orders=all_orders
                    )
                    total_sets = sum(frequencies)
                else:
                    print("  Calcul par échantillonnage (trop d'ensembles pour calcul exact)")
                    diversity_scores, frequencies, total_sets = estimate_diversity_distribution_sampled(
                        generator, size, all_orders, sample_size
                    )
                
                results[size] = {
                    'scores': diversity_scores,
                    'frequencies': frequencies,
                    'total_sets': total_sets,
                    'mean_diversity': np.average(diversity_scores, weights=frequencies),
                    'max_diversity': max(diversity_scores),
                    'min_diversity': min(diversity_scores),
                    'is_sampled': total_theoretical > 1000000
                }
                
                print(f"  - Diversité moyenne: {results[size]['mean_diversity']:.2f}")
                print(f"  - Diversité min-max: {results[size]['min_diversity']}-{results[size]['max_diversity']}")
                print(f"  - Total ensembles: {results[size]['total_sets']:,}")
                if results[size]['is_sampled']:
                    print(f"  - (Résultats basés sur échantillonnage)")
                
            except Exception as e:
                print(f"  Erreur pour taille {size}: {e}")
        else:
            print(f"\nPas assez de combinaisons pour des ensembles de {size}")
    
    # Créer une visualisation comparative
    if results:
        create_optimized_comparison_plot(results)
        create_summary_analysis(results)

def create_optimized_comparison_plot(results):
    """Crée un graphique comparatif optimisé."""
    
    # Graphique 1: Évolution de la diversité moyenne en fonction de la taille
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    
    sizes = list(results.keys())
    mean_diversities = [results[size]['mean_diversity'] for size in sizes]
    max_diversities = [results[size]['max_diversity'] for size in sizes]
    min_diversities = [results[size]['min_diversity'] for size in sizes]
    
    # Évolution de la diversité moyenne
    ax1.plot(sizes, mean_diversities, 'o-', linewidth=2, markersize=8, color='blue', label='Diversité moyenne')
    ax1.plot(sizes, max_diversities, 's--', linewidth=2, markersize=6, color='red', label='Diversité maximale')
    ax1.plot(sizes, min_diversities, '^--', linewidth=2, markersize=6, color='green', label='Diversité minimale')
    ax1.set_xlabel('Taille de l\'Ensemble')
    ax1.set_ylabel('Score de Diversité')
    ax1.set_title('Évolution de la Diversité selon la Taille de l\'Ensemble')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Nombre total d'ensembles possibles (échelle log)
    total_sets = [results[size]['total_sets'] for size in sizes]
    colors = ['blue' if not results[size]['is_sampled'] else 'orange' for size in sizes]
    
    ax2.bar(sizes, total_sets, color=colors, alpha=0.7)
    ax2.set_xlabel('Taille de l\'Ensemble')
    ax2.set_ylabel('Nombre Total d\'Ensembles')
    ax2.set_title('Nombre d\'Ensembles Possibles (Log Scale)')
    ax2.set_yscale('log')
    ax2.grid(True, alpha=0.3)
    
    # Légende pour les couleurs
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor='blue', label='Calcul exact'),
                      Patch(facecolor='orange', label='Échantillonnage')]
    ax2.legend(handles=legend_elements)
    
    # Distribution pour quelques tailles sélectionnées
    selected_sizes = [sizes[0], sizes[len(sizes)//2], sizes[-1]] if len(sizes) >= 3 else sizes
    
    for i, size in enumerate(selected_sizes[:2]):  # Limiter à 2 pour la lisibilité
        ax = ax3 if i == 0 else ax4
        data = results[size]
        
        ax.bar(data['scores'], data['frequencies'], alpha=0.7, 
               color=f'C{i}', edgecolor='navy')
        ax.set_xlabel('Score de Diversité')
        ax.set_ylabel('Nombre d\'Ensembles')
        
        title = f'Distribution - Ensembles de {size} combinaisons'
        if data['is_sampled']:
            title += ' (échantillonné)'
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        
        # Ajouter des statistiques
        stats_text = f'Total: {data["total_sets"]:,}\n'
        stats_text += f'Moy: {data["mean_diversity"]:.1f}\n'
        stats_text += f'Max: {data["max_diversity"]}'
        
        ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, 
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    plt.savefig('analyse_diversite_optimisee.png', dpi=300, bbox_inches='tight')
    plt.show()
    print("Graphique d'analyse optimisée sauvegardé: analyse_diversite_optimisee.png")

def create_summary_analysis(results):
    """Crée une analyse résumée des résultats."""
    
    print("\n" + "="*80)
    print("RÉSUMÉ COMPARATIF DÉTAILLÉ")
    print("="*80)
    print(f"{'Taille':<8} {'Total Sets':<15} {'Moy Div':<10} {'Min Div':<8} {'Max Div':<8} {'Méthode':<12}")
    print("-" * 80)
    
    for size, data in results.items():
        method = "Échantillonné" if data['is_sampled'] else "Exact"
        print(f"{size:<8} {data['total_sets']:<15,} {data['mean_diversity']:<10.2f} "
              f"{data['min_diversity']:<8} {data['max_diversity']:<8} {method:<12}")
    
    # Analyser les tendances
    sizes = list(results.keys())
    mean_diversities = [results[size]['mean_diversity'] for size in sizes]
    
    print(f"\n{'='*50}")
    print("ANALYSE DES TENDANCES")
    print(f"{'='*50}")
    
    # Croissance de la diversité moyenne
    if len(sizes) > 1:
        growth_rate = (mean_diversities[-1] - mean_diversities[0]) / (sizes[-1] - sizes[0])
        print(f"Taux de croissance de la diversité moyenne: {growth_rate:.2f} par unité de taille")
    
    # Rapport diversité max/min
    for size in sizes:
        data = results[size]
        ratio = data['max_diversity'] / data['min_diversity'] if data['min_diversity'] > 0 else float('inf')
        print(f"Taille {size}: Rapport max/min = {ratio:.2f}")

if __name__ == "__main__":
    try:
        # Fixer la graine pour la reproductibilité
        random.seed(42)
        np.random.seed(42)
        
        compare_diversity_distributions_optimized()
    except KeyboardInterrupt:
        print("\nAnalyse interrompue par l'utilisateur.")
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
