#!/usr/bin/env python3
"""
Script de rotation des layouts Overcooked
Applique des rotations à 90°, 180° et 270° aux layouts du dossier generation_cesar

Auteur: Agent IA
Date: Août 2025
"""

import json
import os
import re
from typing import Dict, List, Tuple, Optional
import shutil


def parse_layout_manually(content: str) -> Dict:
    """Parse manuellement un fichier layout avec format spécial"""
    # Extraire la grille entre les triple quotes
    grid_match = re.search(r'"grid":\s*"""([^"]+)"""', content, re.DOTALL)
    if not grid_match:
        raise ValueError("Impossible de trouver la grille dans le fichier")
    
    grid_str = grid_match.group(1).strip()
    
    # Extraire les autres champs avec regex
    def extract_field(field_name, content):
        pattern = rf'"{field_name}":\s*([^,}}]+)'
        match = re.search(pattern, content)
        if match:
            value_str = match.group(1).strip()
            if value_str.startswith('['):
                return json.loads(value_str)
            else:
                try:
                    return int(value_str)
                except:
                    return value_str.strip('"')
        return None
    
    result = {
        'grid': grid_str,
        'start_all_orders': extract_field('start_all_orders', content),
        'counter_goals': extract_field('counter_goals', content),
        'onion_value': extract_field('onion_value', content),
        'tomato_value': extract_field('tomato_value', content),
        'onion_time': extract_field('onion_time', content),
        'tomato_time': extract_field('tomato_time', content),
    }
    
    return result


def load_layout_file(filepath: str) -> Dict:
    """Charge un fichier layout avec support des chaînes multi-lignes Python"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Traiter le contenu comme du code Python pour gérer les """
    # Mais d'abord, on va extraire la grid de manière plus robuste
    try:
        # Méthode sécurisée : eval avec un namespace limité
        safe_dict = {"__builtins__": {}}
        result = eval(content, safe_dict)
        return result
    except:
        # Fallback : parsing manuel
        return parse_layout_manually(content)


def parse_grid_to_matrix(grid_str: str) -> List[List[str]]:
    """Convertit une grille string en matrice de caractères"""
    lines = [line.strip() for line in grid_str.strip().split('\n')]
    # Enlever les lignes vides
    lines = [line for line in lines if line]
    
    # Trouver la largeur maximale
    max_width = max(len(line) for line in lines) if lines else 0
    
    # Normaliser toutes les lignes à la même largeur
    matrix = []
    for line in lines:
        # Compléter avec des espaces si nécessaire
        normalized_line = line.ljust(max_width)
        matrix.append(list(normalized_line))
    
    return matrix


def matrix_to_grid_string(matrix: List[List[str]]) -> str:
    """Convertit une matrice de caractères en string de grille formatée"""
    if not matrix or not matrix[0]:
        return ""
    
    lines = []
    for row in matrix:
        # Enlever les espaces en fin de ligne
        line = ''.join(row).rstrip()
        lines.append(line)
    
    # Formater avec l'indentation appropriée
    formatted_lines = []
    for i, line in enumerate(lines):
        if i == 0:
            formatted_lines.append(line)
        else:
            formatted_lines.append(" " * 16 + line)
    
    return '\n'.join(formatted_lines)


def rotate_matrix_90(matrix: List[List[str]]) -> List[List[str]]:
    """Effectue une rotation de 90° dans le sens horaire"""
    if not matrix or not matrix[0]:
        return matrix
    
    rows = len(matrix)
    cols = len(matrix[0])
    
    # Nouvelle matrice avec dimensions inversées
    rotated = [[' ' for _ in range(rows)] for _ in range(cols)]
    
    for i in range(rows):
        for j in range(cols):
            # Rotation 90° horaire: (i,j) -> (j, rows-1-i)
            rotated[j][rows-1-i] = matrix[i][j]
    
    return rotated


def rotate_matrix_180(matrix: List[List[str]]) -> List[List[str]]:
    """Effectue une rotation de 180°"""
    if not matrix or not matrix[0]:
        return matrix
    
    rows = len(matrix)
    cols = len(matrix[0])
    
    rotated = [[' ' for _ in range(cols)] for _ in range(rows)]
    
    for i in range(rows):
        for j in range(cols):
            # Rotation 180°: (i,j) -> (rows-1-i, cols-1-j)
            rotated[rows-1-i][cols-1-j] = matrix[i][j]
    
    return rotated


