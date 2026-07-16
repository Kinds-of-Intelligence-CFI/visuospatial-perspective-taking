# Visuospatial Perspective-Taking

A research repository containing experimental tasks for evaluating AI models' visual perspective-taking and spatial reasoning abilities. This repository implements two main experimental paradigms designed to test how well models understand different viewpoints and spatial relationships.

## Overview

This repository contains implementations of two visual perspective-taking tasks:

1. **Director Task** (`director_task/`): A grid-based task where a director gives instructions to a participant who must consider the director's limited perspective to select the correct item
2. **Rotating Figure Task** (`rotating_figure_task/`): A visual task using ambiguous rotatable symbols (6/9, u/n, p/d, m/w) that tests perspective-dependent interpretation

Both tasks are designed for evaluation using the [Inspect AI](https://inspect.aisi.org.uk/) framework and generate datasets with accompanying visual stimuli.

## Quick Start

### Setup

```bash
# Clone the repository
git clone https://github.com/Kinds-of-Intelligence-CFI/visuospatial-perspective-taking.git
cd visuospatial-perspective-taking

# Create virtual environment and install dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

### Basic Usage

#### Director Task
```bash
# Generate a dataset
python -m director_task.task_generator --dataset_name my_dataset --dataset_size 100

# Run evaluation
inspect eval director_task/task.py@directors_task --model <model_name> -T dataset_path=datasets/my_dataset/my_dataset.json
```

#### Rotating Figure Task
```bash
# Generate a dataset
python -m rotating_figure_task.task_generator --dataset_name my_dataset --dataset_size 100 --use_number --use_arrow

# Run evaluation
inspect eval rotating_figure_task/task.py@rotating_figure_task --model <model_name> -T dataset_path=datasets/my_dataset/my_dataset.json
```

## Task Details

### Director Task
The director task tests whether models can take the perspective of a "director" who has a limited view of a grid containing various objects. The participant must select items based on the director's instructions, considering what the director can and cannot see.

**Key Features:**
- Grid-based spatial reasoning
- Blocked cell mechanics (director's limited view)
- Control vs. test samples (ambiguous vs. unambiguous)
- Physics-based and spatial constraints
- Configurable item properties and generation parameters

See [director_task/README.md](director_task/README.md) for detailed documentation.

### Rotating Figure Task
This task presents visual stimuli where symbols can appear differently depending on viewing perspective (e.g., "6" vs "9", "u" vs "n"). Models must determine what a figure in the image would see based on their spatial position and orientation.

**Key Features:**
- Ambiguous visual stimuli (rotatable symbols: 6/9, u/n, p/d, m/w)
- Figure positioning and rotation
- Spatial relationship questions (front/behind, left/right)
- Field-of-view constraints using cone geometry
- Visual vs. spatial perspective conditions

## Project Structure

```
visuospatial-perspective-taking/
├── director_task/          # Grid-based perspective-taking task
│   └── results/            # Raw eval logs and R analysis for the paper
├── rotating_figure_task/   # Ambiguous symbol perspective task
│   └── results/            # Raw eval logs and R analysis for the paper
├── resources/              # Shared assets (images, figures)
├── datasets/               # Generated datasets with images (created at runtime)
├── logs/                   # Evaluation results and logs (created at runtime)
├── cogsci_appendix.pdf     # Supplementary appendix for the paper
└── setup.py                # Package configuration
```

## Dependencies

- **inspect_ai**: Framework for AI evaluation tasks
- **pillow**: Image processing and generation
- **pydantic**: Data validation and serialization
- **jsonschema**: JSON validation for datasets
- **pandas/seaborn**: Data analysis and visualization (rotating_figure_task)

The statistical analyses additionally require R with the following packages:
`tidyverse`, `lme4`, `glmmTMB`, `car`, `emmeans`, `kableExtra`, `gridExtra`.

## Evaluation

Both tasks integrate with the Inspect AI framework for systematic model evaluation:

- Support for multiple model providers
- Structured evaluation metrics and logging
- Batch processing capabilities
- Statistical analysis tools

## Development

The repository includes comprehensive test suites and validation tools:

```bash
# Run tests
python -m unittest discover -s director_task -p "test_*.py"

# Interactive item editing (director task)
python -m director_task.item_editor
```

## Citation

## Citation

If you use this work, please cite:

```bibtex
@inproceedings{prunty2026visuospatial,
  title     = {Visuospatial Perspective Taking in Multimodal Language Models},
  author    = {Prunty, Jonathan and Zhang, Seraphina and Quinn, Patrick and Lian, Jianxun and Xie, Xing and Cheke, Lucy},
  booktitle = {Proceedings of the Annual Meeting of the Cognitive Science Society},
  year      = {2026},
  publisher = {Cognitive Science Society},
  note      = {To appear}
}
```

## Datasets 

A copy of the stimuli used in our experiments is available at https://osf.io/bpr5j/overview?view_only=d583d77e39394af08f07ae69881bb938 with each file being password protected.
The password for the directors task dataset is `director_task` and the one for the rotating figure task is `vspt_task`.
