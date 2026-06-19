#!/usr/bin/env bash
# Sauvegarde des données d'expérience : trajectories/ + instance/db.sqlite.
# Idempotent, conçu pour cron / timer systemd. Miroir rsync + snapshot daté tar.gz.
set -euo pipefail

# Racine du dépôt (adapter si besoin) : par défaut, le dossier parent de ce script.
SRC="${OVERCOOKED_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DEST="${OVERCOOKED_BACKUP_DIR:-/var/backups/overcooked}"
MIN_FREE_MB="${OVERCOOKED_BACKUP_MIN_FREE_MB:-1024}"   # refuse si < 1 Gio libre à destination
KEEP_TARS="${OVERCOOKED_BACKUP_KEEP:-30}"               # nb de snapshots datés conservés

mkdir -p "$DEST/mirror"

# --- Contrôle d'espace disque (échoue bruyamment ; capturé par journald/cron) ---
free_mb="$(df -Pm "$DEST" | awk 'NR==2{print $4}')"
if [ "${free_mb:-0}" -lt "$MIN_FREE_MB" ]; then
    echo "[BACKUP][FATAL] seulement ${free_mb}Mo libres à $DEST (< ${MIN_FREE_MB}Mo). Abandon." >&2
    exit 1
fi

# --- 1) Miroir incrémental des trajectoires (inclut _backup/ et _interrupted/) ---
if [ -d "$SRC/trajectories" ]; then
    if command -v rsync >/dev/null 2>&1; then
        rsync -a --delete "$SRC/trajectories/" "$DEST/mirror/trajectories/"
    else
        # Repli sans rsync : copie complète (moins efficace, mais fiable).
        rm -rf "$DEST/mirror/trajectories"
        mkdir -p "$DEST/mirror/trajectories"
        cp -a "$SRC/trajectories/." "$DEST/mirror/trajectories/"
    fi
fi

# --- 2) Copie cohérente de la base SQLite (db de progression des participants) ---
DB=""
for cand in "$SRC/instance/db.sqlite" "$SRC/db.sqlite"; do
    [ -f "$cand" ] && DB="$cand" && break
done
if [ -n "$DB" ]; then
    if command -v sqlite3 >/dev/null 2>&1; then
        sqlite3 "$DB" ".backup '$DEST/mirror/db.sqlite'"
    else
        cp -p "$DB" "$DEST/mirror/db.sqlite"
    fi
fi

# --- 3) Snapshot daté immuable (récupération point-dans-le-temps) ---
ts="$(date -u +%Y%m%dT%H%M%SZ)"
( cd "$DEST/mirror" && tar -czf "$DEST/overcooked_${ts}.tar.gz" . )

# --- 4) Rétention : ne garder que les KEEP_TARS snapshots les plus récents ---
ls -1t "$DEST"/overcooked_*.tar.gz 2>/dev/null | tail -n +"$((KEEP_TARS+1))" | xargs -r rm -f

echo "[BACKUP][OK] $ts -> $DEST (libre: ${free_mb}Mo)"
