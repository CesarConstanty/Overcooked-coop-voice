# 🚀 Système de Ralentissement IA au Début d'Essai

## 🎯 Fonctionnalité Implémentée

Le système de ralentissement de l'IA au début d'essai permet de donner aux participants humains le temps nécessaire pour :
- **S'orienter** dans le nouveau layout
- **Analyser** les contraintes et objectifs du nouvel essai
- **Planifier** leur stratégie avant que l'IA ne devienne pleinement active

## 📋 Configuration

### Nouveaux Paramètres Ajoutés

```json
{
    "ai_trial_start_slowdown": true,      // Active le ralentissement au début des essais
    "ai_trial_start_duration": 60,       // Durée du ralentissement en ticks
    "ai_trial_start_speed": 20,          // Vitesse spécifique pour le début d'essai
    "ai_trial_start_first_only": false   // Si true, seulement le premier essai du bloc
}
```

### Paramètres Existants Utilisés

```json
{
    "ai_slowdown_enabled": true,          // Doit être activé pour le système de ralentissement
    "ai_base_speed": 4,                   // Vitesse normale de l'IA
    "ai_slow_speed": 100,                 // Vitesse pour changements de recette
    "ai_slow_duration": 100               // Durée des ralentissements de recette
}
```

## ⚡ Système de Vitesses Doubles

Le système supporte maintenant **deux types de ralentissement distincts** :

### 1. Ralentissement de Début d'Essai
- **Vitesse** : `ai_trial_start_speed` (ex: 20 ticks par action)
- **Déclencheur** : Automatique au début de chaque essai
- **Durée** : `ai_trial_start_duration` ticks

### 2. Ralentissement de Changement de Recette
- **Vitesse** : `ai_slow_speed` (ex: 100 ticks par action)
- **Déclencheur** : Quand l'IA change d'intention de recette
- **Durée** : `ai_slow_duration` ticks

### 🔥 Système de Priorité
Quand plusieurs ralentissements sont actifs :
1. **Début d'essai** a la priorité maximale
2. **Changement de recette** a la priorité secondaire
3. **Vitesse normale** par défaut

## ⚙️ Options de Configuration

### 1. Ralentissement à Chaque Essai (Recommandé)
```json
{
    "ai_trial_start_slowdown": true,
    "ai_trial_start_duration": 60,
    "ai_trial_start_speed": 20,
    "ai_trial_start_first_only": false
}
```
- **Effet** : L'IA ralentit au début de chaque nouvel essai
- **Usage** : Expériences où chaque essai a un layout différent

### 2. Ralentissement Premier Essai Seulement
```json
{
    "ai_trial_start_slowdown": true,
    "ai_trial_start_duration": 90,
    "ai_trial_start_speed": 25,
    "ai_trial_start_first_only": true
}
```
- **Effet** : L'IA ralentit seulement au premier essai de chaque bloc
- **Usage** : Expériences avec des blocs thématiques

### 3. Système Complet (Recommandé pour Recherche)
```json
{
    "ai_slowdown_enabled": true,
    "ai_base_speed": 4,
    "ai_slow_speed": 100,
    "ai_trial_start_speed": 20,
    "ai_slow_duration": 120,
    "ai_trial_start_slowdown": true,
    "ai_trial_start_duration": 60,
    "ai_trial_start_first_only": false
}
```
- **Effet** : Ralentissement de début d'essai + ralentissement de changement de recette
- **Usage** : Expériences complètes avec signalement d'intentions

### 4. Ralentissement Désactivé
```json
{
    "ai_trial_start_slowdown": false
}
```
- **Effet** : Aucun ralentissement automatique au début d'essai
- **Usage** : Conditions de contrôle ou expériences sans besoin d'orientation

## 🎮 Fonctionnement en Jeu

### Déclenchement
1. **Quand** : Automatiquement lors de l'appel à `game.activate()` au début d'un essai
2. **Condition** : Si `ai_trial_start_slowdown: true` et `ai_slowdown_enabled: true`
3. **Durée** : Nombre de ticks spécifié par `ai_trial_start_duration`

