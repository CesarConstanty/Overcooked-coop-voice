# Installation sur serveur vierge — Overcooked-coop-voice

Procédure pour préparer un **serveur Linux vierge** (VPS OVH) au déploiement du jeu :
système, version de Python, environnement virtuel et dépendances **épinglées et testées**.
Pour la mise en service (nginx/TLS, systemd, sauvegardes, calibrage `MAX_GAMES`),
voir [../DEPLOYMENT.md](../DEPLOYMENT.md).

---

## 1. Cible validée

| Élément | Version testée | Notes |
|---|---|---|
| OS | **Debian 12 (bookworm)** | Ubuntu 22.04 LTS également OK. Choisir une image simple (pas le template Docker/n8n). |
| Architecture | **x86_64** | Les roues (wheels) numpy/scipy/greenlet/eventlet sont disponibles → pas de compilation. |
| Python | **3.11.2** (série 3.11.x) | Ne pas dépasser ce que supporte `eventlet 0.39` ; rester en 3.11. |

> Tout le bloc de dépendances ci-dessous a été **installé et vérifié dans un venv neuf**
> (`pip check` : aucune incohérence ; `import app` OK avec ces seuls paquets).

---

## 2. Paquets système (apt)

```bash
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-pip git \
  nginx certbot python3-certbot-nginx \
  sqlite3 rsync
```

| Paquet | Rôle |
|---|---|
| `python3` / `python3-venv` / `python3-pip` | exécution + environnement virtuel |
| `nginx` | reverse proxy (TLS, WebSocket, /static) — cf. DEPLOYMENT.md |
| `certbot` / `python3-certbot-nginx` | certificat HTTPS Let's Encrypt + renouvellement |
| `sqlite3` | copie cohérente de `instance/db.sqlite` pour les sauvegardes |
| `rsync` | miroir des `trajectories/` (repli `cp` automatique si absent) |

**Repli compilation** (seulement si une wheel manque pour votre archi) :
```bash
sudo apt install -y build-essential python3-dev
```

---

## 3. Code + environnement Python

```bash
# 1) Récupérer le code (overcooked_ai_py est VENDORÉ dans le dépôt : pas d'install pip)
#    Le jeu est sur la branche PUBLIQUE `serveur_test` : clone anonyme, aucun token requis.
#    `~` = home de l'utilisateur courant du serveur (peu importe son nom) ; git crée les dossiers parents.
git clone -b serveur_test \
  https://github.com/CesarConstanty/Overcooked-coop-voice.git \
  ~/python-projects/Overcooked-coop-voice
cd ~/python-projects/Overcooked-coop-voice
ls overcooked_ai_py/   # DOIT être non vide

# 2) Créer le venv et installer les dépendances de déploiement
python3 -m venv ~/environnements/overcooked
~/environnements/overcooked/bin/pip install -U pip
~/environnements/overcooked/bin/pip install -r python-projects/Overcooked-coop-voice/requirements_serv.txt
```

`requirements.txt` ne contient que le **runtime serveur**, en versions épinglées
(reproductible). Les outils dev/notebooks en sont volontairement exclus (§6).

---

## 4. Contraintes de versions CRITIQUES

| Composant | Version | Pourquoi c'est verrouillé |
|---|---|---|
| **gunicorn** | **22.0.0 (`<23`)** | ⚠️ Le worker **eventlet a été retiré dans gunicorn ≥ 23**. Avec gunicorn 23+, `worker_class=eventlet` est introuvable → le serveur **ne démarre pas**. Ne pas « upgrader ». |
| **eventlet** | **0.39.0** | Boucle asynchrone + `monkey_patch()` (tout le serveur tourne en greenlets sur 1 cœur). Compatible Python 3.11. |
| **Flask / Werkzeug** | 3.1.0 / 3.1.3 | Flask 3.x exige Werkzeug 3.x : garder le couple aligné. |
| **Flask-SocketIO / python-socketio / python-engineio** | 5.5.1 / 5.12.1 / 4.11.2 | Trio temps réel **sensible** : un décalage entre ces trois casse la WebSocket. À mettre à jour ensemble seulement. |
| **greenlet / dnspython** | 3.1.1 / 2.7.0 | Requis par eventlet. |
| **numpy / scipy / tqdm** | 2.3.2 / 1.16.0 / 4.67.1 | Moteur de jeu `overcooked_ai_py` (MDP / planification). |

---

## 5. Ce qui n'est PAS nécessaire côté serveur de jeu

Vérifié : le runtime serveur **ne charge pas** ces paquets (ils n'apparaissent que dans
des notebooks ou outils de conception). **Ne pas les installer sur le serveur** (poids,
surface d'attaque) :

`matplotlib`, `ipython`, `ipywidgets`, `jupyter*`, `pygame`, `pandas`, `scikit-learn`,
`ortools`, `pyaudio`, `pydub`, `pyttsx/pyttsx3`, `seaborn`, `gevent`, `flask-login`.

*(`gevent` et `flask-login` étaient historiquement déclarés mais ne sont plus importés au runtime.)*

---

## 6. Outils dev / admin optionnels (machine de travail, pas le serveur)

| Usage | Paquets à ajouter |
|---|---|
| Conception de layouts / notebooks (`creation_layout.py`, `compute_mlam.py`, `layout_explore.ipynb`) | `pip install matplotlib ipython ipywidgets pandas scikit-learn` |
| Test de charge (`scripts/loadtest.py`) — peut tourner sur le serveur ou ailleurs | `pip install "python-socketio[client]" websocket-client requests` |

---

## 7. Vérification post-installation

```bash
VENV=~/environnements/overcooked/bin

# a) Le module s'importe (déclenche le préchauffage des caches MDP/MLAM)
cd ~/python-projects/Overcooked-coop-voice
FLASK_ENV=development $VENV/python -c "import app; print('IMPORT OK')"

# b) Cohérence des dépendances
$VENV/pip check          # -> No broken requirements found.

# c) Lancement prod éphémère + sonde santé
FLASK_ENV=production SECRET_KEY=verif BIND=127.0.0.1:5000 \
  $VENV/gunicorn -c gunicorn.conf.py app:app &
sleep 3 && curl -fsS http://127.0.0.1:5000/healthz   # -> ok
kill %1
```

---

## 8. Reproductibilité (optionnel mais recommandé)

Pour figer l'environnement exact installé :
```bash
~/environnements/overcooked/bin/pip freeze > requirements.lock.txt
```
et réinstaller depuis ce lock sur les futures machines.

---

## 9. Étape suivante

Le serveur est prêt au niveau logiciel. Passer à **[../DEPLOYMENT.md](../DEPLOYMENT.md)** pour :
fichier d'environnement (`/etc/overcooked.env`, `SECRET_KEY` stable, `CORS_ALLOWED_ORIGINS`),
nginx + certbot (HTTPS), service systemd (1 worker eventlet), sauvegardes automatiques,
et **calibrage de `MAX_GAMES`** via `scripts/loadtest.py` avant le lancement.
