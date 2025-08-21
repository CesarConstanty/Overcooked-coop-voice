import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.planning.planners import MotionPlanner

layouts = [
    "V1_layout_combination_01", "V1_layout_combination_02", "V1_layout_combination_03","V1_layout_combination_10", "V1_layout_combination_11", 
    "V1_layout_combination_12","V1_layout_combination_19","V1_layout_combination_04", "V1_layout_combination_05", "V1_layout_combination_06",
    "V1_layout_combination_13", "V1_layout_combination_14", "V1_layout_combination_15","V1_layout_combination_20","V1_layout_combination_07", 
    "V1_layout_combination_08", "V1_layout_combination_09","V1_layout_combination_16", "V1_layout_combination_17", "V1_layout_combination_18",
    "V1_layout_combination_21"
]
layouts_dir = "overcooked_ai_py/data/layouts/generation_cesar/demo"

for layout in layouts:
    print(f"Processing {layout}")
    mdp = OvercookedGridworld.from_layout_name(layout, layouts_dir)
    MotionPlanner.compute_mp(f"{layout}_mp.pkl", mdp, [])
