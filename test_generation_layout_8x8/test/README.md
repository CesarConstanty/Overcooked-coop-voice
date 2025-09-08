# Dossier Test

Ce dossier contient tous les fichiers de test et de démonstration pour le pipeline de génération de layouts.

## Contenu

- **`config_demo.py`** - Script de démonstration pour modifier la configuration du nombre de layouts finaux
- **`demo_pipeline.py`** - Script de démonstration du pipeline complet
- **`test_final_selection.py`** - Test de la sélection finale des layouts
- **`test_format.py`** - Test du formatage des layouts au format final

## Utilisation

### Test de la configuration
```bash
cd test_generation_layout_8x8/test
python3 config_demo.py
```

### Test du formatage
```bash
cd test_generation_layout_8x8/test
python3 test_format.py
```

### Test de la sélection finale
```bash
cd test_generation_layout_8x8/test
python3 test_final_selection.py
```

## Suppression

Une fois le projet fonctionnel, ce dossier peut être supprimé entièrement :
```bash
rm -rf test_generation_layout_8x8/test/
```

## Note

Ces fichiers sont destinés uniquement au développement et aux tests. Ils ne sont pas nécessaires pour le fonctionnement du pipeline en production.
