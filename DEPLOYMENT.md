# Déploiement — Overcooked-coop-voice (serveur Linux, collecte fiable, multi-participants)

Guide pas-à-pas pour héberger le jeu sur un **VPS OVH (Debian/Ubuntu)**, accessible aux
participants par un **simple lien**, avec **plusieurs participants en parallèle** et une
**collecte de données robuste** (sauvegarde même en cas de déconnexion / redémarrage / crash).

## Architecture

```
Participant ──HTTPS/WSS──> nginx (TLS, reverse proxy) ──HTTP/WS──> gunicorn -k eventlet -w 1
                                  │                                   (app:app, état en mémoire)
                                  └── /static/ servi directement       │
                                                                       ├── trajectories/ (données)
systemd: overcooked.service (supervise, redémarre, arrêt en douceur)   └── instance/db.sqlite
systemd: overcooked-backup.timer (sauvegarde rsync + tar daté /30 min)
```

> **Un seul worker eventlet, impératif.** L'app garde l'état des parties en mémoire de
> processus (non partagé entre workers). Pour plus de charge : **CPU plus rapide** (scale
> vertical), jamais plus de workers. Le multi-worker casserait l'affinité participant↔partie
> et provoquerait des pertes de données.

---

## 1. Provisionner le VPS

- Choisir une image **Debian 12** ou **Ubuntu LTS** simple (ignorer le template Docker/n8n :
  inutile ici, on déploie en natif).
- Créer/utiliser un utilisateur non-root (ex. `cesar`). Les exemples ci-dessous utilisent
  ce nom et les chemins `/home/cesar/...` — **les adapter** à votre serveur.
- Paquets système :
  ```bash
  sudo apt update
  sudo apt install -y nginx certbot python3-certbot-nginx sqlite3 rsync git python3-venv
  ```
- Pare-feu : n'ouvrir que **80** et **443**. Le port applicatif **5000 reste en loopback**
  (gunicorn bind `127.0.0.1:5000`).
  ```bash
  sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw enable
  ```
- **DNS** : créer un enregistrement **A** `overcooked.mondomaine.fr` → IPv4 du VPS (et AAAA
  si IPv6). *Sans domaine propre :* utiliser le hostname OVH par défaut (`vpsXXXX.ovh.net`)
  pour Let's Encrypt.

## 2. Récupérer le code

```bash
git clone https://github.com/CesarConstanty/Overcooked-coop-voice.git \
  /home/cesar/python-projects/Overcooked-coop-voice
cd /home/cesar/python-projects/Overcooked-coop-voice
ls overcooked_ai_py/   # DOIT être non vide (paquet vendoré dans le dépôt)
```

## 3. Environnement Python

```bash
python3 -m venv /home/cesar/environnements/overcooked
/home/cesar/environnements/overcooked/bin/pip install -U pip
/home/cesar/environnements/overcooked/bin/pip install -r requirements.txt   # gunicorn<23 inclus
# Repro figée (recommandé pour la prod) :
/home/cesar/environnements/overcooked/bin/pip freeze > requirements.lock.txt
```

> **gunicorn < 23 requis.** Le worker `eventlet` a été retiré de gunicorn ≥ 23 (eventlet
> est en maintenance). `requirements.txt` épingle `gunicorn<23` (testé avec 22.0.0 +
> eventlet 0.39). Ne pas « upgrader » gunicorn sans worker eventlet de remplacement.

## 4. Fichier d'environnement `/etc/overcooked.env`

```bash
sudo cp deploy/overcooked.env.example /etc/overcooked.env
# Générer une clé STABLE (à ne plus jamais changer) :
python3 -c "import os;print(os.urandom(32).hex())"
sudoedit /etc/overcooked.env   # coller SECRET_KEY, régler CORS_ALLOWED_ORIGINS=https://<FQDN>
sudo chmod 600 /etc/overcooked.env
sudo chown cesar:cesar /etc/overcooked.env
```

