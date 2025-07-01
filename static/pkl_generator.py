from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.planning.planners import MotionPlanner

layouts = [
    "trial5_0", "trial5_1", "trial5_2",
    "trial6_0", "trial6_1", "trial6_2"
]
layouts_dir = "overcooked_ai_py/data/layouts/overcooked2804"

for layout in layouts:
    print(f"Processing {layout}")
    mdp = OvercookedGridworld.from_layout_name(layout, layouts_dir)
    MotionPlanner.compute_mp(f"{layout}_mp.pkl", mdp, [])