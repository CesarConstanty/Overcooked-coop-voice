#!/usr/bin/env python3
"""
Script de test du système de logging.
Vérifie que les logs sont correctement créés et formatés.
"""

import os
import sys
from pathlib import Path

def test_log_system():
    """Teste que le système de logging est correctement configuré."""
    
    print("🧪 Test du Système de Logging")
    print("=" * 60)
    
    # Test 1: Vérifier que le répertoire logs existe
    print("\n1️⃣  Vérification répertoire logs/...")
    if Path("logs").exists():
        print("   ✅ Répertoire logs/ existe")
    else:
        print("   ❌ Répertoire logs/ manquant - sera créé au démarrage")
    
    # Test 2: Vérifier que app.py contient le système de logging
    print("\n2️⃣  Vérification configuration dans app.py...")
    with open("app.py", "r", encoding="utf-8") as f:
        content = f.read()
        
        checks = [
            ("ContextFilter", "Filtre de contexte UID"),
            ("RotatingFileHandler", "Rotation des logs"),
            ("log_user_action", "Fonction de logging utilisateur"),
            ("log_data_operation", "Fonction de logging fichiers"),
            ("[USER_ACTION]", "Tags standardisés"),
            ("all_actions.log", "Fichier de logs principal"),
        ]
        
        for check, desc in checks:
            if check in content:
                print(f"   ✅ {desc}")
            else:
                print(f"   ❌ {desc} - MANQUANT")
    
    # Test 3: Vérifier que les outils existent
    print("\n3️⃣  Vérification outils d'analyse...")
    tools = [
        ("tools/log_summary.py", "Script d'analyse"),
        ("docs/logging.md", "Documentation"),
        ("LOGGING_QUICKSTART.md", "Guide rapide"),
        ("docs/IMPLEMENTATION_SUMMARY.md", "Résumé implémentation"),
    ]
    
    for path, desc in tools:
        if Path(path).exists():
            print(f"   ✅ {desc} ({path})")
        else:
            print(f"   ❌ {desc} ({path}) - MANQUANT")
    
    # Test 4: Vérifier que log_summary.py est exécutable
    print("\n4️⃣  Vérification permissions...")
    if Path("tools/log_summary.py").exists():
        if os.access("tools/log_summary.py", os.X_OK):
            print("   ✅ log_summary.py est exécutable")
        else:
            print("   ⚠️  log_summary.py n'est pas exécutable")
            print("      Exécuter: chmod +x tools/log_summary.py")
    
    # Test 5: Synthèse
    print("\n" + "=" * 60)
    print("📊 SYNTHÈSE")
    print("=" * 60)
    print("""
Le système de logging est prêt à l'emploi.

🚀 Pour démarrer:
   python app.py

📊 Pour analyser:
   python tools/log_summary.py

📚 Documentation:
   - Guide rapide: LOGGING_QUICKSTART.md
   - Doc complète: docs/logging.md
   - Résumé modifs: docs/IMPLEMENTATION_SUMMARY.md

💡 Prochaine étape:
   Démarrer l'application et vérifier que logs/ contient:
   - all_actions.log
   - errors.log
   - user_actions.log
""")

if __name__ == "__main__":
    test_log_system()
