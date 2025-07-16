# Système Audio Amélioré - Documentation

## Vue d'ensemble

Le système audio a été entièrement refactorisé pour utiliser la WebAudio API avec fallback vers l'audio Phaser. Cette nouvelle implémentation offre une meilleure performance, un contrôle plus précis et une gestion paramétrable des différentes conditions expérimentales.

## Corrections récentes

### Problème 1: Double lecture des intentions de recettes
**Solution**: Centralisation de la logique audio dans `_drawHUD` uniquement. Le code dans `_drawState` ne gère plus les sons de recettes pour éviter les doublons.

### Problème 2: Erreurs de chargement des buffers audio
**Solution**: 
- Amélioration de la gestion d'erreurs dans `loadAudioBuffers()`
- Vérification de l'existence des buffers avant accès
- Gestion de l'autoplay policy des navigateurs
- Fallback automatique vers Phaser Audio en cas d'échec

## Fonctionnalités principales

### 1. WebAudio API avec fallback robuste
- Utilisation prioritaire de la WebAudio API pour de meilleures performances
- Gestion de l'autoplay policy des navigateurs modernes
- Fallback automatique vers l'audio Phaser si WebAudio échoue
- Gestion des buffers audio en cache pour éviter les latences

### 2. Contrôle paramétrable
Le système offre trois niveaux de contrôle audio :

```javascript
scene.setAudioEnabled(true/false);        // Contrôle global de tous les sons
scene.setRecipeAudioEnabled(true/false);  // Contrôle spécifique aux sons de recettes
scene.setAssetAudioEnabled(true/false);   // Contrôle spécifique aux sons d'assets
```

### 3. Gestion centralisée des conditions expérimentales

La logique audio est maintenant centralisée dans `_drawHUD()` avec quatre cas distincts :

#### Cas 1: Intentions de recette ET d'asset (`recipe_sound: true, asset_sound: true`)
- Séquence : `annonce_recette.mp3` → son de recette → sons d'assets
- Recommence la séquence complète lors d'un changement d'intention de recette
- Joue uniquement les sons d'assets lors d'un changement d'intention d'asset (si la recette n'a pas changé)

#### Cas 2: Intentions de recette uniquement (`recipe_sound: true, asset_sound: false`)
- Séquence : `annonce_recette.mp3` → son de recette
- Recommence lors d'un changement d'intention de recette

#### Cas 3: Intentions d'asset uniquement (`recipe_sound: false, asset_sound: true`)
- Diffusion des sons d'assets le plus tôt possible lors de l'initiation et du changement d'intention

#### Cas 4: Aucun son (`recipe_sound: false, asset_sound: false`)
- Aucune lecture audio, seuls les HUD visuels sont affichés

### 4. Debug et monitoring

Nouvelle méthode de debug pour diagnostiquer les problèmes :
```javascript
scene.debugAudioSystem(); // Affiche l'état complet du système audio
```

## Architecture technique

### Gestion robuste des erreurs
```javascript
// Vérification de l'existence des buffers
if (this.cache.audio.exists(audioKey)) {
    const audioBuffer = this.cache.audio.get(audioKey);
    if (audioBuffer && audioBuffer.buffer) {
        // Traitement sécurisé
    }
}
```

### Gestion de l'autoplay policy
```javascript
if (this.audioContext.state === 'suspended') {
    // Reprise automatique sur interaction utilisateur
    document.addEventListener('click', () => {
        this.audioContext.resume();
    }, { once: true });
}
```

### Fichiers audio supportés
Le système charge automatiquement tous les fichiers audio nécessaires :

**Sons d'assets :**
- `comptoir.mp3`, `marmite.mp3`, `oignon.mp3`, `tomate.mp3`, `assiette.mp3`, `service.mp3`

**Sons de recettes :**
- `annonce_recette.mp3`
- `recette_{X}o_{Y}t.mp3` (X oignons, Y tomates) pour toutes les combinaisons valides

## Configuration dans les conditions expérimentales

Exemple pour la configuration `test_voice_intention_layout` :
```json
{
  "condition": {
    "recipe_head": false,
    "recipe_hud": true,
    "asset_hud": true,
    "motion_goal": false,
    "asset_sound": true,
    "recipe_sound": true
  }
}
```

Cette configuration active le **Cas 1** : séquence complète recette + assets.

## Dépannage

### Sons joués deux fois
✅ **Corrigé** : La logique audio est maintenant centralisée dans `_drawHUD` uniquement.

### Erreurs de buffer audio
✅ **Corrigé** : Vérifications robustes et fallback automatique vers Phaser Audio.

### Pas de son
1. Vérifiez la console pour les messages de debug
2. Utilisez `scene.debugAudioSystem()` pour diagnostiquer
3. Vérifiez les permissions audio du navigateur
4. Testez avec interaction utilisateur (clic) pour déclencher l'autoplay

### Performance
- Les buffers WebAudio sont mis en cache pour éviter les rechargements
- Fallback automatique si WebAudio n'est pas disponible
- Gestion optimisée des états audio pour éviter les conflits

## Compatibilité

- **WebAudio API** : Navigateurs modernes (Chrome 10+, Firefox 25+, Safari 6+)
- **Fallback Phaser Audio** : Tous les navigateurs supportant HTML5 Audio
- **Rétrocompatibilité** : Le code existant continue de fonctionner sans modification
