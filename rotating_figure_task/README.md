# Rotating Figure Task

A visual perspective-taking experiment that tests whether models can understand spatial relationships and perspective-dependent interpretation of ambiguous stimuli. The task uses images containing figures (people or arrows) and ambiguous symbols (6/9, u/n, p/d, m/w) that can appear differently depending on viewing angle.

## Overview

This task evaluates models' ability to:
- Take the perspective of figures in images
- Understand spatial relationships (front/behind, left/right)
- Interpret ambiguous visual stimuli based on viewpoint
- Distinguish between viewer perspective and figure perspective

The experiment generates composite images with figures and numbers positioned according to field-of-view constraints, creating scenarios where the correct answer depends on understanding spatial perspective.

## Quick Start

### 1. Generate a Dataset

```bash
python -m rotating_figure_task.task_generator --dataset_name my_dataset --dataset_size 100 --use_number --use_arrow
```

This creates a dataset in `datasets/my_dataset/` containing:
- `dataset.json` - All samples with metadata, prompts, and correct answers
- `images/` - Generated stimulus images

### 2. Run Evaluation

```bash
inspect eval rotating_figure_task/task.py@rotating_figure_task --model <model_name> -T dataset_path=<path_to_json>
```


## Reproducing Paper Results

To generate the exact datasets used in the paper:

**Main dataset (without level_3):**
```bash
python -m rotating_figure_task.task_generator \
    --dataset_name paper_main \
    --dataset_size 3000 \
    --stimulus_sets control_1,control_2,level_1,level_2 \
    --trial_num 1000 \
    --control_proportion 1 \
    --use_number \
    --image_size 400 400 \
    --figure_scale 1.5 \
    --margin 200 \
    --fov_angle 60 \
    --view_distance 5000 \
    --placement_locations left,right,front,behind,front_left,front_right \
    --rotation_min 0 \
    --rotation_max 360 \
    --jitter_range 20 \
    --seed 42
```

**Extended dataset (with level_3):**
```bash
python -m rotating_figure_task.task_generator \
    --dataset_name paper_extended \
    --dataset_size 3000 \
    --stimulus_sets control_1,control_2,level_1,level_2,level_3 \
    --trial_num 1000 \
    --control_proportion 0.33 \
    --use_number \
    --image_size 400 400 \
    --figure_scale 1.5 \
    --margin 200 \
    --fov_angle 60 \
    --view_distance 5000 \
    --placement_locations left,right,front,behind,front_left,front_right \
    --rotation_min 0 \
    --rotation_max 360 \
    --jitter_range 20 \
    --seed 42
```

## Stimulus Sets

| Set | Description | Question Types |
|-----|-------------|----------------|
| `control_1` | Symbol identification from viewer's perspective (no perspective-taking required) | visual, spatial |
| `control_2` | Figure orientation relative to coloured walls | visual, spatial |
| `level_1` | Can the figure see the symbol? (visibility test) | visual, spatial |
| `level_2` | What does the symbol look like from the figure's perspective? | visual, spatial |
| `level_3` | Combines level 1 and 2 to test combined perspective taking | visual, spatial |

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--dataset_name` | (required) | Unique name for the dataset |
| `--dataset_size` | 100 | Number of stimulus images to generate (per stimulus set and visual or spatial combination) |
| `--stimulus_sets` | all | Comma-separated list of sets to include |
| `--trial_num` | 1000 | Trial number for organization |
| `--output_dir` | datasets | Directory to save datasets |
| `--control_proportion` | 0.33 | Ratio of control to test samples |
| `--use_number` | False | Use actual symbols (vs blank placeholders) |
| `--use_arrow` | False | Use arrow figures (vs human figures) |
| `--image_size` | 400 400 | Output image dimensions |
| `--figure_scale` | 1.0 | Scale factor for figure size |
| `--margin` | 200 | Margin for symbol placement |
| `--fov_angle` | 60 | Field of view angle in degrees |
| `--view_distance` | 5000 | View distance for FOV calculations |
| `--placement_locations` | all | Where symbols can be placed (left, right, front, behind, front_left, front_right) |
| `--rotation_min` | 0 | Minimum figure rotation |
| `--rotation_max` | 360 | Maximum figure rotation |
| `--jitter_range` | 20 | Random jitter for symbol rotation |
| `--seed` | 42 | Random seed for reproducibility |

## Analysing Results

After running the evaluation, convert the Inspect log to CSV, then run the
analysis scripts (from the repo root):

Warning: step 1 overwrites `results/combined_vpt_task_logs.csv`, which as shipped
contains the raw results from the paper. Back it up first (or restore it later
with `git checkout`) if you want to keep the original.

```bash
# 1. Export eval logs to results/combined_vpt_task_logs.csv
python -m rotating_figure_task.log_to_csv \
    --log_path <path_to_eval_logs> \
    --output_file rotating_figure_task/results/combined_vpt_task_logs.csv

# 2. Main analysis: accuracy by rotation (paper Fig. 2), plots,
#    and regenerates results/vpt_task_processed.csv used by the R models
python rotating_figure_task/analyse_results.py

# 3. Diagnostic-symbol follow-up (paper Fig. 3)
python rotating_figure_task/analyse_follow_up.py

# 4. Mixed-effects logistic regression models and LaTeX tables (paper Table 1)
#    (run from inside the results directory - the script uses relative paths)
cd rotating_figure_task/results && Rscript vpt_task.R
```

`results/` tracks only the raw input data (`combined_vpt_task_logs.csv`,
`vpt_follow_up.csv`) and the R analysis script; derived files
(`vpt_task_processed.csv`, `.tex` tables) are regenerated by the steps above.
The stimuli for the follow-up evaluations are available in the OSF storage in the zip file `follow_up_MWE3.zip`, locked with the password `follow_up`.

Two caveats when reproducing:

- Sections 2-4 of `vpt_task.R` (human, combined, and reaction-time models)
  require the human participant data, which is not distributed with this
  repository. Only the AI-model sections can be run on the shipped data.
- `vpt_follow_up.csv` comes from a follow-up experiment using a
  `level_2_rotations` stimulus set (diagnostic symbols m/w/e/3) that the
  shipped generator does not produce; its raw results are included here and
  the stimuli are in the OSF zip mentioned above, but they cannot be
  regenerated from this repository.

## File Structure

```
rotating_figure_task/
    task_generator.py       # Main CLI for dataset generation
    task.py                 # Inspect AI task definition
    dataset.py              # Dataset models and saving logic
    stimulus_generator.py   # Image generation logic
    log_to_csv.py           # Convert Inspect eval logs to CSV
    analyse_results.py      # Main results analysis (plots + processed CSV)
    analyse_follow_up.py    # Diagnostic-symbol follow-up analysis
    create_human_dataset.py # Create balanced human evaluation sets
    prompts_clean.csv       # Prompt/stimulus-set definitions loaded by dataset.py
    results/vpt_task.R       # Mixed-effects models and LaTeX tables
```

