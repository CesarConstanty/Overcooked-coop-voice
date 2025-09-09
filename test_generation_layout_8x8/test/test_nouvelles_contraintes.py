#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test pour visualiser et valider les nouveaux layouts générés
"""

import json
import gzip
import base64
from pathlib import Path

def decode_grid_from_base64(encoded_grid: str) -> list:
    """Décode une grille depuis base64"""
    grid_str = base64.b64decode(encoded_grid.encode('ascii')).decode('utf-8')
    lines = grid_str.strip().split('\n')
    return [list(line) for line in lines]

def print_grid(grid: list, title: str = "Layout"):
    """Affiche une grille de façon lisible"""
    print(f"\n{title}:")
    print("+" + "-" * len(grid[0]) + "+")
    for row in grid:
        print("|" + "".join(row) + "|")
    print("+" + "-" * len(grid[0]) + "+")

def analyze_layout(grid: list) -> dict:
    """Analyse un layout et retourne ses caractéristiques"""
    analysis = {
        'empty_cells': 0,
        'walls': 0,
        'objects': {},
        'serving_on_border': False,
        'players_positions': [],
        'exchanges_zones': 0
    }
    
    height, width = len(grid), len(grid[0])
    
    for i, row in enumerate(grid):
        for j, cell in enumerate(row):
            if cell == ' ':
                analysis['empty_cells'] += 1
            elif cell == 'X':
                analysis['walls'] += 1
            elif cell == 'Y':
                analysis['exchanges_zones'] += 1
            elif cell in ['1', '2']:
                analysis['players_positions'].append((i, j, cell))
                # Les cases des joueurs sont aussi des cases vides (navigables)
                analysis['empty_cells'] += 1
            elif cell in ['O', 'T', 'P', 'D', 'S']:
                analysis['objects'][cell] = (i, j)
                
                # Vérifier si S est sur la bordure
                if cell == 'S':
                    is_on_border = (i == 0 or i == height-1 or j == 0 or j == width-1)
                    analysis['serving_on_border'] = is_on_border
    
    return analysis

def main():
    """Test complet des nouveaux layouts"""
    print("🧪 TEST DES NOUVEAUX LAYOUTS GÉNÉRÉS")
    print("=" * 50)
    
    # Charger la configuration pour connaître le nombre attendu de cellules vides
    config_file = Path("config/pipeline_config.json")
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        expected_empty_cells = config.get('pipeline_config', {}).get('generation', {}).get('layout_constraints', {}).get('empty_cells', 20)
        print(f"📋 Configuration: {expected_empty_cells} cellules vides attendues")
    except Exception as e:
        print(f"⚠️  Impossible de lire la configuration: {e}")
        expected_empty_cells = 20
    
    # Charger les layouts
    layouts_file = Path("outputs/layouts_generes/layout_batch_1.jsonl.gz")
    
    if not layouts_file.exists():
        print("❌ Aucun fichier de layout trouvé")
        return 1
    
    layouts = []
    with gzip.open(layouts_file, 'rt', encoding='utf-8') as f:
        for line in f:
            layouts.append(json.loads(line.strip()))
    
    print(f"📊 {len(layouts)} layouts à analyser\n")
    
    all_valid = True
    
    for i, layout_data in enumerate(layouts):
        # Décompresser la grille
        grid = decode_grid_from_base64(layout_data['g'])
        
        # Analyser
        analysis = analyze_layout(grid)
        
        # Afficher le layout
        print_grid(grid, f"Layout {i+1} (Hash: {layout_data['h'][:8]})")
        
        # Vérifications
        errors = []
        
        # 1. Vérifier le nombre de cellules vides (selon la configuration)
        if analysis['empty_cells'] != expected_empty_cells:
            errors.append(f"Cellules vides: {analysis['empty_cells']}/{expected_empty_cells}")
        
        # 2. Vérifier que S est sur la bordure
        if not analysis['serving_on_border']:
            errors.append("Station S pas sur la bordure")
        
        # 3. Vérifier qu'il n'y a pas de zones d'échange Y
        if analysis['exchanges_zones'] > 0:
            errors.append(f"{analysis['exchanges_zones']} zones d'échange Y détectées")
        
        # 4. Vérifier que les joueurs ne sont pas sur les bordures
        for pos_i, pos_j, player in analysis['players_positions']:
            if pos_i == 0 or pos_i == 7 or pos_j == 0 or pos_j == 7:
                errors.append(f"Joueur {player} sur bordure: ({pos_i},{pos_j})")
        
        # 5. Vérifier tous les objets requis
        required = ['O', 'T', 'P', 'D', 'S']
        for obj in required:
            if obj not in analysis['objects']:
                errors.append(f"Objet manquant: {obj}")
        
        # Afficher les résultats
        print(f"📊 Analyse Layout {i+1}:")
        print(f"   • Cellules vides: {analysis['empty_cells']}")
        print(f"   • Murs: {analysis['walls']}")
        print(f"   • Station S sur bordure: {'✅' if analysis['serving_on_border'] else '❌'}")
        print(f"   • Zones d'échange Y: {analysis['exchanges_zones']}")
        print(f"   • Joueurs: {len(analysis['players_positions'])}")
        print(f"   • Objets: {list(analysis['objects'].keys())}")
        
        if errors:
            print(f"❌ Erreurs détectées:")
            for error in errors:
                print(f"     • {error}")
            all_valid = False
        else:
            print(f"✅ Layout valide!")
        
        print()
    
    # Résultat final
    print("=" * 50)
    if all_valid:
        print("🎉 TOUS LES LAYOUTS RESPECTENT LES NOUVELLES CONTRAINTES!")
        print("✅ S sur bordure extérieure")
        print("✅ Joueurs jamais sur bordure") 
        print("✅ Pas de zones Y en génération")
        print("✅ Nombre exact de cellules vides")
        return 0
    else:
        print("⚠️  CERTAINS LAYOUTS NE RESPECTENT PAS LES CONTRAINTES")
        return 1

if __name__ == "__main__":
    exit(main())
