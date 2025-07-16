# Système de Ralentissement Temporaire de l'Agent AI

## Description

Cette fonctionnalité permet de ralentir temporairement l'agent artificiel lorsqu'il change d'intention de recette, donnant ainsi le temps au participant humain de comprendre la nouvelle intention de l'agent.

## Fonctionnement

### Détection des changements d'intention
- Le système surveille les intentions de recette de l'agent AI à chaque frame
- Lorsqu'un changement d'intention de recette est détecté, un ralentissement temporaire est activé
- Le ralentissement ne se déclenche que lors de vrais changements (pas lors de l'initialisation)

### Paramètres configurables

Les paramètres suivants peuvent être ajustés dans le fichier `config.json` :

```json
{
    "ai_slowdown_enabled": true,     // Activer/désactiver le ralentissement
    "ai_base_speed": 4,              // Vitesse normale (en ticks par action)
    "ai_slow_speed": 12,             // Vitesse ralentie (en ticks par action)
    "ai_slow_duration": 20           // Durée du ralentissement (en ticks)
}
```

### Valeurs par défaut
- **ai_slowdown_enabled**: `true` - Fonctionnalité activée par défaut
- **ai_base_speed**: `4` - Vitesse normale (4 ticks entre chaque action AI)
- **ai_slow_speed**: `12` - Vitesse ralentie (12 ticks entre chaque action AI, soit 3x plus lent)
- **ai_slow_duration**: `20` - Le ralentissement dure 20 ticks

## Exemple d'utilisation

### Configuration dans config.json

Pour une expérience avec ralentissement modéré :
```json
{
    "ai_slowdown_enabled": true,
    "ai_base_speed": 4,
    "ai_slow_speed": 8,
    "ai_slow_duration": 15
}
```

Pour une expérience avec ralentissement plus prononcé :
```json
{
    "ai_slowdown_enabled": true,
    "ai_base_speed": 4,
    "ai_slow_speed": 16,
    "ai_slow_duration": 30
}
```

Pour désactiver le ralentissement :
```json
{
    "ai_slowdown_enabled": false
}
```

## Logs de débogage

Le système produit des logs pour aider au débogage :

- `[AI_SPEED] Recipe intention changed to [ingredients], slowing down AI for X ticks`
- `[AI_SPEED] Returning to normal speed`
- `[AI_SPEED] Error checking recipe intention: [error]`

## Implémentation technique

### Classes modifiées
- **OvercookedGame** : Classe de base avec la logique de ralentissement
- **PlanningGame** : Hérite automatiquement de la fonctionnalité

### Méthodes ajoutées
- `_check_recipe_intention_change()` : Détecte les changements d'intention
- `_update_ai_speed()` : Met à jour la vitesse de l'agent
- Variables d'instance pour suivre l'état du ralentissement

### Sécurité
- La fonctionnalité ne peut pas interrompre le déroulement normal du jeu
- En cas d'erreur, le jeu continue avec la vitesse normale
- Tous les changements sont rétrocompatibles

## Tests

Un script de test `test_ai_slowdown.py` est fourni pour valider la logique :

```bash
python test_ai_slowdown.py
```

Ce script simule différents scénarios de changement d'intention et vérifie que le ralentissement fonctionne correctement.

## Notes importantes

1. **Performance** : Le ralentissement n'affecte que la fréquence des actions AI, pas la performance générale du jeu
2. **Compatibilité** : La fonctionnalité est entièrement rétrocompatible avec le code existant
3. **Flexibilité** : Tous les paramètres peuvent être ajustés sans modifier le code
4. **Robustesse** : Les erreurs sont gérées gracieusement sans affecter le gameplay

## Calibration recommandée

Pour une expérience optimale, nous recommandons :
- **ai_slow_speed** : 2-4x la vitesse normale (8-16 si ai_base_speed = 4)
- **ai_slow_duration** : 15-30 ticks (0.5-1 seconde à 30 FPS)
- Tester avec des participants pour ajuster les paramètres selon l'expérience souhaitée