def rotate_matrix_270(matrix: List[List[str]]) -> List[List[str]]:
    """Effectue une rotation de 270° dans le sens horaire (ou 90° anti-horaire)"""
    if not matrix or not matrix[0]:
        return matrix
    
    rows = len(matrix)
    cols = len(matrix[0])
    
    # Nouvelle matrice avec dimensions inversées
    rotated = [[' ' for _ in range(rows)] for _ in range(cols)]
    
    for i in range(rows):
        for j in range(cols):
            # Rotation 270° horaire: (i,j) -> (cols-1-j, i)
            rotated[cols-1-j][i] = matrix[i][j]
    
    return rotated


def rotate_grid(grid_str: str, angle: int) -> str:
    """Effectue une rotation de la grille selon l'angle spécifié"""
    matrix = parse_grid_to_matrix(grid_str)
    
    if angle == 90:
        rotated_matrix = rotate_matrix_90(matrix)
    elif angle == 180:
        rotated_matrix = rotate_matrix_180(matrix)
    # elif angle == 270:
    #    rotated_matrix = rotate_matrix_270(matrix)
    else:
        raise ValueError(f"Angle de rotation non supporté: {angle}")
    
    return matrix_to_grid_string(rotated_matrix)


def save_layout_file(layout_data: Dict, output_path: str) -> None:
    """Sauvegarde un fichier layout au format correct"""
    
    # Créer le contenu formaté
    content = "{\n"
    content += f'    "grid":  """{layout_data["grid"]}""",\n'
    content += f'    "start_all_orders": {json.dumps(layout_data["start_all_orders"])},\n'
    content += f'    "counter_goals":{json.dumps(layout_data["counter_goals"])},\n'
    content += f'    "onion_value" : {layout_data["onion_value"]},\n'
    content += f'    "tomato_value" : {layout_data["tomato_value"]},\n'
    content += f'    "onion_time" : {layout_data["onion_time"]},\n'
    content += f'    "tomato_time" : {layout_data["tomato_time"]}\n'
    content += "}"
    
    # Sauvegarder
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)


def extract_layout_name_parts(filename: str) -> Tuple[str, str]:
    """Extrait les parties du nom de fichier layout"""
    # Format attendu: LX_RYY_VZZ.layout
    base_name = filename.replace('.layout', '')
    return base_name, '.layout'


def create_rotated_filename(original_filename: str, angle: int) -> str:
    """Crée le nom du fichier rotaté"""
    base_name, extension = extract_layout_name_parts(original_filename)
    return f"{base_name}_R{angle}{extension}"


def rotate_single_layout(input_path: str, output_dir: str, filename: str) -> Dict[str, bool]:
    """Effectue les rotations d'un seul layout"""
    results = {"90": False, "180": False}
    
    try:
        # Charger le layout original
        layout_data = load_layout_file(input_path)
        original_grid = layout_data['grid']
        
        print(f"  📋 Grille originale:")
        print(f"     {original_grid.replace(chr(10), chr(10) + '     ')}")
        
        # Effectuer les 2 rotations demandées (90° et 180°)
        for angle in [90, 180]:
            try:
                # Effectuer la rotation
                rotated_grid = rotate_grid(original_grid, angle)
                
                # Créer les nouvelles données de layout
                rotated_layout = layout_data.copy()
                rotated_layout['grid'] = rotated_grid
                
                # Générer le nom de fichier de sortie
                output_filename = create_rotated_filename(filename, angle)
                output_path = os.path.join(output_dir, output_filename)
                
                # Sauvegarder
                save_layout_file(rotated_layout, output_path)
                
                results[str(angle)] = True
                print(f"  ✅ Rotation {angle}° sauvegardée: {output_filename}")
                print(f"     Grille {angle}°:")
                print(f"     {rotated_grid.replace(chr(10), chr(10) + '     ')}")
                
            except Exception as e:
                print(f"  ❌ Erreur rotation {angle}°: {e}")
                results[str(angle)] = False
    
    except Exception as e:
        print(f"  ❌ Erreur chargement layout: {e}")
    
    return results


