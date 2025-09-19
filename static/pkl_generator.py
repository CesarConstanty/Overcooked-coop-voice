import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.planning.planners import MotionPlanner

layouts = [
    "Ldd18_R04_V00","Ldd18_R11_V00","Ldd18_R27_V00","Ldd18_R71_V00","Ldd19_R54_V00","Ldd19_R64_V00","Ldd19_R82_V00","Ldd21_R75_V00","Ldd22_R03_V00","Ldd22_R29_V00","Ldd22_R69_V00","Ldd22_R78_V00",
    "Ldd18_R04_V00_R90","Ldd18_R11_V00_R90","Ldd18_R27_V00_R90","Ldd18_R71_V00_R90","Ldd19_R54_V00_R90","Ldd19_R64_V00_R90","Ldd19_R82_V00_R90","Ldd21_R75_V00_R90","Ldd22_R03_V00_R90","Ldd22_R29_V00_R90","Ldd22_R69_V00_R90","Ldd22_R78_V00_R90",
    "Ldd18_R04_V00_R180","Ldd18_R11_V00_R180","Ldd18_R27_V00_R180","Ldd18_R71_V00_R180","Ldd19_R54_V00_R180","Ldd19_R64_V00_R180","Ldd19_R82_V00_R180","Ldd21_R75_V00_R180","Ldd22_R03_V00_R180","Ldd22_R29_V00_R180","Ldd22_R69_V00_R180","Ldd22_R78_V00_R180"
]
layouts_dir = "overcooked_ai_py/data/layouts/generation_cesar"

for layout in layouts:
    print(f"Processing {layout}")
    mdp = OvercookedGridworld.from_layout_name(layout, layouts_dir)
    MotionPlanner.compute_mp(f"{layout}_mp.pkl", mdp, [])
