#!/usr/bin/env python3
"""Test de décompression spécifique"""

import gzip
import json
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.append(str(Path(__file__).parent.parent))
from layout_compression import LayoutDecompressor

def main():
    print("🔍 TEST DÉCOMPRESSION SPÉCIFIQUE")
    
    # Charger un layout
    with gzip.open('outputs/layouts_generes/layout_batch_1.jsonl.gz', 'rt') as f:
        layout_data = json.loads(f.readline())
    
    print(f"📁 Layout original:")
    print(f"   Keys: {list(layout_data.keys())}")
    print(f"   Grid (base64): {layout_data['g'][:30]}...")
    print(f"   Object positions: {layout_data['op']}")
    print(f"   Hash: {layout_data['h']}")
    
    # Test décompression
    try:
        decompressor = LayoutDecompressor()
        decompressed = decompressor.decompress_layout(layout_data)
        
        print(f"\n✅ Décompression réussie:")
        print(f"   Grid shape: {len(decompressed['grid'])}x{len(decompressed['grid'][0])}")
        print(f"   Objects: {decompressed.get('objects', {})}")
        
        print(f"\n🗺️  Grille décompressée:")
        for i, row in enumerate(decompressed['grid']):
            print(f"   {i}: {''.join(row)}")
        
        # Test avec l'évaluateur
        print(f"\n🧪 Test avec OptimizedGameState:")
        
        # Import dynamique
        import importlib.util
        evaluator_path = Path(__file__).parent / "scripts" / "2_layout_evaluator.py"
        spec = importlib.util.spec_from_file_location("layout_evaluator", evaluator_path)
        evaluator_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(evaluator_module)
        
        OptimizedGameState = evaluator_module.OptimizedGameState
        
        # Créer l'état avec les données originales (format compressé)
        state = OptimizedGameState(layout_data, [])
        print(f"   ✅ État créé avec format compressé")
        print(f"   Grid shape: {len(state.layout)}x{len(state.layout[0])}")
        print(f"   Player positions: {state.player_positions}")
        print(f"   Pot position: {state.pot_position}")
        print(f"   Service position: {state.service_position}")
        
        print(f"\n🗺️  Grille dans l'état:")
        for i, row in enumerate(state.layout):
            print(f"   {i}: {''.join(row)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()
