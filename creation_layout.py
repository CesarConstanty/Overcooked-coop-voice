#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Éditeur visuel de layouts Overcooked.

Petit programme autonome qui ouvre une fenêtre pour créer, lire et modifier
les fichiers ``.layout`` utilisés dans l'expérience. On définit la taille de la
grille puis on place les objets du jeu (comptoirs, marmites, distributeurs,
service, départs des joueurs, etc.) au clic. La grille est rendue avec les vrais
sprites du jeu pour rester fidèle à ce que voient les participants.

Lancement :
    python creation_layout.py
    python creation_layout.py --layout <fichier.layout>
    python creation_layout.py --layouts-dir <dossier>

Conventions du dépôt : identifiants en anglais, commentaires en français.
"""

import argparse
import ast
import json
import os

# ---------------------------------------------------------------------------
# Chemins de base
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LAYOUTS_DIR = os.path.join(
    REPO_ROOT, "overcooked_ai_py", "data", "layouts", "generation_cesar_2"
)

# Spritesheets réutilisés (PNG + JSON de rectangles, format TexturePacker).
# static/assets/terrain* contient trash_bin (poubelle) et cutting_board (planche),
# absents de overcooked_ai_py/data/graphics.
SHEET_PATHS = {
    "terrain": ("static/assets/terrain.png", "static/assets/terrain.json"),
    "terrain_cut": ("static/assets/terrain_cut.png", "static/assets/terrain_cut.json"),
    "objects": (
        "overcooked_ai_py/data/graphics/objects.png",
        "overcooked_ai_py/data/graphics/objects.json",
    ),
    "chefs": (
        "overcooked_ai_py/data/graphics/chefs.png",
        "overcooked_ai_py/data/graphics/chefs.json",
    ),
}

# ---------------------------------------------------------------------------
# Légende des symboles de grille (cf. overcooked_mdp.py)
# ---------------------------------------------------------------------------
PLAYER_DIGITS = "123456789"
# Caractères qui ferment le terrain (autorisés sur les bords).
NON_FREE_CHARS = set("XOPDSTYABCE")
VALID_CHARS = set("XOPDSTYABCE123456789 ")

# Outils (symbole -> libellé FR), dans l'ordre d'affichage de la palette.
TILE_TOOLS = [
    (" ", "Sol"),
    ("X", "Comptoir / Mur"),
    ("P", "Marmite"),
    ("O", "Distrib. oignon"),
    ("T", "Distrib. tomate"),
    ("D", "Distrib. assiettes"),
    ("S", "Service"),
    ("C", "Planche à découper"),
    ("E", "Poubelle"),
    ("Y", "Counter-goal"),
    ("A", "Distrib. asym. J1"),
    ("B", "Distrib. asym. J2"),
]
TILE_LABELS = dict(TILE_TOOLS)
TILE_LABELS.update({d: "Joueur %s" % d for d in PLAYER_DIGITS})

# Ingrédients connus (interne -> FR).
INGREDIENTS_FR = {"onion": "oignon", "tomato": "tomate"}

# Distributeurs asymétriques : 'A' est exclusif au joueur d'index 0 (chiffre '1'),
# 'B' au joueur d'index 1 (chiffre '2') -- cf. overcooked_mdp.py (allowed_idx).
# Le rôle (humain / IA) de chaque index dépend de la config de l'expérience
# (playerZero / playerOne). Dans config_test (layouts generation_cesar_2),
# playerZero="Planning" => joueur 1 = IA, et playerOne (défaut "human") => joueur 2 = H.
DISPENSER_PLAYER_DIGIT = {"A": "1", "B": "2"}
DEFAULT_HUMAN_DIGIT = "2"


def role_for_digit(digit, human_digit):
    """Renvoie 'H' (humain) ou 'IA' pour un chiffre joueur donné."""
    return "H" if digit == human_digit else "IA"


def tool_label(symbol, human_digit):
    """Libellé FR d'un outil, avec le rôle (H/IA) pour joueurs et distributeurs."""
    if symbol in DISPENSER_PLAYER_DIGIT:
        return "Distrib. asym. (%s)" % role_for_digit(DISPENSER_PLAYER_DIGIT[symbol], human_digit)
    if symbol in ("1", "2"):
        return "Joueur %s (%s)" % (symbol, role_for_digit(symbol, human_digit))
    if symbol in "3456789":
        return "Joueur %s" % symbol
    return TILE_LABELS.get(symbol, symbol)

# ---------------------------------------------------------------------------
# Import optionnel du moteur Overcooked (validation fidèle au jeu)
# ---------------------------------------------------------------------------
ENGINE_AVAILABLE = False
_ENGINE_IMPORT_ERROR = None
try:
    from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld

    ENGINE_AVAILABLE = True
except Exception as exc:  # pragma: no cover - dépend de l'environnement
    OvercookedGridworld = None
    _ENGINE_IMPORT_ERROR = exc


# ===========================================================================
# 1. Lecture / écriture des fichiers .layout (round-trip fidèle)
# ===========================================================================
# Les fichiers .layout sont des littéraux de dict Python (lus par eval() dans le
# dépôt). On utilise ast.literal_eval, plus sûr (pas d'exécution de code), avec
# une substitution de float('inf') (présent dans tutorial_3.layout) qui n'est
# pas un littéral accepté par literal_eval.
_INF_SENTINEL = "__OC_INF__"
_NEG_INF_SENTINEL = "__OC_NEG_INF__"


def parse_layout_text(text):
    """Renvoie le dict d'un fichier .layout sans exécuter de code arbitraire."""
    safe = (
        text.replace("float('inf')", repr(_INF_SENTINEL))
        .replace('float("inf")', repr(_INF_SENTINEL))
        .replace("float('-inf')", repr(_NEG_INF_SENTINEL))
        .replace('float("-inf")', repr(_NEG_INF_SENTINEL))
    )
    data = ast.literal_eval(safe)
    return _restore_sentinels(data)


