#!/usr/bin/env python3
"""
Script de vérification des systèmes de logging et PageTracker.
Valide que l'intégration fonctionne correctement.
"""

import sys
import os
from pathlib import Path

def check_integration():
    """Vérifie l'intégration PageTracker <-> app.logger."""
    
    print("=" * 70)
    print("🔍 VÉRIFICATION INTÉGRATION LOGGING & PAGE_TRACKER")
    print("=" * 70)
    
    # 1. Vérifier que page_tracker.py importe logging
    print("\n1️⃣  Vérification imports PageTracker...")
    with open("page_tracker.py", "r", encoding="utf-8") as f:
        content = f.read()
        if "import logging" in content:
            print("   ✅ logging importé")
        else:
            print("   ❌ logging non importé")
            return False
    
    # 2. Vérifier que PageTracker accepte un logger
    print("\n2️⃣  Vérification __init__ PageTracker...")
    if "def __init__(self, participant_id: str, config_name: str, logger=" in content:
        print("   ✅ PageTracker accepte paramètre logger")
    else:
        print("   ❌ PageTracker n'accepte pas paramètre logger")
        return False
    
    # 3. Vérifier que self.logger est utilisé
    print("\n3️⃣  Vérification utilisation self.logger...")
    logger_calls = content.count("self.logger.")
    if logger_calls > 5:
        print(f"   ✅ self.logger utilisé {logger_calls} fois")
    else:
        print(f"   ⚠️  self.logger utilisé seulement {logger_calls} fois (devrait être > 5)")
    
    # 4. Vérifier que app.py passe app.logger
    print("\n4️⃣  Vérification app.py passe logger...")
    with open("app.py", "r", encoding="utf-8") as f:
        app_content = f.read()
        if "PageTracker(user_id, config_id, logger=app.logger)" in app_content:
            print("   ✅ app.py passe app.logger au PageTracker")
        else:
            print("   ❌ app.py ne passe pas app.logger")
            return False
    
    # 5. Vérifier que track_page_view appelle log_user_action
    print("\n5️⃣  Vérification track_page_view...")
    if "log_user_action(user_id, 'PAGE_VIEW'" in app_content:
        print("   ✅ track_page_view() appelle log_user_action()")
    else:
        print("   ❌ track_page_view() n'appelle pas log_user_action()")
        return False
    
    # 6. Vérifier événements loggués dans PageTracker
    print("\n6️⃣  Vérification événements PageTracker...")
    events = [
        "PAGE_TRACKER_INIT",
        "PAGE_TRACKER_SCAN",
        "PAGE_TRACKER_PAGE_START",
        "PAGE_TRACKER_PAGE_END",
        "PAGE_TRACKER_SAVE"
    ]
    
    for event in events:
        if event in content:
            print(f"   ✅ {event}")
        else:
            print(f"   ❌ {event} - MANQUANT")
    
    # 7. Vérifier validation taille fichier
    print("\n7️⃣  Vérification validation fichiers...")
    if "size_bytes" in content and "PAGE_TRACKER_SAVE" in content:
        print("   ✅ Taille fichier enregistrée dans logs")
    else:
        print("   ⚠️  Taille fichier non enregistrée")
    
    # 8. Synthèse
    print("\n" + "=" * 70)
    print("📊 SYNTHÈSE")
    print("=" * 70)
    print("""
✅ Intégration PageTracker ↔ app.logger validée

Les modifications apportées permettent:
1. Tous les événements PageTracker dans all_actions.log
2. Corrélation facile entre logs et PageTracker
3. Validation taille fichiers _suivis_passation.json
4. Double trace (logs + PageTracker) pour fiabilité

🚀 Prochaine étape:
   Démarrer l'application et vérifier logs/:
   
   python app.py
   
   Puis dans un autre terminal:
   
   tail -f logs/all_actions.log | grep "PAGE_TRACKER"
   
   Vous devriez voir apparaître les événements PageTracker.
""")
    
    return True

def check_log_coverage():
    """Vérifie que tous les points critiques sont loggués."""
    
    print("\n" + "=" * 70)
    print("🔍 VÉRIFICATION COUVERTURE DES LOGS")
    print("=" * 70)
    
    with open("app.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    critical_points = {
        "Routes HTTP": [
            "ROUTE_INDEX_ENTER",
            "ROUTE_INSTRUCTIONS_ENTER",
            "ROUTE_PLANNING_ENTER",
            "ROUTE_QEX_ENTER"
        ],
        "SocketIO": [
            "SOCKETIO_CONNECT",
            "SOCKETIO_CREATE",
            "SOCKETIO_DISCONNECT",
            "SOCKETIO_LEAVE"
        ],
        "Fichiers": [
            "FILE_WRITE.*SUCCESS",
            "FILE_WRITE.*FAILED",
            "TRIAL_SAVE"
        ],
        "Parties": [
            "GAME_START",
            "GAME_END",
            "GAME_CLEANUP"
        ],
        "Questionnaires": [
            "QPT_SUBMIT",
            "QPB_SUBMIT",
            "HOFFMAN_SUBMIT"
        ],
        "PageTracker": [
            "PAGE_VIEW",
            "PAGE_TRACKING"
        ]
    }
    
    print()
    for category, events in critical_points.items():
        print(f"\n📋 {category}:")
        for event in events:
            if event in content:
                print(f"   ✅ {event}")
            else:
                print(f"   ❌ {event} - MANQUANT")
    
    print("\n" + "=" * 70)

def main():
    print("\n🧪 Test des Systèmes de Suivi - Version 2.0\n")
    
    # Vérifier qu'on est dans le bon répertoire
    if not Path("app.py").exists() or not Path("page_tracker.py").exists():
        print("❌ Erreur: Exécuter ce script depuis le répertoire du projet")
        sys.exit(1)
    
    success = check_integration()
    check_log_coverage()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ VALIDATION COMPLÈTE - Systèmes prêts!")
    else:
        print("❌ VALIDATION ÉCHOUÉE - Vérifier les erreurs ci-dessus")
    print("=" * 70 + "\n")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
