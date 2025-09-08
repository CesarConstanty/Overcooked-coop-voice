# AI Coding Agent Instructions - Overcooked Research Platform

## 🎯 Project Overview

This is a Flask-based cognitive science research platform for studying human-AI cooperation in the Overcooked game environment. The codebase has three main operational modes:

1. **Web-based experiments** - Flask app serving interactive sessions for research participants
2. **Layout generation pipelines** - Automated tools for creating game maps at different grid sizes  
3. **AI agent simulation** - Backend systems for agent behavior and evaluation

## 🏗️ Core Architecture

### Central Components

- **`app.py`** - Flask SocketIO server handling web experiments, user sessions, and real-time game coordination
- **`game.py`** - Game state management classes (`OvercookedGame`, `OvercookedTutorial`, `PlanningGame`)
- **`overcooked_ai_py/mdp/overcooked_mdp.py`** - Core MDP implementation (`OvercookedGridworld`) defining game physics and rules
- **`overcooked_ai_py/mdp/overcooked_env.py`** - Environment wrapper for agent-environment interaction

### Key Data Flows

```
Web UI ← SocketIO → app.py ← Game Classes → OvercookedGridworld ← Layout Files
                                        ↕
                                  Agent Systems
```

## 🎮 Layout System Architecture

Layouts define game maps and are stored in `overcooked_ai_py/data/layouts/`. Each layout file (`.layout`) contains:

```python
{
    "grid": """XXXXXXX
               X  1  T
               X YX  X
               XX Y 2S
               XXXXDXX""",
    "start_all_orders": [{"ingredients": ["onion"]}, ...],
    "onion_value": 3, "tomato_value": 2,
    "onion_time": 9, "tomato_time": 6
}
```

**Grid symbols**: `X`=wall, `1`/`2`=players, `O`=onion dispenser, `T`=tomato, `P`=pot, `D`=dish, `S`=serving, `Y`=counter goals

### Layout Generation Pipelines

Two parallel generation systems exist:

- **`test_generation_layout/`** - Original 7x7 grid generator
- **`test_generation_layout_8x8/`** - Adapted 8x8 grid generator with optimized multiprocessing

**5-step pipeline**: recipes → raw layouts → formatting → object placement → evaluation

## 🔧 Development Workflows

### Running Experiments
```bash
export FLASK_ENV=development
python app.py
# Access: http://localhost:5000/?PROLIFIC_PID=1&CONFIG=test
```

### Layout Generation (8x8)
```bash
cd test_generation_layout_8x8
python3 scripts/run_pipeline.py        # Full pipeline
python3 scripts/run_pipeline.py 2      # Step 2 only
```

### Agent Precomputation
For layouts using MLAM/Motion planners:
```bash
python compute_mlam.py <config_key>
```

## 🤖 Agent Integration Points

### Agent Types
- **`GreedyAgent`** - Optimized task completion (primary for evaluation)
- **`LazyAgent`**, **`RandomAgent`** - Testing variants
- **Rule-based agents** - Custom implementations for cognitive studies

### Key Classes
- **`AgentGroup`** - Multi-agent coordination wrapper
- **`MediumLevelActionManager`** - High-level action planning
- **`MotionPlanner`** - Low-level pathfinding with precomputed pickle files

## 📋 Configuration System

### Main Config (`config.json`)
Defines experimental conditions:
```python
"overcooked_SOAVersionUE": {
    "agent_name": "GreedyAgent",
    "layouts": ["trial5_0", "trial5_1"],
    "questionnaire_config": {...}
}
```

### Layout-Specific Configs
- **Recipe configs** - Define ingredient combinations and cooking parameters
- **MDP parameters** - Game physics (cooking times, reward shaping)

## 🚨 Critical Constraints & Patterns

### Layout Generation Rules
1. **Grid borders must be walls** - No free spaces on edges
2. **Connectivity requirement** - All free cells must be reachable
3. **No 2x2 wall blocks** - Prevents dead zones
4. **Player positioning** - Players can't start on borders
5. **Distance optimization** - Objects placed for optimal pathfinding

### Multiprocessing Patterns
```python
# For resource-constrained machines
num_processes = min(mp.cpu_count() - 1, task_count, 4)  # Leave 1 core free, max 4
```

### State Management
- **Thread-safe collections** (`ThreadSafeDict`, `ThreadSafeSet`) for concurrent web sessions
- **Session persistence** via Flask-Session filesystem storage
- **Game cleanup** critical for preventing memory leaks

## 🔍 Debugging & Validation

### Layout Validation
```python
# Check grid consistency
OvercookedGridworld._assert_valid_grid(layout_grid)
# Verify reachability  
mdp = OvercookedGridworld.from_layout_name(layout_name, layouts_dir)
```

### Common Issues
- **Path resolution** - Use absolute paths for cross-directory imports
- **Pickle dependencies** - Precompute MLAM files before running complex agents
- **Memory management** - Ensure proper game cleanup in multiplayer sessions

## 🎯 When Working on This Codebase

1. **Layout modifications** → Test with `OvercookedGridworld.from_layout_name()` validation
2. **Agent changes** → Verify against `GreedyAgent` baseline performance
3. **Pipeline updates** → Maintain 5-step generation sequence integrity
4. **Web features** → Test with both tutorial and experiment modes
5. **Performance optimization** → Profile multiprocessing bottlenecks in layout generation

This architecture balances research flexibility with computational constraints, emphasizing reliable multi-agent simulation and human-subject experimental control.
