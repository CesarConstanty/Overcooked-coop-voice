import argparse
import json
import glob
import numpy as np
from copy import deepcopy
import shutil
import os
import ast

def read_layout_file(layout_name, layout_dir):
    """
    Lit un fichier layout directement
    
    Args:
        layout_name: nom du fichier layout (sans extension)
        layout_dir: répertoire contenant les layouts
    
    Returns:
        dict: contenu du layout
    """
    filepath = os.path.join(layout_dir, layout_name + '.layout')
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Le fichier {filepath} n'existe pas")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Évaluer le contenu comme un dictionnaire Python
    try:
        layout_dict = ast.literal_eval(content)
        return layout_dict
    except (ValueError, SyntaxError) as e:
        # Si ast.literal_eval échoue, essayer eval (moins sécurisé mais nécessaire pour certains formats)
        try:
            layout_dict = eval(content)
            return layout_dict
        except Exception as eval_error:
            raise ValueError(f"Impossible de parser le fichier {filepath}: {eval_error}")

def make_grid_string(grid):
    """
    Convertit une grille (array numpy ou liste) en chaîne formatée pour un fichier layout
    """
    grid_string = ""
    
    # Convertir en array numpy si ce n'est pas déjà fait
    if not isinstance(grid, np.ndarray):
        grid = np.array(grid)
    
    for k, line in enumerate(grid):
        for tile in line:
            grid_string += str(tile)
        if k != grid.shape[0] - 1:
            grid_string += '\n'
            grid_string += '\t\t\t\t'
    grid_string += '""",\n'
    return grid_string
def to_layout_file(grid, layout_name, layout_dir, angle):
    """Sauvegarde un layout avec rotation dans un nouveau fichier"""
    filepath = os.path.join(layout_dir, layout_name)
    source_file = filepath + '.layout'
    target_file = filepath + angle + '.layout'
    
    # Vérifier que le fichier source existe
    if not os.path.exists(source_file):
        print(f"❌ Erreur: Le fichier {source_file} n'existe pas")
        return
    
    # Lire le layout original
    try:
        layout = read_layout_file(layout_name, layout_dir)
    except Exception as e:
        print(f"❌ Erreur lors de la lecture de {source_file}: {e}")
        return
    
    # Créer la nouvelle grille formatée
    layout_grid = make_grid_string(grid)
    
    # Écrire le nouveau layout avec la grille modifiée
    with open(target_file, 'w+', encoding='utf-8') as f:
        f.write("{\n")
        f.write('\t"grid":  """')
        f.write(layout_grid)
        f.write('\t"start_all_orders": ' + str(layout["start_all_orders"]) + ",\n")
        f.write('\t"rew_shaping_params": None,\n')
        f.write('\t"counter_goals": ' + str(layout.get("counter_goals", [])) + ",\n")
        f.write('\t"onion_value": ' + str(layout["onion_value"]) + ",\n")
        f.write('\t"tomato_value": ' + str(layout["tomato_value"]) + ",\n")
        f.write('\t"onion_time": ' + str(layout["onion_time"]) + ",\n")
        f.write('\t"tomato_time": ' + str(layout["tomato_time"]) + "\n")       
        f.write("}")
        f.close()