def process_all_layouts(source_dir: str, output_dir: str) -> None:
    """Traite tous les layouts du dossier source"""
    
    # Vérifier que le dossier source existe
    if not os.path.exists(source_dir):
        print(f"❌ Dossier source introuvable: {source_dir}")
        return
    
    # Créer le dossier de sortie
    os.makedirs(output_dir, exist_ok=True)
    
    # Obtenir tous les fichiers .layout
    layout_files = [f for f in os.listdir(source_dir) if f.endswith('.layout')]
    
    if not layout_files:
        print(f"❌ Aucun fichier .layout trouvé dans {source_dir}")
        return
    
    print(f"🔄 Traitement de {len(layout_files)} layouts...")
    print(f"📂 Source: {source_dir}")
    print(f"📂 Destination: {output_dir}")
    
    total_layouts = len(layout_files)
    successful_rotations = {"90": 0, "180": 0}
    
    # Traiter chaque layout
    for i, filename in enumerate(sorted(layout_files), 1):
        input_path = os.path.join(source_dir, filename)
        
        print(f"\n[{i}/{total_layouts}] 🎯 {filename}")
        
        # Effectuer les rotations
        results = rotate_single_layout(input_path, output_dir, filename)
        
        # Compter les succès
        for angle, success in results.items():
            if success:
                successful_rotations[angle] += 1
    
    # Résumé final
    print(f"\n🎉 Traitement terminé!")
    print(f"   📊 Layouts traités: {total_layouts}")
    for angle, count in successful_rotations.items():
        success_rate = (count / total_layouts) * 100 if total_layouts > 0 else 0
        print(f"   🔄 Rotations {angle}° réussies: {count}/{total_layouts} ({success_rate:.1f}%)")
    
    print(f"   📂 Fichiers générés dans: {output_dir}")


def test_single_rotation():
    """Test sur un seul layout pour vérification"""
    source_dir = "/home/cesar/projet_python/Overcooked-coop-voice/overcooked_ai_py/data/layouts/generation_cesar"
    test_file = "Ldd18_R04_V00.layout"  # Un des fichiers existants
    test_path = os.path.join(source_dir, test_file)
    
    if not os.path.exists(test_path):
        print(f"❌ Fichier de test introuvable: {test_path}")
        # Essayer avec le premier fichier disponible
        layout_files = [f for f in os.listdir(source_dir) if f.endswith('.layout')]
        if layout_files:
            test_file = layout_files[0]
            test_path = os.path.join(source_dir, test_file)
            print(f"🔄 Utilisation de {test_file} à la place")
        else:
            print("❌ Aucun fichier layout trouvé dans le dossier")
            return
    
    print("🧪 TEST DE ROTATION")
    print("=" * 50)
    
    # Dossier de test temporaire
    test_output_dir = "/tmp/test_rotations"
    os.makedirs(test_output_dir, exist_ok=True)
    
    # Effectuer le test
    results = rotate_single_layout(test_path, test_output_dir, test_file)
    
    print(f"\n📋 Résultats du test:")
    for angle, success in results.items():
        status = "✅" if success else "❌"
        print(f"   {status} Rotation {angle}°")
    
    # Afficher les fichiers générés
    if any(results.values()):
        print(f"\n📁 Fichiers générés dans {test_output_dir}:")
        for f in os.listdir(test_output_dir):
            if test_file.replace('.layout', '') in f:
                print(f"   📄 {f}")


def main():
    """Fonction principale"""
    print("🔄 GÉNÉRATEUR DE ROTATIONS DE LAYOUTS OVERCOOKED")
    print("=" * 60)
    
    # Chemins - sauvegarde dans le même dossier source
    source_dir = "/home/cesar/projet_python/Overcooked-coop-voice/overcooked_ai_py/data/layouts/generation_cesar"
    output_dir = "/home/cesar/projet_python/Overcooked-coop-voice/overcooked_ai_py/data/layouts/generation_cesar"  # Même dossier
    
    # Demander le mode d'exécution
    print("Mode d'exécution:")
    print("1. Test sur un seul layout")
    print("2. Traitement complet")
    
    choice = input("Choisir (1/2): ").strip()
    
    if choice == "1":
        test_single_rotation()
    elif choice == "2":
        # Confirmation pour traitement complet
        print(f"\n📂 Source: {source_dir}")
        print(f"📂 Destination: {output_dir}")
        
        # Compter les layouts à traiter
        if os.path.exists(source_dir):
            layout_count = len([f for f in os.listdir(source_dir) if f.endswith('.layout')])
            print(f"📊 {layout_count} layouts seront traités")
            print(f"🔄 {layout_count * 2} fichiers seront générés (2 rotations par layout)")
        
        confirm = input("\n🚀 Continuer? (y/N): ").strip().lower()
        if confirm == 'y':
            process_all_layouts(source_dir, output_dir)
        else:
            print("👋 Traitement annulé")
    else:
        print("❌ Choix invalide")


if __name__ == "__main__":
    main()
