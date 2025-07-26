#!/usr/bin/env python3
"""
Comparaison des distributions de diversité pour différentes tailles d'ensembles.

Ce script permet de voir comment la distribution de diversité change selon 
la taille des ensembles de recettes sélectionnés.
"""

import sys
import os
import matplotlib.pyplot as plt
import numpy as np
sys.path.append(os.path.dirname(__file__))

from recipe_generator import RecipeGenerator

def compare_diversity_distributions():
    """Compare les distributions de diversité pour différentes tailles d'ensembles."""
    
    print("=== COMPARAISON DES DISTRIBUTIONS DE DIVERSITÉ ===\n")
    
    # Initialiser le générateur
    generator = RecipeGenerator(onion_value=3, tomato_value=2, onion_time=9, tomato_time=6)
    
    # Générer des combinaisons plus petites pour que ce soit plus rapide
    print("Génération des combinaisons de 4 recettes...")
    generator.generate_combinations(combination_size=4)
    
    all_orders = list(generator.combinations.keys())
    print(f"Total de combinaisons disponibles: {len(all_orders)}")
    
    # Tailles d'ensembles à comparer
    ensemble_sizes = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    
    # Collecter les données pour chaque taille
    results = {}
    
    for size in ensemble_sizes:
        if size <= len(all_orders):
            print(f"\nAnalyse pour des ensembles de {size} combinaisons...")
            try:
                diversity_scores, frequencies = generator.calculate_set_diversity_distribution(
                    n_combinations=size,
                    orders=all_orders
                )
                results[size] = {
                    'scores': diversity_scores,
                    'frequencies': frequencies,
                    'total_sets': sum(frequencies),
                    'mean_diversity': np.average(diversity_scores, weights=frequencies),
                    'max_diversity': max(diversity_scores),
                    'min_diversity': min(diversity_scores)
                }
                print(f"  - Diversité moyenne: {results[size]['mean_diversity']:.2f}")
                print(f"  - Diversité min-max: {results[size]['min_diversity']}-{results[size]['max_diversity']}")
                print(f"  - Total ensembles: {results[size]['total_sets']:,}")
            except Exception as e:
                print(f"  Erreur pour taille {size}: {e}")
        else:
            print(f"\nPas assez de combinaisons pour des ensembles de {size}")
    
    # Créer une visualisation comparative
    if results:
        create_comparison_plot(results)
        
        # Afficher un résumé comparatif
        print("\n" + "="*60)
        print("RÉSUMÉ COMPARATIF")
        print("="*60)
        print(f"{'Taille':<8} {'Total Sets':<12} {'Moy Div':<10} {'Min Div':<8} {'Max Div':<8}")
        print("-" * 60)
        
        for size, data in results.items():
            print(f"{size:<8} {data['total_sets']:<12,} {data['mean_diversity']:<10.2f} "
                  f"{data['min_diversity']:<8} {data['max_diversity']:<8}")

def create_comparison_plot(results):
    """Crée un graphique comparatif des distributions."""
    
    fig, axes = plt.subplots(len(results), 2, figsize=(15, 4 * len(results)))
    
    if len(results) == 1:
        axes = axes.reshape(1, -1)
    
    colors = ['skyblue', 'lightcoral', 'lightgreen', 'wheat', 'lightpink']
    
    for idx, (size, data) in enumerate(results.items()):
        color = colors[idx % len(colors)]
        
        # Distribution des fréquences
        ax1 = axes[idx, 0]
        ax1.bar(data['scores'], data['frequencies'], alpha=0.7, color=color, edgecolor='navy')
        ax1.set_title(f'Distribution - Ensembles de {size} recettes')
        ax1.set_xlabel('Score de Diversité')
        ax1.set_ylabel('Nombre d\'Ensembles')
        ax1.grid(True, alpha=0.3)
        
        # Ajouter des statistiques
        stats_text = f'Total: {data["total_sets"]:,}\n'
        stats_text += f'Moy: {data["mean_diversity"]:.1f}\n'
        stats_text += f'Max: {data["max_diversity"]}'
        
        ax1.text(0.05, 0.95, stats_text, transform=ax1.transAxes, 
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        # Distribution cumulative
        ax2 = axes[idx, 1]
        cumulative_freq = np.cumsum(data['frequencies'])
        cumulative_percent = 100 * cumulative_freq / data['total_sets']
        
        ax2.plot(data['scores'], cumulative_percent, marker='o', linewidth=2, 
                markersize=4, color=color.replace('light', ''))
        ax2.set_title(f'Distribution Cumulative - Ensembles de {size} recettes')
        ax2.set_xlabel('Score de Diversité')
        ax2.set_ylabel('Pourcentage Cumulé (%)')
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, 100)
        
        # Ligne médiane
        median_idx = np.searchsorted(cumulative_percent, 50)
        if median_idx < len(data['scores']):
            ax2.axhline(y=50, color='red', linestyle='--', alpha=0.7)
            ax2.axvline(x=data['scores'][median_idx], color='red', linestyle='--', alpha=0.7)
            ax2.text(data['scores'][median_idx], 52, f'Médiane', 
                    ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    plt.savefig('comparaison_distributions_diversite.png', dpi=300, bbox_inches='tight')
    plt.show()
    print("Graphique de comparaison sauvegardé: comparaison_distributions_diversite.png")

if __name__ == "__main__":
    try:
        compare_diversity_distributions()
    except KeyboardInterrupt:
        print("\nAnalyse interrompue par l'utilisateur.")
    except Exception as e:
        print(f"Erreur: {e}")
