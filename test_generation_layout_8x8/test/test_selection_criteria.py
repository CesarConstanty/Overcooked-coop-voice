#!/usr/bin/env python3
"""Analyse des critères de sélection des layouts"""

import json
import importlib.util
from pathlib import Path
from collections import defaultdict

def main():
    print("🔍 ANALYSE DES CRITÈRES DE SÉLECTION")
    print("=" * 50)
    
    # Import dynamique du sélecteur
    selector_path = Path(__file__).parent / "scripts" / "3_layout_selector.py"
    spec = importlib.util.spec_from_file_location("layout_selector", selector_path)
    selector_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(selector_module)
    
    LayoutMetrics = selector_module.LayoutMetrics
    LayoutCandidate = selector_module.LayoutCandidate
    LayoutSelector = selector_module.LayoutSelector
    
    # Charger les résultats
    with open('outputs/evaluation_results/evaluation_metrics_batch_0000.json', 'r') as f:
        data = json.load(f)
    
    metrics = data['metrics']
    print(f"📊 {len(metrics)} évaluations à analyser")
    
    # Grouper par layout
    layout_metrics = defaultdict(list)
    for m in metrics:
        layout_id = m['layout_id']
        lm = LayoutMetrics(
            layout_id=layout_id,
            layout_hash=m['layout_hash'],
            recipe_group_id=m['recipe_group_id'],
            solo_steps=m['solo_steps'],
            duo_steps=m['duo_steps'],
            exchanges_count=m['exchanges_count'],
            improvement_ratio=m['improvement_ratio'],
            evaluation_time=m['evaluation_time'],
            recipe_hash=m['recipe_hash']
        )
        layout_metrics[layout_id].append(lm)
    
    print(f"🏗️  {len(layout_metrics)} layouts uniques")
    
    # Analyser chaque layout
    selector = LayoutSelector()
    weights = {"cooperation": 0.4, "efficiency": 0.35, "exchanges": 0.25}
    
    scores = []
    cooperation_benefits = []
    
    for layout_id, metrics_list in layout_metrics.items():
        # Calculer le score moyen
        total_score = 0.0
        total_cooperation = 0.0
        
        for metrics in metrics_list:
            cooperation = metrics.cooperation_benefit()
            efficiency = metrics.efficiency_score()
            exchanges = metrics.exchange_score()
            
            score = (cooperation * weights['cooperation'] +
                    efficiency * weights['efficiency'] +
                    exchanges * weights['exchanges'])
            
            total_score += score
            total_cooperation += cooperation
        
        avg_score = total_score / len(metrics_list)
        avg_cooperation = total_cooperation / len(metrics_list)
        
        scores.append(avg_score)
        cooperation_benefits.append(avg_cooperation)
    
    # Statistiques
    print(f"\\n📈 STATISTIQUES DES SCORES:")
    print(f"   Score final:")
    print(f"     Min: {min(scores):.3f}")
    print(f"     Max: {max(scores):.3f}")
    print(f"     Moyenne: {sum(scores)/len(scores):.3f}")
    print(f"     Seuil requis: 0.5")
    print(f"     Layouts passant: {sum(1 for s in scores if s >= 0.5)}")
    
    print(f"\\n   Bénéfice coopération:")
    print(f"     Min: {min(cooperation_benefits):.3f}")
    print(f"     Max: {max(cooperation_benefits):.3f}")
    print(f"     Moyenne: {sum(cooperation_benefits)/len(cooperation_benefits):.3f}")
    print(f"     Seuil requis: 0.2")
    print(f"     Layouts passant: {sum(1 for c in cooperation_benefits if c >= 0.2)}")
    
    # Layouts qui passent les deux critères
    both_pass = sum(1 for s, c in zip(scores, cooperation_benefits) 
                   if s >= 0.5 and c >= 0.2)
    print(f"\\n🎯 Layouts passant TOUS les critères: {both_pass}")
    
    # Recommandations
    if both_pass == 0:
        print(f"\\n💡 RECOMMANDATIONS:")
        max_score = max(scores)
        max_coop = max(cooperation_benefits)
        
        if max_score < 0.5:
            print(f"   - Réduire min_final_score de 0.5 à {max_score * 0.9:.2f}")
        if max_coop < 0.2:
            print(f"   - Réduire min_cooperation_benefit de 0.2 à {max_coop * 0.9:.2f}")
    
    # Top 5 layouts
    print(f"\\n🏆 TOP 5 LAYOUTS:")
    layout_scores = [(layout_id, score, coop) 
                    for (layout_id, _), score, coop 
                    in zip(layout_metrics.items(), scores, cooperation_benefits)]
    
    top_layouts = sorted(layout_scores, key=lambda x: x[1], reverse=True)[:5]
    
    for i, (layout_id, score, coop) in enumerate(top_layouts):
        status = "✅" if score >= 0.5 and coop >= 0.2 else "❌"
        print(f"   {i+1}. {layout_id[:8]}... - Score: {score:.3f}, Coop: {coop:.3f} {status}")

if __name__ == "__main__":
    main()