Variables clés : `FLASK_ENV=production`, `SECRET_KEY=...` (stable !), `CORS_ALLOWED_ORIGINS`,
`BIND=127.0.0.1:5000`. (voir [deploy/overcooked.env.example](deploy/overcooked.env.example))

## 5. Config applicative

- `MAX_GAMES` dans [config.json](config.json) : déjà à **15** (≈ participants simultanés en
  phase de jeu + marge). À **ajuster avec le load-test** (étape 9).
- Vérifier `config_test.completion_link` = bon code de complétion Prolific.

## 6. nginx + TLS (Let's Encrypt)

```bash
sudo cp deploy/nginx-overcooked.conf /etc/nginx/sites-available/overcooked
sudo sed -i 's/overcooked.exemple.fr/<VOTRE_FQDN>/g' /etc/nginx/sites-available/overcooked
# adapter aussi le chemin alias /static/ si le dépôt n'est pas dans /home/cesar/...
sudo ln -s /etc/nginx/sites-available/overcooked /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d <VOTRE_FQDN>     # émet le certificat + réécrit le vhost + renouvellement auto
```

## 7. Service systemd

```bash
sudo cp deploy/overcooked.service /etc/systemd/system/overcooked.service
# adapter User/Group, WorkingDirectory et le chemin du venv si besoin
sudo systemctl daemon-reload
sudo systemctl enable --now overcooked
journalctl -u overcooked -f    # attendre "[WARMUP] caches d'environnement préchauffés", aucun traceback
```

## 8. Smoke test

```bash
curl -fsS https://<FQDN>/healthz            # -> ok
curl -s -o /dev/null -w "%{http_code}\n" https://<FQDN>/debug   # -> 404 (fermé en prod)
```
Puis, dans un navigateur : `https://<FQDN>/?TEST_UID=smoke1&CONFIG=config_test`
- jouer un essai jusqu'au bout → un fichier apparaît :
  `trajectories/config_test/smoke1/<trial_id>.json` ;
- le questionnaire post-essai s'enchaîne ; vérifier
  `trajectories/config_test/smoke1/smoke1_suivis_passation.json` (timing client) ;
- **parallélisme** : ouvrir 2 navigateurs/profils avec des `TEST_UID` distincts simultanément
  → deux dossiers distincts, parties fluides, pas de collision.

**Tests data-safety** (à faire au moins une fois) :
- *Déconnexion* en plein essai (fermer l'onglet) → fichier sous `_interrupted/`. Rouvrir le
  même lien → reprise au bon essai (progression SQLite).
- *Redémarrage* avec un essai actif : `sudo systemctl restart overcooked` → l'essai actif est
  écrit sous `_interrupted/`, log `[SHUTDOWN_FLUSH]`, **aucun** `[TRIAL_SAVE_LOST]`.
- *Checkpoint* : pendant un essai, observer `trajectories/config_test/<uid>/_checkpoint/<trial_id>.json`
  se mettre à jour, puis disparaître après complétion.

## 9. Load-test (fixer MAX_GAMES)

Sur le CPU de prod, avant le lancement :
```bash
/home/cesar/environnements/overcooked/bin/pip install "python-socketio[client]" requests websocket-client
for K in 2 4 8 12 16; do
  /home/cesar/environnements/overcooked/bin/python scripts/loadtest.py \
    --base-url https://<FQDN> --clients $K --duration 90
done
```
Plafond sûr = plus grand `K` où **p95(intervalle state_pong) < ~150 ms** et **0 déconnexion**.
Régler `MAX_GAMES ≈ plafond × 0,7` dans `config.json`, puis `systemctl restart overcooked`.

## 10. Sauvegardes

```bash
sudo cp deploy/overcooked-backup.service /etc/systemd/system/
sudo cp deploy/overcooked-backup.timer   /etc/systemd/system/
# adapter User/Group/chemins dans le .service
sudo mkdir -p /var/backups/overcooked && sudo chown cesar:cesar /var/backups/overcooked
sudo systemctl daemon-reload
sudo systemctl enable --now overcooked-backup.timer
sudo systemctl start overcooked-backup.service   # exécution immédiate de contrôle
ls -lh /var/backups/overcooked/                  # un overcooked_*.tar.gz doit apparaître
```
**Surveillance des logs** (mettre une alerte dessus) :
- `[TRIAL_SAVE_LOST]` → perte totale d'un essai : **alerte immédiate** ;
- `[TRIAL_SAVE_BACKUP]` → repli `trajectories/_backup/` : à investiguer ;
- `[DISK_LOW]` → espace disque sous le seuil : parties refusées ;
- surveiller le contenu de `trajectories/_backup/` et `_interrupted/`.
  ```bash
  journalctl -u overcooked | grep -E "TRIAL_SAVE_LOST|TRIAL_SAVE_BACKUP|DISK_LOW"
  ```

## 11. Lien participant (Prolific)

- URL d'étude Prolific : `https://<FQDN>/?CONFIG=config_test`
  (Prolific ajoute `&PROLIFIC_PID=<id>` automatiquement).
- Vérifier que le code de complétion Prolific correspond à `completion_link`.
- Faire **un pilote en réel** (1–2 participants) avant l'ouverture.

## 12. Exploitation

- **Redéploiement / redémarrage** : de préférence quand aucune partie n'est active (le flush
  d'arrêt protège, mais évite d'interrompre des essais). Vérifier l'activité avant :
  `journalctl -u overcooked -n0 -f` puis `systemctl restart overcooked`.
