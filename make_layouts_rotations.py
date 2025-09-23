import argparse
import json
# all imports used in this tutorial, run this if you want to jump to different sections and run only selected cells
import numpy as np
from copy import deepcopy
from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.mdp.layout_generator import Grid
from overcooked_ai_py.utils import read_layout_dict
import shutil
import os

def make_grid_string(grid):
    grid_string = """"""
    for k,line in enumerate(grid):
        for tile in line:
            grid_string += tile
        if k != grid.shape[0] -1 :
            grid_string +='\n'
            grid_string +='\t\t\t\t'
    grid_string += "\"\"\",\n"
    return grid_string
def to_layout_file(grid, layout_name, layout_dir, angle):
    filepath = os.path.join(layout_dir, layout_name)
    shutil.copyfile(filepath + '.layout', filepath+angle+'.layout')
    filepath = filepath+angle+'.layout'
    with open(filepath, "r") as f:
        layout = eval(f.read())
        f.close()
    layout = dict(layout)
    layout_grid = make_grid_string(grid)
    with open(filepath, 'w+', encoding='utf-8') as f:
        f.write("{\n")
        f.write("\t\"grid\":  \"\"\"")
        f.write(layout_grid)
        f.write("\t\"start_all_orders\": " +str(layout["start_all_orders"]) + ",\n")
        f.write("\t\"rew_shaping_params\": None,\n")
        f.write("\t\"counter_goals\":" + '[]' +",\n")
        f.write("\t\"onion_value\":" +str(layout["onion_value"]) +",\n")
        f.write("\t\"tomato_value\":" +str(layout["tomato_value"]) +",\n")
        f.write("\t\"onion_time\":" +str(layout["onion_time"]) +",\n")
        f.write("\t\"tomato_time\":" +str(layout["tomato_time"]) +",\n")       
        f.write("}")
        f.close()

def rotate_layout(layout_name, config, base_bloc):
    layout_dir = config.get("layouts_dir", 'overcooked_ai_py/data/layouts')
    base_layout_params = read_layout_dict(layout_name, layout_dir)
    grid = base_layout_params['grid']
    grid = [layout_row.strip() for layout_row in grid.split("\n")]
    grid = [[c for c in row] for row in grid]
    grid90 = np.rot90(grid,1)
    to_layout_file(grid90, layout_name, layout_dir, '90')
    grid180 = np.rot90(grid,2)
    to_layout_file(grid180, layout_name, layout_dir, '180')
    grid270 = np.rot90(grid,3)
    to_layout_file(grid270, layout_name, layout_dir, '270')
    gridT = np.transpose(grid)
    to_layout_file(gridT, layout_name, layout_dir, 'T')
   
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    parser.add_argument("--base_bloc", default=0)
    args=parser.parse_args()
    with open("./config.json", 'r') as f:
        CONFIG = json.load(f)
        f.close()
    config = CONFIG[args.config]
    base_bloc = args.base_bloc
    base_layouts = config["blocs"][str(base_bloc)]
    for layout_name in base_layouts:
        rotate_layout(layout_name, config, base_bloc)
    print(CONFIG[args.config]['blocs'])








    





