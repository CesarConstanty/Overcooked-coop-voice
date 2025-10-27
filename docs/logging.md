# Guide du Système de Logging - Overcooked Coop Voice

## 📋 Vue d'ensemble

Le système de logging a été mis en place pour tracer **toutes les actions des participants** et identifier les causes des **fichiers de données incomplets** et des **durées d'essai anormalement courtes**.

## 📁 Fichiers de Logs

Les logs sont stockés dans le répertoire `logs/` avec rotation automatique (10 fichiers de 10MB max):

### 1. `all_actions.log` (DEBUG et plus)
- **Contenu**: Toutes les actions (routes, SocketIO, fichiers, games)
- **Usage**: Analyse détaillée du parcours utilisateur
- **Format**: `[timestamp] LEVEL | UID:user_id | CFG:config_id | ... | message`

### 2. `errors.log` (WARNING et plus)
- **Contenu**: Erreurs et avertissements uniquement
- **Usage**: Identifier rapidement les problèmes
- **Format**: Identique à `all_actions.log`

### 3. `user_actions.log` (INFO et plus)
- **Contenu**: Actions utilisateur significatives (routes, soumissions, etc.)
- **Usage**: Tracer le parcours expérimental sans le bruit des actions de jeu
- **Format**: Identique

## 🔍 Événements Tracés

### Routes HTTP
```
[USER_ACTION] ROUTE_INDEX_ENTER | uid=user123 | config_id=exp1
[USER_ACTION] ROUTE_INSTRUCTIONS_ENTER | uid=user123 | method=GET
[USER_ACTION] ROUTE_PLANNING_ENTER | uid=user123 | step=0 | trial=0
[USER_ACTION] ROUTE_QEX_ENTER | uid=user123 | step=3
```

### Événements SocketIO
```
[USER_ACTION] SOCKETIO_CONNECT | uid=user123 | sid=abc123 | step=0
[USER_ACTION] SOCKETIO_CREATE | uid=user123 | game_name=planning
[USER_ACTION] SOCKETIO_DISCONNECT | uid=user123 | step=1 | trial=5
```

### Sauvegardes de Fichiers
```
[FILE_WRITE] ✓ SUCCESS | uid=user123 | path=trajectories/.../QPT.json | size_bytes=2048
[FILE_WRITE] ✗ FAILED | uid=user123 | path=... | error=PermissionError
[FILE_WRITE] Fichier existe - ÉCRASEMENT ÉVITÉ | uid=user123 | path=...
```

### Cycle de Vie des Parties
```
[GAME_START] game_id=user123 | fps=15 | start_time=1729698045.123
[GAME_END] game_id=user123 | status=DONE | duration=45.67s
[GAME_CLEANUP] game_id=user123 | status=DONE | duration=45.67s
```

### Questionnaires
```
[USER_ACTION] QPT_SUBMIT | uid=user123 | step=0 | trial=2 | timeout=False
[USER_ACTION] QPB_SUBMIT | uid=user123 | step=0 | bloc=bloc_1
[USER_ACTION] HOFFMAN_SUBMIT | uid=user123 | step=0 | bloc=bloc_1
```

### Progression
```
[USER_ACTION] TRIAL_INCREMENT | uid=user123 | old_trial=2 | new_trial=3
[USER_ACTION] STEP_INCREMENT | uid=user123 | old_step=0 | new_step=1
[USER_ACTION] LAST_TRIAL_COMPLETE | uid=user123 | step=2
```

## 🛠️ Outils d'Analyse

### Script `tools/log_summary.py`

Analyse automatique des logs pour détecter les problèmes :

```bash
# Analyse complète
python tools/log_summary.py

# Filtrer par utilisateur
python tools/log_summary.py --uid user123

# Filtrer par date
python tools/log_summary.py --date 2025-10-23

# Ajuster le seuil de durée minimale (défaut: 30s)
python tools/log_summary.py --min-duration 60
```

**Détections automatiques:**
- ✅ Sessions incomplètes (démarrées mais pas terminées)
- ✅ Erreurs d'écriture de fichiers
- ✅ Parties anormalement courtes
- ✅ Déconnexions pendant les parties
- ✅ Résumé statistique global

### Commandes Grep Utiles

```bash
# Tous les événements d'un utilisateur
grep "UID:user123" logs/all_actions.log

# Toutes les erreurs
grep "ERROR\|WARNING" logs/all_actions.log

# Écritures de fichiers échouées
grep "FILE_WRITE.*FAILED" logs/all_actions.log

# Durées de parties
grep "GAME_END.*duration" logs/all_actions.log

# Déconnexions
grep "SOCKETIO_DISCONNECT" logs/all_actions.log

# Timeline d'un utilisateur (afficher uniquement timestamps et events)
grep "UID:user123" logs/all_actions.log | cut -d'|' -f1,6
```

## 🔧 Démarches de Debug

### Problème : Fichier de données incomplet ou manquant

1. **Vérifier si l'écriture a été tentée:**
   ```bash
   grep "UID:user123.*FILE_WRITE.*QPT" logs/all_actions.log
   ```

2. **Chercher des erreurs d'écriture:**
   ```bash
   grep "UID:user123.*FILE_WRITE.*FAILED" logs/all_actions.log
   ```