def _restore_sentinels(obj):
    """Reconvertit les sentinelles en float('inf') / float('-inf')."""
    if obj == _INF_SENTINEL:
        return float("inf")
    if obj == _NEG_INF_SENTINEL:
        return float("-inf")
    if isinstance(obj, dict):
        return {k: _restore_sentinels(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_restore_sentinels(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_restore_sentinels(v) for v in obj)
    return obj


def grid_string_to_rows(grid_str):
    """Découpe le bloc grille triple-quote en matrice rectangulaire de chars.

    Reproduit le nettoyage du moteur (``layout_row.strip()``) : comme tout le
    bord est non-libre (jamais un espace), le strip ne mange aucune case réelle.
    On re-padde ensuite à droite à la largeur commune.
    """
    rows = [line.strip() for line in grid_str.split("\n")]
    rows = [r for r in rows if r != ""]
    if not rows:
        return [["X"]]
    width = max(len(r) for r in rows)
    return [list(r.ljust(width)) for r in rows]


# Préfixe d'alignement du bloc grille, reproduit le style des fichiers commités
# (4 espaces + clé + 2 espaces + triple-quote). L'indentation n'affecte pas le
# parsing (le moteur fait strip()) mais garde un rendu lisible.
GRID_KEY_PREFIX = '    "grid":  """'
GRID_ROW_INDENT = " " * len(GRID_KEY_PREFIX)


def rows_to_grid_block(rows):
    """Reconstruit le bloc ``"grid": \"\"\"...\"\"\"`` aligné."""
    lines = ["".join(row) for row in rows]
    out = [GRID_KEY_PREFIX + lines[0]]
    for line in lines[1:]:
        out.append(GRID_ROW_INDENT + line)
    return "\n".join(out) + '"""'


def _repr_value(value):
    """repr() Python ré-parsable ; ré-émet float('inf') en token littéral."""
    if isinstance(value, float):
        if value == float("inf"):
            return "float('inf')"
        if value == float("-inf"):
            return "float('-inf')"
        if value != value:  # NaN
            return "float('nan')"
    if isinstance(value, dict):
        return "{" + ", ".join(
            "%s: %s" % (repr(k), _repr_value(v)) for k, v in value.items()
        ) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_repr_value(v) for v in value) + "]"
    if isinstance(value, tuple):
        inner = ", ".join(_repr_value(v) for v in value)
        return "(" + inner + ("," if len(value) == 1 else "") + ")"
    return repr(value)


def serialize_layout(rows, metadata):
    """Sérialise (grille + métadonnées) au format .layout canonique.

    La grille reste un bloc triple-quote lisible ; les autres clés sont écrites
    via ``_repr_value`` (ré-parsable, gère float('inf')). L'ordre d'insertion
    des clés est préservé.
    """
    parts = ["{", rows_to_grid_block(rows) + ","]
    for key, value in metadata.items():
        parts.append("    %s: %s," % (repr(key), _repr_value(value)))
    parts.append("}")
    return "\n".join(parts) + "\n"


# ===========================================================================
# 2. Validation (réutilise le moteur si disponible)
# ===========================================================================
def _local_assert_valid_grid(grid):
    """Réplique exacte de OvercookedGridworld._assert_valid_grid (repli)."""
    height = len(grid)
    assert height > 0, "Grille vide"
    width = len(grid[0])
    assert all(len(row) == width for row in grid), "Ragged grid"

    def is_not_free(c):
        return c in "XOPDSTYABCE"

    for y in range(height):
        assert is_not_free(grid[y][0]), "Left border must not be free"
        assert is_not_free(grid[y][-1]), "Right border must not be free"
    for x in range(width):
        assert is_not_free(grid[0][x]), "Top border must not be free"
        assert is_not_free(grid[-1][x]), "Bottom border must not be free"

    all_elements = [e for row in grid for e in row]
    digits = [e for e in all_elements if e in PLAYER_DIGITS]
    num_players = len(digits)
    assert num_players > 0, "No players (digits) in grid"
    assert sorted(map(int, digits)) == list(
        range(1, num_players + 1)
    ), "Some players were missing"
    assert all(c in "XOPDSTYABCE123456789 " for c in all_elements), "Invalid character in grid"
    assert all_elements.count("1") == 1, "'1' must be present exactly once"
    assert all_elements.count("D") >= 1, "'D' must be present at least once"
    assert all_elements.count("S") >= 1, "'S' must be present at least once"
    assert all_elements.count("P") >= 1, "'P' must be present at least once"
    assert (
        all_elements.count("O") >= 1
        or all_elements.count("T") >= 1
        or all_elements.count("A") >= 1
        or all_elements.count("B") >= 1
    ), "'O', 'T', 'A' or 'B' must be present at least once"


def validate_grid_rows(rows):
    """(ok, message) — utilise le moteur si présent, sinon le repli local."""
    grid = [list(r) for r in rows]
    try:
        if ENGINE_AVAILABLE:
            OvercookedGridworld._assert_valid_grid(grid)
        else:
            _local_assert_valid_grid(grid)
        return True, "Layout valide ✓"
    except AssertionError as exc:
        return False, str(exc)
    except Exception as exc:  # pragma: no cover - défensif
        return False, "Erreur: %s" % exc


# ===========================================================================
# 3. Modèle (état découplé de l'UI)
# ===========================================================================
class LayoutModel:
    """Grille éditable + métadonnées préservées."""

    def __init__(self):
        self.grid = [["X"]]
        self.metadata = {}
        self.filepath = None
        self.dirty = False
        self.new(7, 7)

    # --- dimensions -------------------------------------------------------
    @property
    def height(self):
        return len(self.grid)

    @property
    def width(self):
        return len(self.grid[0]) if self.grid else 0

    def in_bounds(self, x, y):
        return 0 <= y < self.height and 0 <= x < self.width

    def is_border(self, x, y):
        return x == 0 or y == 0 or x == self.width - 1 or y == self.height - 1

    # --- création / redimensionnement ------------------------------------
    @staticmethod
    def _blank_grid(width, height):
        return [
            [
                "X" if (x == 0 or y == 0 or x == width - 1 or y == height - 1) else " "
                for x in range(width)
            ]
            for y in range(height)
        ]

    def new(self, width, height, num_players=2):
        """Nouvelle grille : bord X, intérieur sol, quelques départs joueurs."""
        self.grid = self._blank_grid(width, height)
        interior = [
            (x, y) for y in range(1, height - 1) for x in range(1, width - 1)
        ]
        for i in range(min(num_players, len(interior))):
            x, y = interior[i]
            self.grid[y][x] = str(i + 1)
        self.metadata = {
            "start_all_orders": [
                {"ingredients": ["onion"]},
                {"ingredients": ["tomato"]},
            ],
            "order_triplets": [],
            "counter_goals": [],
            "cutting_board_symbol": "C",
        }
        self.filepath = None
        self.dirty = False

    def resize(self, width, height):
        """Redimensionne en conservant l'intérieur (ancrage haut-gauche)."""
        old = self.grid
        old_h, old_w = len(old), len(old[0])
        new = self._blank_grid(width, height)
        for y in range(min(old_h, height)):
            for x in range(min(old_w, width)):
                # On ne recopie que l'intérieur ; le bord reste imposé en X.
                if 0 < x < width - 1 and 0 < y < height - 1:
                    new[y][x] = old[y][x]
        self.grid = new
        self.dirty = True

    # --- édition ----------------------------------------------------------
    def set_cell(self, x, y, symbol):
        """Pose un symbole. Renvoie (ok, message_erreur_ou_None)."""
        if not self.in_bounds(x, y):
            return False, None
        if symbol in PLAYER_DIGITS:
            if self.is_border(x, y):
                return False, "Un départ joueur doit être à l'intérieur (pas sur un bord)."
            # Unicité : effacer l'éventuelle occurrence existante de ce joueur.
            for yy in range(self.height):
                for xx in range(self.width):
                    if self.grid[yy][xx] == symbol:
                        self.grid[yy][xx] = " "
            self.grid[y][x] = symbol
        else:
            self.grid[y][x] = symbol
        self.dirty = True
        return True, None

    def remove_players_above(self, max_player):
        """Efface de la grille tout chiffre joueur > max_player."""
        for y in range(self.height):
            for x in range(self.width):
                c = self.grid[y][x]
                if c in PLAYER_DIGITS and int(c) > max_player:
                    self.grid[y][x] = " "

    def max_player(self):
        digits = [int(c) for row in self.grid for c in row if c in PLAYER_DIGITS]
        return max(digits) if digits else 0

    # --- métadonnées ------------------------------------------------------
    def grid_rows(self):
        return ["".join(row) for row in self.grid]

    def has_counter_goals(self):
        return any(c == "Y" for row in self.grid for c in row)

    def validate(self):
        return validate_grid_rows(self.grid_rows())


def materialize_counter_goals(rows, metadata):
    """Force en 'Y' les cases listées dans counter_goals mais pas marquées."""
    coords = metadata.get("counter_goals") or []
    for coord in coords:
        try:
            x, y = int(coord[0]), int(coord[1])
        except (TypeError, ValueError, IndexError):
            continue
        if 0 <= y < len(rows) and 0 <= x < len(rows[0]):
            rows[y][x] = "Y"


# ===========================================================================
# 4. Cache de sprites (découpe PIL des spritesheets)
# ===========================================================================
from PIL import Image, ImageDraw, ImageFont, ImageTk  # noqa: E402  (après constantes)

# Mapping symbole -> (clé spritesheet, nom de frame) pour la tuile de base.
_DIRECT_FRAMES = {
    " ": ("terrain", "floor"),
    "X": ("terrain", "counter"),
    "O": ("terrain", "onions"),
    "T": ("terrain", "tomatoes"),
    "P": ("terrain", "pot"),
    "D": ("terrain", "dishes"),
    "S": ("terrain", "serve"),
    "E": ("terrain", "trash_bin"),
}
# Sprites de chef par joueur (couleurs présentes dans chefs.json).
_PLAYER_CHEF = {
    "1": "SOUTH-bluehat",
    "2": "SOUTH-greenhat",
    "3": "SOUTH-orangehat",
    "4": "SOUTH-purplehat",
    "5": "SOUTH-redhat",
}
# Couleurs de repli si une découpe échoue.
_FALLBACK_COLOR = {
    " ": (181, 152, 90),
    "X": (130, 110, 70),
    "P": (90, 90, 90),
    "O": (210, 180, 70),
    "T": (200, 70, 60),
    "D": (200, 200, 210),
    "S": (80, 150, 80),
    "C": (150, 120, 80),
    "E": (60, 60, 60),
    "Y": (70, 160, 90),
    "A": (160, 140, 90),
    "B": (160, 140, 90),
}


class SpriteCache:
    """Charge les spritesheets et fournit des ImageTk.PhotoImage par symbole.

    Les PhotoImage sont conservés dans ``self._cache`` (référence forte) pour
    éviter le ramasse-miettes de tkinter (sinon : tuiles blanches).
    """

    def __init__(self, root=REPO_ROOT):
        self.root = root
        self._sheets = {}  # clé -> (PIL.Image RGBA, {frame: (l, u, r, d)})
        self._cache = {}   # (symbole, taille, human_digit) -> ImageTk.PhotoImage
        self._fonts = {}
        # Chiffre du joueur humain (l'autre est l'IA) ; pilote les libellés A/B.
        self.human_digit = DEFAULT_HUMAN_DIGIT

    # --- chargement des planches -----------------------------------------
    def _sheet(self, key):
        if key not in self._sheets:
            png_rel, json_rel = SHEET_PATHS[key]
            img = Image.open(os.path.join(self.root, png_rel)).convert("RGBA")
            raw = json.load(open(os.path.join(self.root, json_rel)))
            frames = raw["frames"] if isinstance(raw, dict) and "frames" in raw else raw
            if isinstance(frames, list):  # format atlas (liste)
                frames = {f["filename"]: f for f in frames}
            rects = {}
            for name, info in frames.items():
                fr = info["frame"]
                rects[name.rsplit(".", 1)[0]] = (
                    fr["x"],
                    fr["y"],
                    fr["x"] + fr["w"],
                    fr["y"] + fr["h"],
                )
            self._sheets[key] = (img, rects)
        return self._sheets[key]

    def _crop(self, sheet_key, frame_name, size):
        img, rects = self._sheet(sheet_key)
        if frame_name not in rects:
            raise KeyError(frame_name)
        tile = img.crop(rects[frame_name])
        if tile.size != (size, size):
            # NEAREST : garde le pixel-art net comme dans le jeu.
            tile = tile.resize((size, size), Image.NEAREST)
        return tile.convert("RGBA").copy()

    def _font(self, px):
        if px not in self._fonts:
            try:
                self._fonts[px] = ImageFont.load_default(size=px)
            except Exception:
                self._fonts[px] = ImageFont.load_default()
        return self._fonts[px]

    # --- composition ------------------------------------------------------
    def _draw_glyph(self, img, text, size, fill=(230, 30, 30, 255), corner=False):
        draw = ImageDraw.Draw(img)
        if corner:
            ratio = 0.30 if len(text) > 1 else 0.42  # "IA" tient dans le coin
        else:
            ratio = 0.55
        font = self._font(int(size * ratio))
        if corner:
            pos = (2, 1)
        else:
            bbox = draw.textbbox((0, 0), text, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pos = ((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1])
        # Contour noir pour la lisibilité, puis le texte.
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            draw.text((pos[0] + dx, pos[1] + dy), text, font=font, fill=(0, 0, 0, 255))
        draw.text(pos, text, font=font, fill=fill)

    @staticmethod
    def _tint(img, rgba):
        img.alpha_composite(Image.new("RGBA", img.size, rgba))

    def _compose(self, symbol, size):
        # Symboles avec frame terrain directe.
        if symbol in _DIRECT_FRAMES:
            sheet, frame = _DIRECT_FRAMES[symbol]
            return self._crop(sheet, frame, size)
        # Planche à découper (atlas terrain_cut), repli comptoir + glyphe.
        if symbol == "C":
            try:
                return self._crop("terrain_cut", "cutting_board", size)
            except Exception:
                img = self._crop("terrain", "counter", size)
                self._draw_glyph(img, "C", size)
                return img
        # Counter-goal : comptoir teinté + glyphe.
        if symbol == "Y":
            img = self._crop("terrain", "counter", size)
            self._tint(img, (50, 170, 90, 90))
            self._draw_glyph(img, "Y", size, fill=(255, 255, 255, 255))
            return img
        # Distributeurs asymétriques : comptoir + ingrédient + lettre.
        if symbol in ("A", "B"):
            img = self._crop("terrain", "counter", size)
            try:
                overlay = self._crop("objects", "onion" if symbol == "A" else "tomato", size)
                img.alpha_composite(overlay)
            except Exception:
                pass
            # Affiche le rôle (H / IA) du joueur exclusif à ce distributeur.
            role = role_for_digit(DISPENSER_PLAYER_DIGIT[symbol], self.human_digit)
            self._draw_glyph(img, role, size, fill=(20, 20, 20, 255), corner=True)
            return img
        # Départs joueurs : sol + chef + badge numéro.
        if symbol in PLAYER_DIGITS:
            img = self._crop("terrain", "floor", size)
            chef = _PLAYER_CHEF.get(symbol, "SOUTH")
            try:
                img.alpha_composite(self._crop("chefs", chef, size))
            except Exception:
                try:
                    img.alpha_composite(self._crop("chefs", "SOUTH", size))
                except Exception:
                    pass
            self._draw_glyph(img, symbol, size, fill=(255, 230, 0, 255), corner=True)
            return img
        # Inconnu : sol + glyphe.
        img = self._crop("terrain", "floor", size)
        self._draw_glyph(img, symbol, size)
        return img

    def _fallback(self, symbol, size):
        """Tuile pleine couleur + glyphe si les sprites sont indisponibles."""
        color = _FALLBACK_COLOR.get(symbol, (120, 120, 120))
        img = Image.new("RGBA", (size, size), color + (255,))
        label = symbol if symbol != " " else ""
        if label:
            self._draw_glyph(img, label, size, fill=(0, 0, 0, 255))
        return img

    def get(self, symbol, size):
        # human_digit fait partie de la clé : changer l'humain régénère A/B.
        key = (symbol, size, self.human_digit)
        if key not in self._cache:
            try:
                img = self._compose(symbol, size)
            except Exception:
                img = self._fallback(symbol, size)
            self._cache[key] = ImageTk.PhotoImage(img)
        return self._cache[key]


# ===========================================================================
# 5. Interface tkinter
# ===========================================================================
import tkinter as tk  # noqa: E402
from tkinter import filedialog, messagebox, simpledialog, ttk  # noqa: E402


class SizeDialog(simpledialog.Dialog):
    """Demande largeur × hauteur."""

    def __init__(self, parent, title, init_w, init_h):
        self.init_w, self.init_h = init_w, init_h
        super().__init__(parent, title)

    def body(self, master):
        self.var_w = tk.IntVar(value=self.init_w)
        self.var_h = tk.IntVar(value=self.init_h)
        ttk.Label(master, text="Largeur :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Spinbox(master, from_=3, to=30, textvariable=self.var_w, width=6).grid(row=0, column=1, padx=4)
        ttk.Label(master, text="Hauteur :").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Spinbox(master, from_=3, to=30, textvariable=self.var_h, width=6).grid(row=1, column=1, padx=4)
        return None

    def validate(self):
        if self.var_w.get() < 3 or self.var_h.get() < 3:
            messagebox.showwarning("Taille invalide", "Minimum 3 × 3.", parent=self)
            return False
        return True

    def apply(self):
        self.result = (self.var_w.get(), self.var_h.get())


class RecipeDialog(simpledialog.Dialog):
    """Compose une recette (1 à 3 ingrédients)."""

    def body(self, master):
        self.var_o = tk.IntVar(value=1)
        self.var_t = tk.IntVar(value=0)
        ttk.Label(master, text="Oignons :").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Spinbox(master, from_=0, to=3, textvariable=self.var_o, width=6).grid(row=0, column=1, padx=4)
        ttk.Label(master, text="Tomates :").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Spinbox(master, from_=0, to=3, textvariable=self.var_t, width=6).grid(row=1, column=1, padx=4)
        return None

    def validate(self):
        total = self.var_o.get() + self.var_t.get()
        if total < 1 or total > 3:
            messagebox.showwarning(
                "Recette invalide", "Une recette doit contenir 1 à 3 ingrédients.", parent=self
            )
            return False
        return True

    def apply(self):
        ingredients = ["onion"] * self.var_o.get() + ["tomato"] * self.var_t.get()
        self.result = {"ingredients": ingredients}


class TripletDialog(simpledialog.Dialog):
    """Saisit un triplet d'indices vers start_all_orders."""

    def __init__(self, parent, title, num_recipes):
        self.num_recipes = num_recipes
        super().__init__(parent, title)

    def body(self, master):
        self.vars = [tk.IntVar(value=0) for _ in range(3)]
        for i in range(3):
            ttk.Label(master, text="Indice %d :" % (i + 1)).grid(row=i, column=0, sticky="w", padx=4, pady=4)
            ttk.Spinbox(
                master, from_=0, to=max(0, self.num_recipes - 1), textvariable=self.vars[i], width=6
            ).grid(row=i, column=1, padx=4)
        return None

    def validate(self):
        if self.num_recipes == 0:
            messagebox.showwarning("Aucune recette", "Ajoutez d'abord des recettes.", parent=self)
            return False
        for v in self.vars:
            if v.get() < 0 or v.get() >= self.num_recipes:
                messagebox.showwarning(
                    "Indice invalide",
                    "Les indices doivent être entre 0 et %d." % (self.num_recipes - 1),
                    parent=self,
                )
                return False
        return True

    def apply(self):
        self.result = [v.get() for v in self.vars]


class ToolPalette(ttk.Frame):
    """Palette d'outils : un bouton (icône + libellé) par symbole."""

    ICON_SIZE = 36

    def __init__(self, parent, app):
        super().__init__(parent, padding=6)
        self.app = app
        self.buttons = {}

        ttk.Label(self, text="Outils", font=("", 11, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 4))
        self._tools_frame = ttk.Frame(self)
        self._tools_frame.grid(row=1, column=0, columnspan=2, sticky="nw")
        for i, (symbol, _label) in enumerate(TILE_TOOLS):
            self._make_button(self._tools_frame, symbol, i)

        ttk.Separator(self, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="ew", pady=6)
        ttk.Label(self, text="Joueurs", font=("", 11, "bold")).grid(row=3, column=0, columnspan=2)
        count_row = ttk.Frame(self)
        count_row.grid(row=4, column=0, columnspan=2, pady=2)
        ttk.Label(count_row, text="Nombre :").pack(side="left")
        self.var_players = tk.IntVar(value=self.app.num_players)
        ttk.Spinbox(
            count_row, from_=1, to=9, textvariable=self.var_players, width=4,
            command=self._on_player_count,
        ).pack(side="left", padx=4)
        # Choix du joueur humain (l'autre est l'IA) : pilote les libellés H/IA.
        human_row = ttk.Frame(self)
        human_row.grid(row=5, column=0, columnspan=2, pady=2)
        ttk.Label(human_row, text="Humain :").pack(side="left")
        self.var_human = tk.StringVar(value=self.app.human_digit)
        ttk.Radiobutton(
            human_row, text="J1", value="1", variable=self.var_human, command=self._on_human
        ).pack(side="left")
        ttk.Radiobutton(
            human_row, text="J2", value="2", variable=self.var_human, command=self._on_human
        ).pack(side="left")
        self._players_frame = ttk.Frame(self)
        self._players_frame.grid(row=6, column=0, columnspan=2, sticky="nw")
        self.rebuild_players()

    def _make_button(self, parent, symbol, index):
        icon = self.app.sprites.get(symbol, self.ICON_SIZE)
        btn = tk.Button(
            parent, image=icon, text=" " + tool_label(symbol, self.app.human_digit),
            compound="left", anchor="w",
            width=150, relief="raised", bd=2,
            command=lambda s=symbol: self.app.select_tool(s),
        )
        btn.image = icon  # référence forte
        btn.default_bg = btn.cget("background")  # couleur par défaut (varie selon l'OS)
        btn.grid(row=index, column=0, sticky="ew", pady=1)
        self.buttons[symbol] = btn

    def rebuild_players(self):
        for child in self._players_frame.winfo_children():
            child.destroy()
        for symbol in self.buttons.copy():
            if symbol in PLAYER_DIGITS:
                del self.buttons[symbol]
        for i in range(self.app.num_players):
            self._make_button(self._players_frame, str(i + 1), i)
        self.highlight(self.app.current_symbol)

    def refresh_labels(self):
        """Met à jour icônes + libellés (rôles H/IA) après changement d'humain."""
        for symbol, btn in self.buttons.items():
            icon = self.app.sprites.get(symbol, self.ICON_SIZE)
            btn.configure(image=icon, text=" " + tool_label(symbol, self.app.human_digit))
            btn.image = icon
        self.highlight(self.app.current_symbol)

    def _on_player_count(self):
        self.app.set_num_players(self.var_players.get())

    def _on_human(self):
        self.app.set_human_player(self.var_human.get())

    def highlight(self, symbol):
        for sym, btn in self.buttons.items():
            if sym == symbol:
                btn.configure(relief="sunken", bg="#ffe89a")
            else:
                btn.configure(relief="raised", bg=btn.default_bg)


class GridCanvas(ttk.Frame):
    """Zone de dessin : rendu des tuiles + édition à la souris."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.canvas = tk.Canvas(self, bg="#2b2b2b", highlightthickness=0)
        hbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.cell_items = {}
        self._last_cell = None

        c = self.canvas
        c.bind("<Button-1>", lambda e: self._paint(e, self.app.current_symbol))
        c.bind("<B1-Motion>", lambda e: self._paint(e, self.app.current_symbol))
        c.bind("<ButtonRelease-1>", lambda e: self._reset_last())
        c.bind("<Button-3>", lambda e: self._paint(e, " "))
        c.bind("<B3-Motion>", lambda e: self._paint(e, " "))
        c.bind("<ButtonRelease-3>", lambda e: self._reset_last())
        c.bind("<Motion>", self._hover)
        c.bind("<Leave>", lambda e: c.delete("hover"))
        # Zoom (Ctrl + molette) ; molette seule = défilement.
        c.bind("<Control-MouseWheel>", lambda e: self.app.zoom(1 if e.delta > 0 else -1))
        c.bind("<Control-Button-4>", lambda e: self.app.zoom(1))
        c.bind("<Control-Button-5>", lambda e: self.app.zoom(-1))
        c.bind("<MouseWheel>", lambda e: c.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        c.bind("<Shift-MouseWheel>", lambda e: c.xview_scroll(-1 if e.delta > 0 else 1, "units"))
        c.bind("<Button-4>", lambda e: c.yview_scroll(-1, "units"))
        c.bind("<Button-5>", lambda e: c.yview_scroll(1, "units"))

    def _reset_last(self):
        self._last_cell = None

    def _event_cell(self, event):
        ts = self.app.tile_size
        x = int(self.canvas.canvasx(event.x) // ts)
        y = int(self.canvas.canvasy(event.y) // ts)
        return x, y

    def _paint(self, event, symbol):
        x, y = self._event_cell(event)
        if not self.app.model.in_bounds(x, y):
            return
        if self._last_cell == (x, y):
            return
        self._last_cell = (x, y)
        self.app.paint_cell(x, y, symbol)

    def _hover(self, event):
        self.canvas.delete("hover")
        x, y = self._event_cell(event)
        if not self.app.model.in_bounds(x, y):
            return
        ts = self.app.tile_size
        self.canvas.create_rectangle(
            x * ts, y * ts, (x + 1) * ts, (y + 1) * ts,
            outline="#ffd400", width=2, tags=("hover",),
        )

    def redraw(self):
        c = self.canvas
        c.delete("all")
        self.cell_items = {}
        ts = self.app.tile_size
        m = self.app.model
        for y in range(m.height):
            for x in range(m.width):
                img = self.app.sprites.get(m.grid[y][x], ts)
                item = c.create_image(x * ts, y * ts, anchor="nw", image=img, tags=("cell",))
                self.cell_items[(x, y)] = item
        for x in range(m.width + 1):
            c.create_line(x * ts, 0, x * ts, m.height * ts, fill="#3a3a3a")
        for y in range(m.height + 1):
            c.create_line(0, y * ts, m.width * ts, y * ts, fill="#3a3a3a")
        c.config(scrollregion=(0, 0, m.width * ts, m.height * ts))

    def update_cell(self, x, y):
        if (x, y) not in self.cell_items:
            self.redraw()
            return
        img = self.app.sprites.get(self.app.model.grid[y][x], self.app.tile_size)
        self.canvas.itemconfig(self.cell_items[(x, y)], image=img)


class MetadataPanel(ttk.Frame):
    """Édition des clés présentes dans test01.layout + autres clés préservées."""

    def __init__(self, parent, app):
        super().__init__(parent, padding=6)
        self.app = app

        ttk.Label(self, text="Métadonnées", font=("", 11, "bold")).pack(anchor="w")

        # Recettes (start_all_orders)
        rec = ttk.LabelFrame(self, text="Recettes (start_all_orders)", padding=4)
        rec.pack(fill="x", pady=4)
        self.recipes_list = tk.Listbox(rec, height=5)
        self.recipes_list.pack(fill="x")
        rec_btns = ttk.Frame(rec)
        rec_btns.pack(fill="x", pady=2)
        ttk.Button(rec_btns, text="Ajouter", command=self.add_recipe).pack(side="left")
        ttk.Button(rec_btns, text="Supprimer", command=self.remove_recipe).pack(side="left", padx=4)

        # Triplets (order_triplets)
        tri = ttk.LabelFrame(self, text="Triplets (order_triplets)", padding=4)
        tri.pack(fill="x", pady=4)
        self.triplets_list = tk.Listbox(tri, height=4)
        self.triplets_list.pack(fill="x")
        tri_btns = ttk.Frame(tri)
        tri_btns.pack(fill="x", pady=2)
        ttk.Button(tri_btns, text="Ajouter", command=self.add_triplet).pack(side="left")
        ttk.Button(tri_btns, text="Supprimer", command=self.remove_triplet).pack(side="left", padx=4)

        # Réglages
        cfg = ttk.LabelFrame(self, text="Réglages", padding=4)
        cfg.pack(fill="x", pady=4)
        row = ttk.Frame(cfg)
        row.pack(fill="x")
        ttk.Label(row, text="Symbole planche :").pack(side="left")
        self.var_cut = tk.StringVar(value="C")
        ent = ttk.Entry(row, textvariable=self.var_cut, width=4)
        ent.pack(side="left", padx=4)
        self.var_cut.trace_add("write", self._on_cut_symbol)
        self.lbl_goals = ttk.Label(cfg, text="counter-goals : 0 (auto depuis Y)")
        self.lbl_goals.pack(anchor="w", pady=2)

        # Clés préservées (lecture seule)
        self.lbl_other = ttk.Label(self, text="", foreground="#666", wraplength=240, justify="left")
        self.lbl_other.pack(anchor="w", pady=4)

    # --- helpers ----------------------------------------------------------
    @staticmethod
    def _recipe_label(recipe):
        names = [INGREDIENTS_FR.get(i, i) for i in recipe.get("ingredients", [])]
        return " + ".join(names) if names else "(vide)"

    def refresh(self):
        meta = self.app.model.metadata
        self.recipes_list.delete(0, "end")
        for i, recipe in enumerate(meta.get("start_all_orders", []) or []):
            self.recipes_list.insert("end", "%d. %s" % (i, self._recipe_label(recipe)))
        self.triplets_list.delete(0, "end")
        for triplet in meta.get("order_triplets", []) or []:
            self.triplets_list.insert("end", str(list(triplet)))
        self.var_cut.set(str(meta.get("cutting_board_symbol", "C")))
        self.lbl_goals.config(
            text="counter-goals : %d (auto depuis Y)"
            % sum(row.count("Y") for row in self.app.model.grid)
        )
        handled = {"start_all_orders", "order_triplets", "cutting_board_symbol", "counter_goals"}
        others = [k for k in meta if k not in handled]
        self.lbl_other.config(
            text=("Clés préservées : " + ", ".join(others)) if others else ""
        )

    # --- callbacks --------------------------------------------------------
    def add_recipe(self):
        dlg = RecipeDialog(self.app, "Ajouter une recette")
        if dlg.result is not None:
            self.app.model.metadata.setdefault("start_all_orders", [])
            self.app.model.metadata["start_all_orders"].append(dlg.result)
            self.app.mark_dirty()
            self.refresh()

    def remove_recipe(self):
        sel = self.recipes_list.curselection()
        if not sel:
            return
        recipes = self.app.model.metadata.get("start_all_orders", [])
        idx = sel[0]
        if 0 <= idx < len(recipes):
            recipes.pop(idx)
            # Purge des triplets devenus hors-bornes.
            n = len(recipes)
            self.app.model.metadata["order_triplets"] = [
                t for t in self.app.model.metadata.get("order_triplets", [])
                if all(0 <= i < n for i in t)
            ]
            self.app.mark_dirty()
            self.refresh()

    def add_triplet(self):
        n = len(self.app.model.metadata.get("start_all_orders", []))
        dlg = TripletDialog(self.app, "Ajouter un triplet", n)
        if dlg.result is not None:
            self.app.model.metadata.setdefault("order_triplets", [])
            self.app.model.metadata["order_triplets"].append(dlg.result)
            self.app.mark_dirty()
            self.refresh()

    def remove_triplet(self):
        sel = self.triplets_list.curselection()
        if not sel:
            return
        triplets = self.app.model.metadata.get("order_triplets", [])
        idx = sel[0]
        if 0 <= idx < len(triplets):
            triplets.pop(idx)
            self.app.mark_dirty()
            self.refresh()

    def _on_cut_symbol(self, *_):
        self.app.model.metadata["cutting_board_symbol"] = self.var_cut.get()
        self.app.mark_dirty()


class StatusBar(ttk.Frame):
    """Barre d'état : dimensions, joueurs, validité (vert/rouge)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.info = ttk.Label(self, text="", anchor="w")
        self.info.pack(side="left", padx=8)
        self.validity = tk.Label(self, text="", anchor="e", padx=8)
        self.validity.pack(side="right")

    def set_info(self, text):
        self.info.config(text=text)

    def set_validity(self, ok, message):
        self.validity.config(
            text=message,
            bg="#bff0c0" if ok else "#f3b6b6",
            fg="#114411" if ok else "#661111",
        )

    def set_warning(self, message):
        self.validity.config(text=message, bg="#ffe2a6", fg="#664400")


class LayoutEditorApp(tk.Tk):
    """Fenêtre principale et orchestration."""

    def __init__(self, layouts_dir, initial_layout=None):
        super().__init__()
        self.title("Éditeur de layout Overcooked")
        self.geometry("1180x740")

        self.layouts_dir = layouts_dir
        self.sprites = SpriteCache()
        self.model = LayoutModel()
        self.tile_size = 48
        self.current_symbol = "X"
        self.num_players = max(2, self.model.max_player())
        # Joueur humain (l'autre est l'IA) ; défaut = config_test (joueur 2 = humain).
        self.human_digit = DEFAULT_HUMAN_DIGIT
        self.sprites.human_digit = DEFAULT_HUMAN_DIGIT

        self._build_menu()
        self._build_layout()

        if initial_layout:
            self.load(initial_layout)
        else:
            self.refresh_all()

        self.protocol("WM_DELETE_WINDOW", self.on_quit)

    # --- construction UI --------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Nouveau", accelerator="Ctrl+N", command=self.cmd_new)
        filem.add_command(label="Ouvrir…", accelerator="Ctrl+O", command=self.cmd_open)
        filem.add_separator()
        filem.add_command(label="Enregistrer", accelerator="Ctrl+S", command=self.cmd_save)
        filem.add_command(label="Enregistrer sous…", accelerator="Ctrl+Maj+S", command=self.cmd_save_as)
        filem.add_separator()
        filem.add_command(label="Quitter", command=self.on_quit)
        menubar.add_cascade(label="Fichier", menu=filem)

        gridm = tk.Menu(menubar, tearoff=0)
        gridm.add_command(label="Redimensionner…", command=self.cmd_resize)
        gridm.add_command(label="Valider", command=self.cmd_validate)
        menubar.add_cascade(label="Grille", menu=gridm)

        helpm = tk.Menu(menubar, tearoff=0)
        helpm.add_command(label="Légende des symboles", command=self.cmd_legend)
        menubar.add_cascade(label="Aide", menu=helpm)

        self.config(menu=menubar)
        self.bind("<Control-n>", lambda e: self.cmd_new())
        self.bind("<Control-o>", lambda e: self.cmd_open())
        self.bind("<Control-s>", lambda e: self.cmd_save())
        self.bind("<Control-Shift-S>", lambda e: self.cmd_save_as())
        self.bind("<Control-Shift-s>", lambda e: self.cmd_save_as())

    def _build_layout(self):
        toolbar = ttk.Frame(self, padding=4)
        toolbar.pack(side="top", fill="x")
        for text, cmd in (
            ("Nouveau", self.cmd_new), ("Ouvrir", self.cmd_open),
            ("Enregistrer", self.cmd_save), ("Enregistrer sous", self.cmd_save_as),
            ("Redimensionner", self.cmd_resize), ("Valider", self.cmd_validate),
        ):
            ttk.Button(toolbar, text=text, command=cmd).pack(side="left", padx=2)
        ttk.Label(toolbar, text="   (clic gauche = poser · clic droit = sol · Ctrl+molette = zoom)").pack(side="left")

        self.status = StatusBar(self)
        self.status.pack(side="bottom", fill="x")

        self.palette = ToolPalette(self, self)
        self.palette.pack(side="left", fill="y")

        self.meta_panel = MetadataPanel(self, self)
        self.meta_panel.pack(side="right", fill="y")

        self.grid_canvas = GridCanvas(self, self)
        self.grid_canvas.pack(side="left", fill="both", expand=True)

    # --- rafraîchissement -------------------------------------------------
    def refresh_all(self):
        self.palette.var_players.set(self.num_players)
        self.palette.rebuild_players()
        self.grid_canvas.redraw()
        self.meta_panel.refresh()
        self.refresh_validation()
        self.update_title()

    def refresh_validation(self):
        ok, message = self.model.validate()
        self.status.set_info(
            "Grille %d × %d · %d joueur(s)"
            % (self.model.width, self.model.height, self.model.max_player())
        )
        self.status.set_validity(ok, message)

    def update_title(self):
        name = os.path.basename(self.model.filepath) if self.model.filepath else "sans titre"
        star = " *" if self.model.dirty else ""
        self.title("Éditeur de layout Overcooked — %s%s" % (name, star))

    def mark_dirty(self):
        self.model.dirty = True
        self.update_title()

    # --- actions outils / édition ----------------------------------------
    def select_tool(self, symbol):
        self.current_symbol = symbol
        self.palette.highlight(symbol)

    def paint_cell(self, x, y, symbol):
        ok, message = self.model.set_cell(x, y, symbol)
        if not ok:
            if message:
                self.status.set_warning(message)
            return
        if symbol in PLAYER_DIGITS:
            self.grid_canvas.redraw()  # l'unicité a pu effacer une autre case
        else:
            self.grid_canvas.update_cell(x, y)
        self.meta_panel.refresh()
        self.refresh_validation()
        self.update_title()

    def set_num_players(self, n):
        n = max(1, min(9, int(n)))
        if n < self.model.max_player():
            self.model.remove_players_above(n)
            self.mark_dirty()
        self.num_players = n
        self.palette.rebuild_players()
        self.grid_canvas.redraw()
        self.refresh_validation()

    def zoom(self, direction):
        self.tile_size = max(16, min(96, self.tile_size + direction * 8))
        self.grid_canvas.redraw()

    def set_human_player(self, digit):
        """Désigne le joueur humain ; met à jour les libellés H/IA (affichage seul)."""
        self.human_digit = digit
        self.sprites.human_digit = digit
        self.palette.refresh_labels()
        self.grid_canvas.redraw()

    # --- commandes fichier ------------------------------------------------
    def _confirm_discard(self):
        if not self.model.dirty:
            return True
        return messagebox.askyesno(
            "Modifications non enregistrées", "Abandonner les modifications en cours ?"
        )

    def cmd_new(self):
        if not self._confirm_discard():
            return
        dlg = SizeDialog(self, "Nouvelle grille", 7, 7)
        if dlg.result is None:
            return
        w, h = dlg.result
        self.num_players = 2
        self.model.new(w, h, num_players=2)
        self.refresh_all()

    def cmd_open(self):
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(
            initialdir=self.layouts_dir,
            title="Ouvrir un layout",
            filetypes=[("Layout Overcooked", "*.layout"), ("Tous les fichiers", "*.*")],
        )
        if path:
            self.load(path)

    def load(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = parse_layout_text(f.read())
        except Exception as exc:
            messagebox.showerror("Erreur de lecture", "Impossible de lire le fichier :\n%s" % exc)
            return
        if not isinstance(data, dict) or "grid" not in data:
            messagebox.showerror("Erreur de lecture", "Fichier invalide : clé 'grid' absente.")
            return
        rows = grid_string_to_rows(data["grid"])
        metadata = {k: v for k, v in data.items() if k != "grid"}
        materialize_counter_goals(rows, metadata)
        self.model.grid = rows
        self.model.metadata = metadata
        self.model.filepath = path
        self.model.dirty = False
        self.num_players = max(2, self.model.max_player())
        self.refresh_all()

    def cmd_save(self):
        if self.model.filepath:
            self._save_to(self.model.filepath)
        else:
            self.cmd_save_as()

    def cmd_save_as(self):
        path = filedialog.asksaveasfilename(
            initialdir=self.layouts_dir,
            title="Enregistrer le layout",
            defaultextension=".layout",
            filetypes=[("Layout Overcooked", "*.layout")],
        )
        if path:
            self._save_to(path)

    def _save_to(self, path):
        # Réconciliation Y / counter_goals : la grille fait foi.
        if self.model.has_counter_goals():
            self.model.metadata["counter_goals"] = []
        else:
            self.model.metadata.setdefault("counter_goals", [])

        ok, message = self.model.validate()
        if not ok:
            if not messagebox.askyesno(
                "Layout invalide",
                "%s\n\nEnregistrer quand même ?" % message,
                default="no",
            ):
                return

        try:
            text = serialize_layout(self.model.grid, self.model.metadata)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, path)
        except Exception as exc:
            messagebox.showerror("Erreur d'écriture", "Impossible d'enregistrer :\n%s" % exc)
            return

        self.model.filepath = path
        self.model.dirty = False
        self.update_title()

        # Test de chargeabilité par le moteur (si disponible et grille valide).
        if ENGINE_AVAILABLE and ok:
            try:
                name = os.path.splitext(os.path.basename(path))[0]
                OvercookedGridworld.from_layout_name(name, os.path.dirname(path))
            except Exception as exc:
                messagebox.showwarning(
                    "Avertissement",
                    "Fichier enregistré, mais le moteur n'a pas pu le charger :\n%s" % exc,
                )
                return
        messagebox.showinfo("Enregistré", "Layout enregistré :\n%s" % path)

    def cmd_resize(self):
        dlg = SizeDialog(self, "Redimensionner la grille", self.model.width, self.model.height)
        if dlg.result is None:
            return
        w, h = dlg.result
        self.model.resize(w, h)
        self.grid_canvas.redraw()
        self.meta_panel.refresh()
        self.refresh_validation()
        self.update_title()

    def cmd_validate(self):
        ok, message = self.model.validate()
        if ok:
            messagebox.showinfo("Validation", "Layout valide ✓")
        else:
            messagebox.showerror("Layout invalide", message)

    def cmd_legend(self):
        lines = ["Légende des symboles :", ""]
        for symbol, _label in TILE_TOOLS:
            shown = "(espace)" if symbol == " " else symbol
            lines.append("  %s  =  %s" % (shown, tool_label(symbol, self.human_digit)))
        lines.append("  1-9  =  Départs des joueurs")
        human = "Joueur %s" % self.human_digit
        lines += [
            "",
            "Distributeurs asymétriques : A est réservé au joueur 1, B au joueur 2.",
            "Humain = %s (l'autre joueur est l'IA)." % human,
        ]
        messagebox.showinfo("Légende", "\n".join(lines))

    def on_quit(self):
        if self._confirm_discard():
            self.destroy()


# ===========================================================================
# 6. Point d'entrée
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(description="Éditeur visuel de layouts Overcooked")
    parser.add_argument("--layout", default=None, help="Fichier .layout à ouvrir au démarrage")
    parser.add_argument(
        "--layouts-dir", default=DEFAULT_LAYOUTS_DIR,
        help="Dossier initial des dialogues Ouvrir/Enregistrer",
    )
    args = parser.parse_args()

    try:
        app = LayoutEditorApp(args.layouts_dir, initial_layout=args.layout)
    except tk.TclError as exc:
        print("Aucun affichage graphique disponible (DISPLAY) : %s" % exc)
        print("Lancez ce programme dans un environnement avec interface graphique.")
        return
    app.mainloop()


if __name__ == "__main__":
    main()
