import os
import json
import glob
import numpy as np
import shutil


def best_improvement_for_json(json_file):
    """Retourne la meilleure amélioration en pourcentage pour un fichier JSON donné."""
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        best_percentage = None
        best_version = None
        best_solo = None
        best_coop = None
        for version in data:
            solo = version.get('solo_distance', 0)
            coop = version.get('coop_distance', 0)
            if solo > 0:
                percentage = ((solo - coop) / solo) * 100
                if (best_percentage is None) or (percentage > best_percentage):
                    best_percentage = percentage
                    best_version = version.get('variation_num', 1)
                    best_solo = solo
                    best_coop = coop
        return best_percentage, best_version, best_solo, best_coop
    except Exception as e:
        print(f"Erreur avec {json_file}: {e}")
        return None, None, None, None

def homogene_layouts (json_path="test_generation_layout/layout_analysis_results/best_layout_version.json", n=11) :
    # Charger les données JSON
    with open(json_path, 'r') as f:
        data = json.load(f)
    # Extraire les triplets (coop_distance, layout_file, version)
    entries = [
        (entry["coop_distance"], entry["layout_file"], entry["version"])
        for entry in data
        if "coop_distance" in entry and "layout_file" in entry and "version" in entry
    ]

    # Trier les entrées par coop_distance
    entries.sort(key=lambda x: x[0])

    # Chercher la fenêtre de taille n avec l’écart minimal entre min et max
    min_range = float('inf')
    best_slice = None

    for i in range(len(entries) - n + 1):
        window = entries[i:i + n]
        dist_range = window[-1][0] - window[0][0]
        if dist_range < min_range:
            min_range = dist_range
            best_slice = window

    if best_slice is None:
        raise ValueError("Pas assez de données pour sélectionner 11 valeurs.")

    # Extraire les layout_file et version
    layout_files = [entry[1] for entry in best_slice]
    versions = [entry[2] for entry in best_slice]

    return layout_files, versions

def select_homogeneous_layouts(results, n):
    # Trie les résultats selon coop_distance puis improvement_percentage
    results_sorted = sorted(results, key=lambda x: (x["coop_distance"], x["improvement_percentage"]))
    min_window_size = 1
    found = False
    selected = []
    while not found:
        # Pour chaque combinaison possible de fenêtre sur coop_distance
        for i in range(len(results_sorted)):
            min_coop = results_sorted[i]["coop_distance"]
            max_coop = min_coop + min_window_size
            # Filtrer sur coop_distance dans la fenêtre
            coop_window = [x for x in results_sorted if min_coop <= x["coop_distance"] <= max_coop]
            if len(coop_window) < n:
                continue
            # Pour chaque combinaison possible de fenêtre sur improvement_percentage dans cette fenêtre coop
            coop_window_sorted = sorted(coop_window, key=lambda x: x["improvement_percentage"])
            for j in range(len(coop_window_sorted)):
                min_imp = coop_window_sorted[j]["improvement_percentage"]
                max_imp = min_imp + min_window_size
                final_window = [x for x in coop_window_sorted if min_imp <= x["improvement_percentage"] <= max_imp]
                if len(final_window) >= n:
                    selected = final_window[:n]
                    found = True
                    break
            if found:
                break
        if not found:
            min_window_size += 1
            if min_window_size > 1000:  # sécurité anti-boucle infinie
                break
    return selected if selected else results_sorted[:n]

def main():
    results_dir = "test_generation_layout/path_evaluation_results"
    json_pattern = os.path.join(results_dir, "layout_*_R_*_results.json")
    json_files = glob.glob(json_pattern)
    if not json_files:
        print(f"Aucun fichier trouvé dans {results_dir}")
        return
    results = []
    for json_file in sorted(json_files):
        best_percentage, best_version, best_solo, best_coop = best_improvement_for_json(json_file)
        if best_percentage is not None:
            version_str = f"{int(best_version):02d}"
            layout_name = f"L{os.path.basename(json_file).split('_')[1]}_R{os.path.basename(json_file).split('_')[3]}_V{version_str}.layout"
            results.append({
                "name": layout_name,
                "solo_distance": best_solo,
                "coop_distance": best_coop,
                "improvement_percentage": round(best_percentage, 2)
            })
    n = 11  # nombre de layouts à sélectionner (modifiable)
    if len(results) < n:
        selected = results
    else:
        selected = select_homogeneous_layouts(results, n)
    # Création du dossier de sortie si besoin
    output_dir = "test_generation_layout/layout_analysis_results"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "final_layouts.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(selected, f, indent=2, ensure_ascii=False)
    print(f"Résultats enregistrés dans {output_path}")

    # Copier les layouts sélectionnés dans le dossier cible
    layout_names = [layout["name"] for layout in selected]
    src_dir = "test_generation_layout/layouts_with_objects"
    dst_dir = "overcooked_ai_py/data/layouts/generation_cesar/selection_finale"
    os.makedirs(dst_dir, exist_ok=True)
    # Recherche récursive dans tous les sous-dossiers de src_dir, affichage debug
    for name in layout_names:
        found = False
        for root, dirs, files in os.walk(src_dir):
            # Affichage debug pour comprendre ce qui est trouvé
            # print(f"Recherche dans {root}, fichiers: {files}")
            for file in files:
                if file.strip() == name.strip():
                    src_path = os.path.join(root, file)
                    dst_path = os.path.join(dst_dir, name)
                    shutil.copy(src_path, dst_path)
                    print(f"Copié: {src_path} -> {dst_path}")
                    found = True
                    break
            if found:
                break
        if not found:
            print(f"Attention: {name} n'a pas été trouvé dans {src_dir} (recherche récursive) et n'a pas été copié.")

if __name__ == "__main__":
    main()