3. **Vérifier si le fichier existait déjà (écrasement évité):**
   ```bash
   grep "UID:user123.*ÉCRASEMENT ÉVITÉ" logs/all_actions.log
   ```

4. **Timeline complète des questionnaires:**
   ```bash
   grep "UID:user123.*QPT\|QPB\|HOFFMAN" logs/all_actions.log
   ```

### Problème : Durée d'essai anormalement courte

1. **Trouver les parties courtes automatiquement:**
   ```bash
   python tools/log_summary.py --min-duration 30
   ```

2. **Vérifier le début et la fin de la partie:**
   ```bash
   grep "UID:user123.*GAME_START\|GAME_END" logs/all_actions.log
   ```

3. **Chercher des déconnexions pendant le jeu:**
   ```bash
   grep "UID:user123.*DISCONNECT" logs/all_actions.log
   ```

4. **Vérifier si le bouton Start a été cliqué:**
   ```bash
   grep "UID:user123.*START_GAME" logs/all_actions.log
   ```

5. **Timeline complète d'une session:**
   ```bash
   grep "UID:user123" logs/all_actions.log | less
   ```

### Problème : Session abandonnée

1. **Identifier les sessions incomplètes:**
   ```bash
   python tools/log_summary.py
   ```

2. **Trouver le dernier événement:**
   ```bash
   grep "UID:user123" logs/all_actions.log | tail -n 20
   ```

3. **Vérifier les erreurs dans cette session:**
   ```bash
   grep "UID:user123" logs/errors.log
   ```

## 📊 Corrélation Temporelle

### Exemple de Timeline Complète

```
[2025-10-23 14:30:00] ROUTE_INDEX_ENTER          → Arrivée sur la page d'accueil
[2025-10-23 14:30:05] USER_NEW_CREATION          → Nouvel utilisateur créé
[2025-10-23 14:30:10] ROUTE_INSTRUCTIONS_ENTER   → Page instructions
[2025-10-23 14:32:15] ROUTE_PLANNING_ENTER       → Début expérience (step=0, trial=0)
[2025-10-23 14:32:20] SOCKETIO_CREATE            → Création de la partie
[2025-10-23 14:32:25] GAME_START                 → Partie démarre
[2025-10-23 14:33:10] GAME_END (duration=45s)    → Partie termine
[2025-10-23 14:33:11] FILE_WRITE (TRIAL_DATA)    → Sauvegarde données de jeu
[2025-10-23 14:33:15] QPT_SUBMIT                 → Soumission questionnaire
[2025-10-23 14:33:16] FILE_WRITE (QPT)           → Sauvegarde questionnaire
[2025-10-23 14:33:17] TRIAL_INCREMENT (0→1)      → Passage essai suivant
```

### Calcul de Durées

Pour calculer la durée entre deux événements:
```bash
# Extraire timestamps
grep "UID:user123.*GAME_START" logs/all_actions.log
grep "UID:user123.*GAME_END" logs/all_actions.log

# La durée est déjà affichée dans GAME_END:
# [GAME_END] ... | duration=45.67s
```

## 🚨 Patterns à Surveiller

### 🔴 Signaux de Problème

1. **FILE_WRITE FAILED** → Problème de permissions ou disque plein
2. **ÉCRASEMENT ÉVITÉ** → Double soumission ou rafraîchissement de page
3. **SOCKETIO_DISCONNECT** pendant partie → Perte de connexion
4. **duration < 30s** → Partie terminée prématurément
5. **QPT_ALREADY_EXISTS** → Double soumission questionnaire
6. **NO_UID dans les logs** → Session non authentifiée

### ✅ Patterns Normaux

1. **ROUTE → SOCKETIO_CREATE → GAME_START → GAME_END → QPT_SUBMIT**
2. **FILE_WRITE SUCCESS** avec `size_bytes > 0`
3. **TRIAL_INCREMENT** après chaque QPT
4. **STEP_INCREMENT** après HOFFMAN
5. **duration entre 45s et 180s** (selon configuration)

## 🔄 Rotation des Logs

- **Max size par fichier**: 10 MB
- **Nombre de backups**: 10 fichiers
- **Fichiers générés**: `all_actions.log`, `all_actions.log.1`, ..., `all_actions.log.10`
- **Nettoyage automatique**: Les plus anciens sont supprimés automatiquement

## 💡 Conseils

1. **Consulter régulièrement** `logs/errors.log` pour détecter les problèmes rapidement
2. **Utiliser `tools/log_summary.py`** après chaque session d'expérimentation
3. **Archiver les logs** des sessions importantes avant qu'ils ne soient écrasés
4. **Corréler avec les fichiers** dans `trajectories/` pour vérifier la cohérence

## 🆘 En Cas de Problème

Si les logs ne suffisent pas:

1. Vérifier les permissions du dossier `logs/` (doit être writable)
2. Vérifier l'espace disque disponible: `df -h`
3. Vérifier que l'application démarre correctement: `grep "APPLICATION DÉMARRÉE" logs/all_actions.log`
4. Consulter la console Python pour les erreurs critiques

---

**Dernière mise à jour**: 23 octobre 2025  
**Auteur**: Système de logging automatisé