- **Mise à jour du code** : `git pull` + `pip install -r requirements.txt` si deps changées,
  puis `systemctl restart overcooked` (hors créneau de passation).
- **Logs** : `journalctl -u overcooked` (gunicorn) et `logs/server.log` (rotatif, 10 Mo × 50).
- **Restauration** : décompresser le dernier `overcooked_*.tar.gz` de `/var/backups/overcooked`
  par-dessus `trajectories/` + `instance/db.sqlite` (service arrêté).

## Variables d'environnement (récap)

| Variable | Défaut | Rôle |
|---|---|---|
| `FLASK_ENV` | `production` | `production` ⇒ pas de debug, cookies Secure, ProxyFix, clé persistée |
| `SECRET_KEY` | (persistée sous `instance/secret_key` en prod) | Signature des cookies — **doit rester stable** |
| `CORS_ALLOWED_ORIGINS` | `*` si non défini | Origine(s) autorisées (mettre `https://<FQDN>`) |
| `BIND` | `127.0.0.1:5000` | Adresse d'écoute gunicorn (loopback derrière nginx) |
| `SESSION_COOKIE_SECURE` | `true` en prod | Cookie envoyé seulement en HTTPS (`0` pour test HTTP) |
| `TRUST_PROXY` | `true` en prod | Active ProxyFix (schéma/IP réels derrière nginx) |
| `MIN_FREE_DISK_MB` | `500` | Sous ce seuil libre, refuse de lancer un essai |
| `TRAJECTORY_CHECKPOINT_EVERY` | `50` | Fréquence (frames) des checkpoints de trajectoire |
| `ENABLE_DEBUG_ENDPOINT` | `false` | Ouvre `/debug` en prod (triage ponctuel seulement) |
| `HOST` / `PORT` | `0.0.0.0` / `5000` | Uniquement pour le mode dev `python app.py` |

## Notes de sécurité / fiabilité

- `SECRET_KEY` **stable** : un changement invalide les sessions actives (reprise possible via
  le lien, mais à éviter). Le fichier `instance/` ne doit pas être éphémère.
- TLS doit être **actif avant** d'envoyer le lien (cookies `Secure`). Pour un test HTTP, poser
  `SESSION_COOKIE_SECURE=0`.
- `TimeoutStopSec=120` (systemd) **>** `graceful_timeout=90` (gunicorn) : ne pas réduire, sinon
  SIGKILL pendant une sauvegarde.
