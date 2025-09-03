Overcooked layout generator (test_generation_layout_V2)

This repository contains a pipeline to generate 8x8 Overcooked-like layouts for cognitive experiments.

Quick start

1. Create a virtualenv and install dependencies:

   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

2. Run the basic generator:

   python scripts/run_pipeline.py --mode test --n 5 --n_empty 30 --select 5 --recipes_per_layout 6

Structure

- core/: core logic (grid, generation, scoring, planning)
- scripts/: execution scripts
- data/: generated raw layouts
- selected_layouts/: selected final layouts
- debug&test/: intermediate logs and debug artifacts
