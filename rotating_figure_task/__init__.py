"""
Rotating Figure Task Package

Visual perspective-taking experiments using ambiguous rotatable symbols (6/9, u/n, p/d, m/w).
"""

from .task import rotating_figure_task
from .dataset import save_dataset, load_dataset, validate_dataset_file
from .task_generator import main as generate_dataset

__version__ = "1.0.0"
__all__ = [
    "rotating_figure_task",
    "save_dataset",
    "load_dataset",
    "validate_dataset_file",
    "generate_dataset"
]