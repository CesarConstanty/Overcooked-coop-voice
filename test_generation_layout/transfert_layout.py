import shutil
from pathlib import Path

dest_dir = Path("overcooked_ai_py/data/layouts/generation_cesar/demo")
dest_dir.mkdir(exist_ok=True)

for i in range(1, 22):
    src = Path(f"test_generation_layout/layouts_with_objects/recette_lot_1/layout_combination_{i:02d}/V1_layout_combination_{i:02d}.layout")
    if src.exists():
        shutil.copy(src, dest_dir / src.name)
        print(f"Copié: {src} -> {dest_dir / src.name}")
    else:
        print(f"Non trouvé: {src}")
