#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Évaluateur avec correctifs - Compatible pipeline

Utilise l'évaluateur principal 2_layout_evaluator.py mais avec des correctifs 
pour le temps de cuisson déjà appliqués.
"""

import sys
import subprocess
from pathlib import Path

def main():
    """Lance l'évaluateur principal avec les correctifs déjà appliqués"""
    # Chemin vers l'évaluateur principal
    script_path = Path(__file__).parent.parent / "scripts" / "2_layout_evaluator.py"
    
    # Lancer l'évaluateur principal
    result = subprocess.run([
        sys.executable, str(script_path)
    ], cwd=Path(__file__).parent.parent)
    
    return result.returncode

if __name__ == "__main__":
    exit(main())
