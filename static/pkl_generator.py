import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.planning.planners import MotionPlanner

layouts = [
    "L10_R54_V06","L22_R69_V02","L26_R64_V08","L45_R59_V01","L53_R82_V02","L89_R63_V07","L99_R75_V05","L109_R79_V03","L114_R84_V10","L125_R38_V08","L186_R39_V10","L374_R83_V07",
    "L10_R54_V06_R90","L22_R69_V02_R90","L26_R64_V08_R90","L45_R59_V01_R90","L53_R82_V02_R90","L89_R63_V07_R90","L99_R75_V05_R90","L109_R79_V03_R90","L114_R84_V10_R90","L125_R38_V08_R90","L186_R39_V10_R90","L374_R83_V07_R90",
    "L10_R54_V06_R180","L22_R69_V02_R180","L26_R64_V08_R180","L45_R59_V01_R180","L53_R82_V02_R180","L89_R63_V07_R180","L99_R75_V05_R180","L109_R79_V03_R180","L114_R84_V10_R180","L125_R38_V08_R180","L186_R39_V10_R180","L374_R83_V07_R180"
]
layouts_dir = "overcooked_ai_py/data/layouts/generation_cesar"

for layout in layouts:
    print(f"Processing {layout}")
    mdp = OvercookedGridworld.from_layout_name(layout, layouts_dir)
    MotionPlanner.compute_mp(f"{layout}_mp.pkl", mdp, [])
