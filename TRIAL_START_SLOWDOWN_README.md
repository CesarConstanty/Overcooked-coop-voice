# 🚀 Système de Ralentissement IA Multi-Types

## 🎯 Fonctionnalité Implémentée

Le système de ralentissement de l'IA multi-types permet de donner aux participants humains le temps nécessaire pour :
- **S'orienter** dans le nouveau layout (ralentissement de début d'essai)
- **Percevoir les changements d'intention** de l'IA concernant les ingrédients/objets (ralentissement d'asset)
- **Comprendre les changements de stratégie** de l'IA concernant les recettes (ralentissement de recette)

## 📋 Configuration

### Nouveaux Paramètres Ajoutés

```json
{
    "ai_trial_start_slowdown": true,      // Active le ralentissement au début des essais
    "ai_trial_start_duration": 60,       // Durée du ralentissement en ticks
    "ai_trial_start_speed": 20,          // Vitesse spécifique pour le début d'essai
    "ai_trial_start_first_only": false,  // Si true, seulement le premier essai du bloc
    "ai_asset_slowdown_enabled": true,   // Active le ralentissement pour changements d'asset
    "ai_asset_slow_speed": 60,           // Vitesse pendant ralentissement d'asset
    "ai_asset_slow_duration": 40         // Durée du ralentissement d'asset en ticks
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

## ⚡ Système de Vitesses Triples

Le système supporte maintenant **trois types de ralentissement distincts** :

### 1. Ralentissement de Début d'Essai
- **Vitesse** : `ai_trial_start_speed` (ex: 20 ticks par action)
- **Déclencheur** : Automatique au début de chaque essai
- **Durée** : `ai_trial_start_duration` ticks
- **Priorité** : **MAXIMALE**

### 2. Ralentissement de Changement d'Asset
- **Vitesse** : `ai_asset_slow_speed` (ex: 60 ticks par action)
- **Déclencheur** : Quand l'IA change d'intention d'ingrédient/objet
- **Durée** : `ai_asset_slow_duration` ticks
- **Priorité** : **ÉLEVÉE**
- **Assets détectés** : Oignon (O), Tomate (T), Marmite (P), Soupe (S), Livraison (D), Autre (X)

### 3. Ralentissement de Changement de Recette
- **Vitesse** : `ai_slow_speed` (ex: 100 ticks par action)
- **Déclencheur** : Quand l'IA change d'intention de recette
- **Durée** : `ai_slow_duration` ticks
- **Priorité** : **STANDARD**

### 🔥 Système de Priorité
Quand plusieurs ralentissements sont actifs simultanément :
1. **Début d'essai** a la priorité maximale
2. **Changement d'asset** a la priorité élevée
3. **Changement de recette** a la priorité standard
4. **Vitesse normale** par défaut

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

### 3. Système Complet avec Assets (Recommandé pour Recherche)
```json
{
    "ai_slowdown_enabled": true,
    "ai_base_speed": 4,
    "ai_slow_speed": 100,
    "ai_trial_start_speed": 20,
    "ai_asset_slow_speed": 60,
    "ai_slow_duration": 120,
    "ai_trial_start_duration": 60,
    "ai_asset_slow_duration": 40,
    "ai_trial_start_slowdown": true,
    "ai_trial_start_first_only": false,
    "ai_asset_slowdown_enabled": true
}
```
- **Effet** : Tous les types de ralentissement actifs
- **Usage** : Expériences complètes avec signalement d'intentions multi-niveaux

### 4. Ralentissement d'Asset Seulement
```json
{
    "ai_slowdown_enabled": true,
    "ai_base_speed": 4,
    "ai_asset_slowdown_enabled": true,
    "ai_asset_slow_speed": 50,
    "ai_asset_slow_duration": 30,
    "ai_trial_start_slowdown": false
}
```
- **Effet** : Ralentissement uniquement lors des changements d'intention d'ingrédient/objet
- **Usage** : Étude spécifique des intentions d'assets

### 5. Ralentissement Désactivé
```json
{
    "ai_trial_start_slowdown": false,
    "ai_asset_slowdown_enabled": false
}
```
- **Effet** : Aucun ralentissement automatique
- **Usage** : Conditions de contrôle ou expériences sans besoin d'orientation

## 🎮 Fonctionnement en Jeu

### Déclenchement des Ralentissements

#### 1. Ralentissement de Début d'Essai
- **Quand** : Automatiquement lors de l'appel à `game.activate()` au début d'un essai
- **Condition** : Si `ai_trial_start_slowdown: true` et `ai_slowdown_enabled: true`
- **Durée** : Nombre de ticks spécifié par `ai_trial_start_duration`

#### 2. Ralentissement de Changement d'Asset
- **Quand** : Quand l'agent IA change d'intention d'ingrédient/objet
- **Condition** : Si `ai_asset_slowdown_enabled: true` et `ai_slowdown_enabled: true`
- **Durée** : Nombre de ticks spécifié par `ai_asset_slow_duration`
- **Assets détectés** :
  - **O** : Oignon (Onion)
  - **T** : Tomate (Tomato)
  - **P** : Marmite (Pot)
  - **S** : Soupe (Soup)
  - **D** : Livraison (Deliver)
  - **X** : Autre action

#### 3. Ralentissement de Changement de Recette
- **Quand** : Quand l'agent IA change d'intention de recette
- **Condition** : Si `ai_slowdown_enabled: true`
- **Durée** : Nombre de ticks spécifié par `ai_slow_duration`

### Effet Visible
- **Vitesse normale** : L'IA reçoit des mises à jour toutes les `ai_base_speed` frames (ex: 4)
- **Vitesse début d'essai** : L'IA reçoit des mises à jour toutes les `ai_trial_start_speed` frames (ex: 20)
- **Vitesse changement asset** : L'IA reçoit des mises à jour toutes les `ai_asset_slow_speed` frames (ex: 60)
- **Vitesse changement recette** : L'IA reçoit des mises à jour toutes les `ai_slow_speed` frames (ex: 100)
- **Retour automatique** : Après la durée spécifiée, retour à la vitesse normale

### Logs de Débogage
```
[AI_SLOWDOWN] Trial start slowdown triggered for 60 ticks at speed 20
[AI_SLOWDOWN] Speed changed to TRIAL START SLOW: 20 (remaining: 59)
[AI_SLOWDOWN] Asset intention changed: Onion -> Tomato
[AI_SLOWDOWN] Triggering asset slowdown for 40 ticks
[AI_SLOWDOWN] Speed changed to ASSET CHANGE SLOW: 60 (remaining: 39)
[AI_SLOWDOWN] Recipe intention changed: None -> onion (triggering slowdown for 100 ticks)
[AI_SLOWDOWN] Speed changed to RECIPE CHANGE SLOW: 100 (remaining: 99)
[AI_SLOWDOWN] Speed returned to NORMAL: 4
```

## 🔗 Interaction avec le Système Multi-Types

### Compatibilité
- **Triple compatibilité** : Les trois types de ralentissement fonctionnent ensemble
- **Système de priorité avancé** : 
  1. Début d'essai (priorité maximale)
  2. Changement d'asset (priorité élevée)
  3. Changement de recette (priorité standard)
- **Vitesses indépendantes** : Chaque type a sa propre vitesse et durée

### Exemple de Séquence Complexe
1. **Début d'essai** : Ralentissement automatique (vitesse 20, durée 60 ticks)
2. **Pendant le ralentissement** : L'IA change d'asset → mémorisé mais pas appliqué
3. **Fin du ralentissement de début** : Application du ralentissement d'asset (vitesse 60, durée 40 ticks)
4. **Pendant ralentissement d'asset** : Changement de recette → mémorisé
5. **Fin du ralentissement d'asset** : Application du ralentissement de recette (vitesse 100, durée 120 ticks)
6. **Fin de tous les ralentissements** : Retour à la vitesse normale (4)

## 📊 Paramètres Recommandés

### Pour des Layouts Complexes avec Signalement d'Intentions
```json
{
    "ai_trial_start_slowdown": true,
    "ai_trial_start_duration": 90,      // Plus long pour analyser
    "ai_trial_start_speed": 25,         // Plus lent pour observation
    "ai_trial_start_first_only": false,
    "ai_asset_slowdown_enabled": true,
    "ai_asset_slow_speed": 50,          // Ralentissement modéré pour assets
    "ai_asset_slow_duration": 35        // Durée suffisante pour perception
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
