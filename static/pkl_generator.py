import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.planning.planners import MotionPlanner

layouts = [
    "test01",
    "test01_180",
    "test01_90",
    "test02",
    "test02_180",
    "test02_90",
    "test03",
    "test03_180",
    "test03_90",
    "test04",
    "test04_180",
    "test04_90",
    "test05",
    "test05_180",
    "test05_90",
    "test06",
    "test06_180",
    "test06_90",
    "test07",
    "test07_180",
    "test07_90",
    "test08",
    "test08_180",
    "test08_90",
    "test09",
    "test09_180",
    "test09_90",
    "test10",
    "test10_180",
    "test10_90",
    "test11",
    "test11_180",
    "test11_90",
    "test12",
    "test12_180",
    "test12_90",
]
layouts_dir = "overcooked_ai_py/data/layouts/generation_cesar_2"

for layout in layouts:
    print(f"Processing {layout}")
    mdp = OvercookedGridworld.from_layout_name(layout, layouts_dir)
    MotionPlanner.compute_mp(f"{layout}_mp.pkl", mdp, [])