### Effet Visible
- **Vitesse normale** : L'IA reçoit des mises à jour toutes les `ai_base_speed` frames (ex: 4)
- **Vitesse début d'essai** : L'IA reçoit des mises à jour toutes les `ai_trial_start_speed` frames (ex: 20)
- **Vitesse changement recette** : L'IA reçoit des mises à jour toutes les `ai_slow_speed` frames (ex: 100)
- **Retour automatique** : Après la durée spécifiée, retour à la vitesse normale

### Logs de Débogage
```
[AI_SLOWDOWN] Trial start slowdown triggered for 60 ticks at speed 20
[AI_SLOWDOWN] First trial of block 2 - extended orientation time
[AI_SLOWDOWN] Speed changed to TRIAL START SLOW: 20 (remaining: 59)
[AI_SLOWDOWN] Recipe intention changed: None -> onion (triggering slowdown for 100 ticks)
[AI_SLOWDOWN] Speed changed to RECIPE CHANGE SLOW: 100 (remaining: 99)
[AI_SLOWDOWN] Speed returned to NORMAL: 4
```

## 🔗 Interaction avec le Système Existant

### Compatibilité
- **Compatible** avec le ralentissement par changement d'intention de recette
- **Système de priorité** : Le ralentissement de début d'essai a priorité sur le changement de recette
- **Indépendant** : Les deux systèmes peuvent fonctionner simultanément avec leurs propres vitesses

### Exemple de Séquence Complexe
1. **Début d'essai** : Ralentissement automatique (vitesse 20, durée 60 ticks)
2. **Pendant le ralentissement** : L'IA change d'intention → mémorisé mais pas appliqué
3. **Fin du ralentissement de début** : Application du ralentissement de recette (vitesse 100, durée 120 ticks)
4. **Fin des ralentissements** : Retour à la vitesse normale (4)

## 📊 Paramètres Recommandés

### Pour des Layouts Complexes
```json
{
    "ai_trial_start_slowdown": true,
    "ai_trial_start_duration": 90,      // Plus long pour analyser
    "ai_trial_start_speed": 25,         // Plus lent pour observation
    "ai_trial_start_first_only": false
}
```

### Pour des Expériences avec Blocs
```json
{
    "ai_trial_start_slowdown": true,
    "ai_trial_start_duration": 80,      // Orientation étendue
    "ai_trial_start_first_only": true   // Seulement premier essai du bloc
}
```

### Pour des Essais Courts
```json
{
    "ai_trial_start_slowdown": true,
    "ai_trial_start_duration": 30,      // Ralentissement bref
    "ai_trial_start_first_only": false
}
```

## 🧪 Validation

### Tests Effectués
- ✅ **Déclenchement automatique** au début d'essai
- ✅ **Durée correcte** du ralentissement
- ✅ **Mode "premier seulement"** fonctionne
- ✅ **Désactivation** possible
- ✅ **Retour à la vitesse normale** automatique
- ✅ **Compatibilité** avec le système existant

### Configurations Testées
- ✅ Sections `test_voice_intention`, `test_voice_intention_layout`
- ✅ Paramètres globaux du fichier de configuration
- ✅ Différentes durées et options

## 🚀 Utilisation

### Pour Activer dans une Expérience
1. **Éditer** la section de configuration correspondante dans `config.json`
2. **Ajouter** les paramètres de ralentissement au début d'essai
3. **Tester** avec différentes durées selon les besoins
4. **Observer** les logs pour vérifier le bon fonctionnement

### Exemple d'Intégration
```json
"mon_experience": {
    "mechanic": "recipe",
    "gameTime": 120,
    "ai_slowdown_enabled": true,
    "ai_base_speed": 4,
    "ai_slow_speed": 15,
    "ai_slow_duration": 20,
    
    // Nouveaux paramètres pour le début d'essai
    "ai_trial_start_slowdown": true,
    "ai_trial_start_duration": 45,
    "ai_trial_start_first_only": false
}
```

## ✅ Statut

**🎉 IMPLÉMENTÉ ET TESTÉ** : Le système de ralentissement au début d'essai est pleinement fonctionnel et prêt pour utilisation en production.

---

*Système implémenté le : $(date)*
*Validation complète effectuée*
