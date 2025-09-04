#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de vérification des recettes - aucun doublon autorisé
"""

import json
from pathlib import Path
from collections import defaultdict

def verify_no_duplicates():
    """Vérifie qu'il n'y a aucun doublon dans les recettes."""
    
    # Trouver le fichier le plus récent
    base_dir = Path(__file__).parent.parent
    recipe_files = list(base_dir.glob("outputs/base_recipes_*.json"))
    
    if not recipe_files:
        print("❌ Aucun fichier de recettes trouvé")
        return False
    
    latest_file = max(recipe_files, key=lambda f: f.stat().st_mtime)
    
    print(f"🔍 Vérification: {latest_file.name}")
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    recipes = data['recipes']
    
    print(f"📊 Analyse de {len(recipes)} recettes")
    print("="*50)
    
    # Analyser les signatures
    signatures = defaultdict(list)
    
    for recipe in recipes:
        ingredients = recipe['ingredients']
        onion_count = ingredients.count('onion')
        tomato_count = ingredients.count('tomato')
        signature = (onion_count, tomato_count)
        
        signatures[signature].append({
            'id': recipe['id'],
            'ingredients': ingredients,
            'type': recipe['type']
        })
    
    # Vérifier les doublons
    has_duplicates = False
    
    print("🔍 ANALYSE DES SIGNATURES:")
    for signature, recipe_list in sorted(signatures.items()):
        onion_count, tomato_count = signature
        print(f"\n📋 Signature ({onion_count} onions, {tomato_count} tomatoes):")
        
        if len(recipe_list) > 1:
            print(f"   ❌ DOUBLON DÉTECTÉ! {len(recipe_list)} recettes:")
            has_duplicates = True
        else:
            print(f"   ✅ Unique:")
        
        for recipe in recipe_list:
            print(f"      {recipe['id']}: {recipe['ingredients']} ({recipe['type']})")
    
    # Résumé
    print(f"\n📊 RÉSUMÉ:")
    print(f"   Total recettes: {len(recipes)}")
    print(f"   Signatures uniques: {len(signatures)}")
    
    if has_duplicates:
        print(f"   ❌ DOUBLONS DÉTECTÉS!")
        return False
    else:
        print(f"   ✅ AUCUN DOUBLON!")
        return True

if __name__ == "__main__":
    verify_no_duplicates()
