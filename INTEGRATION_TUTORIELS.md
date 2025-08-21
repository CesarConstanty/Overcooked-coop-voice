# Documentation des modifications pour l'intégration des tutoriels de condition

## Résumé des modifications

L'intégration des tutoriels spécifiques aux conditions EA, U, et EV a été implémentée avec succès. Voici un résumé des modifications apportées :

## Fichiers créés

### 1. Templates HTML des tutoriels
- `static/templates/tutorial_EA.html` - Tutoriel pour la condition EA (Explicabilité Auditive)
- `static/templates/tutorial_U.html` - Tutoriel pour la condition U (Sans Explicabilité)
- `static/templates/tutorial_EV.html` - Tutoriel pour la condition EV (Explicabilité Visuelle)

### 2. Scripts de test
- `test_tutorial_integration.py` - Script de validation de l'intégration

## Fichiers modifiés

### 1. Configuration (`config.json`)
**Modification dans `test_experiment_1`:**
```json
"condition_tutorials" : {"EA": "tutorial_EA.html", "U": "tutorial_U.html", "EV": "tutorial_EV.html"}
```

Cette ligne a été ajoutée après la ligne `"conditions"` pour mapper chaque condition à son tutoriel correspondant.

### 2. Application Flask (`app.py`)

#### Nouvelle route ajoutée:
```python
@app.route('/condition_tutorial')
@login_required
def condition_tutorial():
```

Cette route gère l'affichage des tutoriels spécifiques aux conditions. Elle :
- Récupère la condition du bloc courant
- Trouve le template de tutoriel correspondant
- Affiche le tutoriel avec les bonnes variables

#### Modification de la route `/planning`:
Ajout d'une logique pour rediriger vers le tutoriel de condition quand nécessaire :
- Vérifie si l'utilisateur commence un nouveau bloc (trial == 0)
- Vérifie s'il n'a pas déjà vu le tutoriel (paramètre from_condition_tutorial)
- Redirige vers le tutoriel approprié si nécessaire

## Fonctionnement

### Flux de l'expérience
1. **Tutoriel général** : Reste inchangé, affiché au début de l'expérience
2. **Début d'un bloc** : 
   - L'utilisateur est redirigé vers `/condition_tutorial`
   - Le tutoriel spécifique à la condition est affiché
   - L'utilisateur clique sur "Commencer le bloc"
   - Redirection vers `/planning?from_condition_tutorial=true`
3. **Jeu** : L'expérience se déroule normalement

### Gestion de l'ordre aléatoire
- L'option `shuffle_blocs: true` reste fonctionnelle
- Peu importe l'ordre des blocs, le bon tutoriel est toujours affiché
- La logique utilise `current_user.config["bloc_order"][current_user.step]` pour déterminer la condition

### Évitement des boucles de redirection
- Paramètre `from_condition_tutorial=true` dans l'URL de retour
- La route `/planning` vérifie ce paramètre pour éviter une nouvelle redirection

## Personnalisation future

### Modification du contenu des tutoriels
Pour modifier le contenu d'un tutoriel, éditer le fichier HTML correspondant :
- `static/templates/tutorial_EA.html` pour la condition EA
- `static/templates/tutorial_U.html` pour la condition U  
- `static/templates/tutorial_EV.html` pour la condition EV

### Ajout de nouvelles conditions
1. Ajouter la condition dans `config.json` > `test_experiment_1` > `conditions`
2. Créer le template HTML correspondant dans `static/templates/`
3. Ajouter le mapping dans `config.json` > `test_experiment_1` > `condition_tutorials`

## Tests

Exécuter le script de test pour valider l'intégration :
```bash
python3 test_tutorial_integration.py
```

## Compatibilité

- ✅ Ordre aléatoire des blocs (`shuffle_blocs: true`)
- ✅ Tutoriel général existant inchangé
- ✅ Logique existante de l'expérience préservée
- ✅ Configuration test_experiment_1 uniquement (test_experiment_2 inchangée)
- ✅ Robustesse : gestion des cas d'erreur et configurations manquantes
