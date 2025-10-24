#!/usr/bin/env python3
"""
Script d'analyse des logs pour détecter les problèmes dans les sessions utilisateurs.

Usage:
    python tools/log_summary.py [--uid USER_ID] [--date YYYY-MM-DD]

Ce script analyse les fichiers de logs pour identifier:
- Sessions incomplètes (users démarrés mais pas terminés)
- Fichiers de données manquants ou incomplets
- Durées de jeu anormalement courtes
- Erreurs d'écriture de fichiers
- Déconnexions pendant les parties
"""

import re
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

class LogAnalyzer:
    def __init__(self, log_file='logs/all_actions.log'):
        self.log_file = log_file
        self.sessions = defaultdict(lambda: {
            'events': [],
            'errors': [],
            'file_writes': [],
            'games': []
        })
        
    def parse_log_line(self, line):
        """Parse une ligne de log et extrait les informations clés."""
        # Format: [2025-10-23 14:30:45] INFO | UID:user123 | CFG:config_1 | ... | message
        match = re.match(
            r'\[([^\]]+)\] (\w+) \| UID:([^\|]+) \| CFG:([^\|]+) \| .+ \| (.+)',
            line
        )
        if not match:
            return None
            
        timestamp, level, uid, config_id, message = match.groups()
        
        return {
            'timestamp': datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S'),
            'level': level,
            'uid': uid.strip(),
            'config_id': config_id.strip(),
            'message': message.strip()
        }
    
    def analyze(self):
        """Analyse le fichier de logs."""
        if not Path(self.log_file).exists():
            print(f"❌ Fichier de log introuvable: {self.log_file}")
            return
            
        print(f"📖 Analyse du fichier: {self.log_file}\n")
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                entry = self.parse_log_line(line)
                if not entry or entry['uid'] == 'NO_UID':
                    continue
                    
                uid = entry['uid']
                self.sessions[uid]['events'].append(entry)
                
                # Collecter les erreurs
                if entry['level'] in ['ERROR', 'WARNING']:
                    self.sessions[uid]['errors'].append(entry)
                
                # Collecter les écritures de fichiers
                if '[FILE_WRITE]' in entry['message']:
                    self.sessions[uid]['file_writes'].append(entry)
                
                # Collecter les infos de jeu
                if '[GAME_' in entry['message']:
                    self.sessions[uid]['games'].append(entry)
    
    def find_incomplete_sessions(self):
        """Identifie les sessions incomplètes."""
        print("=" * 80)
        print("🔍 SESSIONS INCOMPLÈTES")
        print("=" * 80)
        
        incomplete = []
        for uid, data in self.sessions.items():
            events = [e['message'] for e in data['events']]
            
            # Vérifier si l'utilisateur a commencé mais pas terminé
            has_start = any('ROUTE_INDEX_ENTER' in e or 'USER_NEW_CREATION' in e for e in events)
            has_end = any('ROUTE_PLANNING_COMPLETE' in e or 'QEX_' in e for e in events)
            
            if has_start and not has_end:
                last_event = data['events'][-1] if data['events'] else None
                incomplete.append({
                    'uid': uid,
                    'last_event': last_event['message'] if last_event else 'UNKNOWN',
                    'last_time': last_event['timestamp'] if last_event else None,
                    'total_events': len(data['events'])
                })
        
        if incomplete:
            for session in incomplete:
                print(f"\n👤 UID: {session['uid']}")
                print(f"   Dernier événement: {session['last_event']}")
                print(f"   Heure: {session['last_time']}")
                print(f"   Total événements: {session['total_events']}")
        else:
            print("✅ Aucune session incomplète détectée")
    
    def find_file_errors(self):
        """Identifie les erreurs d'écriture de fichiers."""
        print("\n" + "=" * 80)
        print("💾 ERREURS D'ÉCRITURE DE FICHIERS")
        print("=" * 80)
        
        errors_found = False
        for uid, data in self.sessions.items():
            failed_writes = [e for e in data['file_writes'] if 'FAILED' in e['message'] or 'ERROR' in e['level']]
            
            if failed_writes:
                errors_found = True
                print(f"\n👤 UID: {uid}")
                for write in failed_writes:
                    print(f"   ❌ {write['timestamp']} - {write['message']}")
        
        if not errors_found:
            print("✅ Aucune erreur d'écriture détectée")
    
    def find_short_games(self, min_duration=30):
        """Identifie les parties anormalement courtes."""
        print("\n" + "=" * 80)
        print(f"⏱️  PARTIES ANORMALEMENT COURTES (< {min_duration}s)")
        print("=" * 80)
        
        short_games = []
        for uid, data in self.sessions.items():
            game_events = data['games']
            
            # Apparier START et END
            for i, event in enumerate(game_events):
                if '[GAME_START]' in event['message']:
                    # Chercher le END correspondant
                    for j in range(i + 1, len(game_events)):
                        if '[GAME_END]' in game_events[j]['message']:
                            duration_match = re.search(r'duration=([\d.]+)s', game_events[j]['message'])
                            if duration_match:
                                duration = float(duration_match.group(1))
                                if duration < min_duration:
                                    short_games.append({
                                        'uid': uid,
                                        'duration': duration,
                                        'start_time': event['timestamp'],
                                        'end_event': game_events[j]['message']
                                    })
                            break
        
        if short_games:
            for game in short_games:
                print(f"\n👤 UID: {game['uid']}")
                print(f"   ⏱️  Durée: {game['duration']:.1f}s")
                print(f"   🕐 Démarrage: {game['start_time']}")
                print(f"   📝 Fin: {game['end_event']}")
        else:
            print(f"✅ Aucune partie < {min_duration}s détectée")
    
    def find_disconnects_during_game(self):
        """Identifie les déconnexions pendant les parties."""
        print("\n" + "=" * 80)
        print("🔌 DÉCONNEXIONS PENDANT LES PARTIES")
        print("=" * 80)
        
        disconnects = []
        for uid, data in self.sessions.items():
            events = data['events']
            
            for i, event in enumerate(events):
                if '[GAME_START]' in event['message']:
                    # Chercher déconnexion avant GAME_END
                    for j in range(i + 1, len(events)):
                        if 'SOCKETIO_DISCONNECT' in events[j]['message']:
                            # Vérifier si c'est avant GAME_END
                            game_ended = False
                            for k in range(i + 1, j):
                                if '[GAME_END]' in events[k]['message']:
                                    game_ended = True
                                    break
                            
                            if not game_ended:
                                disconnects.append({
                                    'uid': uid,
                                    'game_start': event['timestamp'],
                                    'disconnect': events[j]['timestamp'],
                                    'duration_before_disconnect': (events[j]['timestamp'] - event['timestamp']).total_seconds()
                                })
                            break
                        elif '[GAME_END]' in events[j]['message']:
                            break
        
        if disconnects:
            for dc in disconnects:
                print(f"\n👤 UID: {dc['uid']}")
                print(f"   🎮 Jeu démarré: {dc['game_start']}")
                print(f"   🔌 Déconnecté: {dc['disconnect']}")
                print(f"   ⏱️  Durée avant déconnexion: {dc['duration_before_disconnect']:.1f}s")
        else:
            print("✅ Aucune déconnexion pendant partie détectée")
    
    def generate_summary(self):
        """Génère un résumé global."""
        print("\n" + "=" * 80)
        print("📊 RÉSUMÉ GLOBAL")
        print("=" * 80)
        
        total_users = len(self.sessions)
        total_errors = sum(len(data['errors']) for data in self.sessions.values())
        total_writes = sum(len(data['file_writes']) for data in self.sessions.values())
        total_games = sum(len(data['games']) for data in self.sessions.values()) // 2  # START + END
        
        print(f"\n👥 Utilisateurs uniques: {total_users}")
        print(f"❌ Total erreurs/warnings: {total_errors}")
        print(f"💾 Total écritures fichiers: {total_writes}")
        print(f"🎮 Total parties: {total_games}")
        
        # Utilisateurs les plus actifs
        if self.sessions:
            most_active = sorted(self.sessions.items(), key=lambda x: len(x[1]['events']), reverse=True)[:5]
            print("\n🏆 Utilisateurs les plus actifs:")
            for uid, data in most_active:
                print(f"   {uid}: {len(data['events'])} événements")

def main():
    parser = argparse.ArgumentParser(description='Analyse les logs pour détecter les problèmes')
    parser.add_argument('--uid', help='Filtrer par UID spécifique')
    parser.add_argument('--date', help='Filtrer par date (YYYY-MM-DD)')
    parser.add_argument('--min-duration', type=int, default=30, 
                       help='Durée minimale d\'une partie en secondes (défaut: 30)')
    
    args = parser.parse_args()
    
    analyzer = LogAnalyzer()
    analyzer.analyze()
    
    # Filtrer si nécessaire
    if args.uid:
        analyzer.sessions = {k: v for k, v in analyzer.sessions.items() if k == args.uid}
    
    # Exécuter les analyses
    analyzer.find_incomplete_sessions()
    analyzer.find_file_errors()
    analyzer.find_short_games(args.min_duration)
    analyzer.find_disconnects_during_game()
    analyzer.generate_summary()
    
    print("\n" + "=" * 80)
    print("✅ Analyse terminée!")
    print("=" * 80 + "\n")

if __name__ == '__main__':
    main()
