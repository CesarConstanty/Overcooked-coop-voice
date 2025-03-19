import tqdm
import os
print (os.getcwd())
os.chdir('Overcooked-coop-voice')
# from overcooked_ai_py.agents.benchmarking import AgentEvaluator
# from overcooked_ai_py.visualization.state_visualizer import StateVisualizer
# from overcooked_ai_py.visualization.visualization_utils import show_image_in_ipython
# from overcooked_ai_py.utils import generate_temporary_file_path
# from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
# from overcooked_ai_py.visualization.pygame_utils import vstack_surfaces
# import pygame
# import numpy as np
import sys
sys.path
sys.path.insert(0, "")
from overcooked_ai_py.agents.benchmarking import AgentEvaluator, LayoutGenerator
from overcooked_ai_py.agents.agent import Agent, AgentPair, StayAgent, GreedyAgent
from overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai_py.planning.planners import MediumLevelActionManager, COUNTERS_MLG_PARAMS, MotionPlanner
mdp = OvercookedGridworld.from_layout_name("marin_II_constrained/marinII4") #avant
#mdp = OvercookedGridworld.from_layout_name("/marinII4") #apres
counter_params = COUNTERS_MLG_PARAMS
if mdp.counter_goals:
    counter_params["counter_goals"] = mdp.counter_goals
    counter_params["counter_drop"] = mdp.counter_goals
    counter_params["counter_pickup"] = mdp.counter_goals
#print(mdp.to_dict())
env_params = {"horizon": 300000}
agent_eval = AgentEvaluator.from_mdp(mdp, env_params, mlam_params=counter_params)
greedyagent1 = GreedyAgent()
greedyagent1.set_mdp(mdp)
greedyagent2 = GreedyAgent()
greedyagent2.set_mdp(mdp)
agent_pair = AgentPair(greedyagent1, greedyagent2)
a = agent_eval.evaluate_agent_pair(agent_pair, num_games=1, native_eval=True)
a.keys() # dict_keys(['env_params', 'ep_lengths', 'ep_states', 'ep_infos', 'ep_returns', 'ep_actions', 'ep_rewards', 'ep_dones', 'metadatas', 'mdp_params'])