def rotate_layout(layout_name, layout_dir, rotations):
    """
    Applique les rotations spécifiées à un layout
    
    Args:
        layout_name: nom du fichier layout (sans extension)
        layout_dir: répertoire contenant les layouts
        rotations: dict avec les rotations à appliquer (ex: {"90": True, "180": True, "270": False, "transpose": False})
    """
    # Lire le layout
    base_layout_params = read_layout_file(layout_name, layout_dir)
    
    # Extraire et parser la grille
    grid_str = base_layout_params['grid']
    
    # Nettoyer la chaîne de la grille (enlever les espaces en début/fin de ligne)
    grid_lines = [line.strip() for line in grid_str.strip().split('\n')]
    # Filtrer les lignes vides
    grid_lines = [line for line in grid_lines if line]
    
    # Créer la grille sous forme de liste de listes
    grid = [list(line) for line in grid_lines]
    
    # Appliquer les rotations demandées
    if rotations.get("90", False):
        grid90 = np.rot90(grid, 1)
        to_layout_file(grid90, layout_name, layout_dir, '_90')
        print(f"✓ Rotation 90° créée: {layout_name}_90.layout")
    
    if rotations.get("180", False):
        grid180 = np.rot90(grid, 2)
        to_layout_file(grid180, layout_name, layout_dir, '_180')
        print(f"✓ Rotation 180° créée: {layout_name}_180.layout")
    
    if rotations.get("270", False):
        grid270 = np.rot90(grid, 3)
        to_layout_file(grid270, layout_name, layout_dir, '_270')
        print(f"✓ Rotation 270° créée: {layout_name}_270.layout")
    
    if rotations.get("transpose", False):
        gridT = np.transpose(grid)
        to_layout_file(gridT, layout_name, layout_dir, '_T')
        print(f"✓ Transposition créée: {layout_name}_T.layout")
   
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script pour créer des rotations de layouts Overcooked",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  # Rotations 90° et 180° seulement pour le dossier generation_cesar_2
  python make_layouts_rotations.py --input-dir ./overcooked_ai_py/data/layouts/generation_cesar_2 --rot90 --rot180
  
  # Toutes les rotations pour un dossier spécifique
  python make_layouts_rotations.py --input-dir ./overcooked_ai_py/data/layouts/generation_cesar_2 --rot90 --rot180 --rot270 --transpose
  
  # Utiliser l'ancien mode avec config.json
  python make_layouts_rotations.py --config config_name --base_bloc 0
        """
    )
    
    # Mode moderne avec répertoire direct
    parser.add_argument("--input-dir", type=str, 
                       help="Répertoire contenant les fichiers .layout à traiter")
    parser.add_argument("--rot90", action="store_true", 
                       help="Créer une rotation à 90°")
    parser.add_argument("--rot180", action="store_true", 
                       help="Créer une rotation à 180°")
    parser.add_argument("--rot270", action="store_true", 
                       help="Créer une rotation à 270°")
    parser.add_argument("--transpose", action="store_true", 
                       help="Créer une transposition")
    
    # Mode legacy avec config.json (pour rétrocompatibilité)
    parser.add_argument("--config", type=str, 
                       help="[MODE LEGACY] Nom de la configuration dans config.json")
    parser.add_argument("--base_bloc", type=int, default=0, 
                       help="[MODE LEGACY] Numéro du bloc à traiter")
    
    args = parser.parse_args()
    
    # Vérifier les arguments
    if args.input_dir:
        # Mode moderne
        if not os.path.exists(args.input_dir):
            print(f"❌ Erreur: Le répertoire {args.input_dir} n'existe pas")
            exit(1)
        
        # Vérifier qu'au moins une rotation est demandée
        rotations = {
            "90": args.rot90,
            "180": args.rot180,
            "270": args.rot270,
            "transpose": args.transpose
        }
        
        if not any(rotations.values()):
            print("❌ Erreur: Vous devez spécifier au moins une rotation (--rot90, --rot180, --rot270, --transpose)")
            exit(1)
        
        # Trouver tous les fichiers .layout dans le répertoire
        layout_files = glob.glob(os.path.join(args.input_dir, "*.layout"))
        layout_names = [os.path.splitext(os.path.basename(f))[0] for f in layout_files]
        
        if not layout_names:
            print(f"❌ Aucun fichier .layout trouvé dans {args.input_dir}")
            exit(1)
        
        print(f"📁 Répertoire de travail: {args.input_dir}")
        print(f"🎯 Layouts trouvés: {len(layout_names)}")
        print(f"🔄 Rotations à appliquer: {[k for k, v in rotations.items() if v]}")
        print()
        
        # Traiter chaque layout
        for layout_name in layout_names:
            print(f"🔄 Traitement de {layout_name}...")
            try:
                rotate_layout(layout_name, args.input_dir, rotations)
            except Exception as e:
                print(f"❌ Erreur lors du traitement de {layout_name}: {e}")
        
        print(f"\n✅ Traitement terminé! {len(layout_names)} layouts traités.")
        
    elif args.config:
        # Mode legacy avec config.json
        print("⚠️  Mode legacy utilisé (config.json)")
        if not os.path.exists("./config.json"):
            print("❌ Erreur: Le fichier config.json n'existe pas")
            exit(1)
            
        with open("./config.json", 'r') as f:
            CONFIG = json.load(f)
            f.close()
        
        if args.config not in CONFIG:
            print(f"❌ Erreur: La configuration '{args.config}' n'existe pas dans config.json")
            exit(1)
            
        config = CONFIG[args.config]
        layout_dir = config.get("layouts_dir", "/home/cesar/python-projects/Overcooked-coop-voice/overcooked_ai_py/data/layouts/generation_cesar_2")
        base_layouts = config["blocs"][str(args.base_bloc)]
        
        # En mode legacy, toutes les rotations sont appliquées
        rotations = {"90": True, "180": True, "270": False, "transpose": False}
        
        for layout_name in base_layouts:
            rotate_layout(layout_name, layout_dir, rotations)
        print(CONFIG[args.config]['blocs'])
    
    else:
        print("❌ Erreur: Vous devez spécifier soit --input-dir soit --config")
        parser.print_help()
        exit(1)