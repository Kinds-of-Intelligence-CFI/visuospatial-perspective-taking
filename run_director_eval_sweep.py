#!/usr/bin/env python3
"""
Director Task Evaluation Sweep Script

This script automates the evaluation of director task datasets across different
related_prop and fill_prop combinations using the Inspect AI Python API.

For each dataset, it runs two evaluations:
1. Default mode: Standard image rendering with block_description_index=0
2. ASCII mode: ASCII image rendering with block_description_index=1

Results are organized in a structured logging directory similar to logs/initial_sweep.
"""

import os
import re
import glob
from datetime import datetime
from typing import List, Tuple, Dict, Optional, Any
import traceback

from inspect_ai import eval
from director_task.task import directors_task
from director_task.control_task import control_task


def discover_datasets(
    datasets_dir: str = "datasets", 
    fill_ratios: Optional[List[float]] = None,
    related_ratios: Optional[List[float]] = None
) -> List[Dict[str, Any]]:
    """
    Discover all director task datasets with related_prop and fill_prop variations.
    
    Args:
        datasets_dir: Base directory containing datasets
        fill_ratios: Optional list of fill ratios to include (if None, includes all)
        related_ratios: Optional list of related ratios to include (if None, includes all)
        
    Returns:
        List of dataset info dictionaries containing name, related_prop, fill_prop, and path
    """
    datasets = []
    dataset_pattern = os.path.join(datasets_dir, "director_task_large_related_prop_*")
    
    for dataset_path in glob.glob(dataset_pattern):
        if os.path.isdir(dataset_path):
            dataset_name = os.path.basename(dataset_path)
            
            # Extract related_prop and fill_prop from dataset name
            # Pattern: director_task_large_related_prop_X.X_fill_prop_Y.Y
            # or: director_task_large_related_prop_X.X
            match = re.match(r'director_task_large_related_prop_([0-9.]+)(?:_fill_prop_([0-9.]+))?', dataset_name)
            
            if match:
                related_prop = float(match.group(1))
                fill_prop = float(match.group(2)) if match.group(2) else None
                
                # Filter by specified ratios
                if related_ratios is not None and related_prop not in related_ratios:
                    continue
                if fill_ratios is not None and fill_prop not in fill_ratios:
                    continue
                
                # Check if dataset JSON file exists
                json_path = os.path.join(dataset_path, f"{dataset_name}.json")
                if os.path.exists(json_path):
                    datasets.append({
                        'name': dataset_name,
                        'related_prop': related_prop,
                        'fill_prop': fill_prop,
                        'path': json_path,
                        'dir': dataset_path
                    })
                else:
                    print(f"Warning: Dataset JSON not found for {dataset_name}")
    
    # Sort datasets by fill_prop first (None values last), then by related_prop
    datasets.sort(key=lambda x: (x['fill_prop'] if x['fill_prop'] is not None else 999, x['related_prop']))
    
    return datasets


def create_log_directory(base_log_dir: str, related_prop: float, fill_prop: Optional[float], mode: str) -> str:
    """
    Create organized log directory structure.
    
    Args:
        base_log_dir: Base logging directory for this sweep
        related_prop: Related proportion value
        fill_prop: Fill proportion value (None for datasets without fill_prop)
        mode: Evaluation mode ('default' or 'ascii')
        
    Returns:
        Path to the specific log directory
    """
    if fill_prop is not None:
        log_path = os.path.join(
            base_log_dir,
            f"fill_ratio_{fill_prop}",
            f"related_ratio_{related_prop}",
            mode
        )
    else:
        # For datasets without fill_prop, use a special directory
        log_path = os.path.join(
            base_log_dir,
            "no_fill_ratio",
            f"related_ratio_{related_prop}",
            mode
        )
    
    os.makedirs(log_path, exist_ok=True)
    return log_path


def run_single_evaluation(dataset: Dict[str, Any], mode: str, model: str, log_dir: str) -> Tuple[bool, str]:
    """
    Run a single evaluation for a dataset in the specified mode.
    
    Args:
        dataset: Dataset information dictionary
        mode: Evaluation mode ('default' or 'ascii')
        model: Model name to use for evaluation
        log_dir: Directory to save evaluation logs
        
    Returns:
        Tuple of (success: bool, error_message: str or empty if success)
    """
    try:
        # Configure evaluation parameters based on mode
        
        block_description_index = 2
        use_ascii_image = mode == "ascii"
        # Run the evaluation using Inspect AI Python API
        print(f"    Running {mode} evaluation...")
        eval(
            tasks=directors_task(
                dataset_path=dataset['path'],
                use_ascii_image=use_ascii_image,
                block_description_index=block_description_index
            ),
            model=model,
            log_dir=log_dir,
            retry_on_error=3,
            max_connections=2,
        )
        
        print(f"    ✓ {mode.capitalize()} evaluation completed successfully")
        return True, ""
        
    except Exception as e:
        error_msg = f"Error in {mode} evaluation: {str(e)}"
        print(f"    ✗ {error_msg}")
        # Print traceback for debugging
        traceback.print_exc()
        return False, error_msg


def run_control_task_evaluation(model: str, datasets_dir: str, log_dir: str) -> Tuple[bool, str]:
    """
    Run the control task evaluation on the specific dataset (fill_prop=0.9, related_prop=0.7).
    
    Args:
        model: Model name to use for evaluation
        datasets_dir: Directory containing datasets
        log_dir: Directory to save evaluation logs
        
    Returns:
        Tuple of (success: bool, error_message: str or empty if success)
    """
    try:
        # Find the specific control dataset
        control_dataset_name = "director_task_large_related_prop_0.7_fill_prop_0.9"
        control_dataset_path = os.path.join(datasets_dir, control_dataset_name, f"{control_dataset_name}.json")
        
        # Check if the dataset exists
        if not os.path.exists(control_dataset_path):
            raise FileNotFoundError(f"Control dataset not found at: {control_dataset_path}")
        
        print("    Running control task evaluation...")
        eval(
            tasks=control_task(
                dataset_path=control_dataset_path,
                use_ascii_image=True,  # Control task defaults to ASCII
                block_description_index=2
            ),
            model=model,
            log_dir=log_dir,
            retry_on_error=3,
            max_connections=2,
        )
        
        print("    ✓ Control task evaluation completed successfully")
        return True, ""
        
    except Exception as e:
        error_msg = f"Error in control task evaluation: {str(e)}"
        print(f"    ✗ {error_msg}")
        traceback.print_exc()
        return False, error_msg


def run_evaluation_sweep(
    model: str = "gpt-4",
    datasets_dir: str = "datasets",
    logs_base_dir: str = "logs",
    modes: List[str] = ["default", "ascii"],
    include_control_task: bool = True,
    fill_ratios: Optional[List[float]] = None,
    related_ratios: Optional[List[float]] = None
) -> None:
    """
    Run the complete evaluation sweep across all discovered datasets.
    
    Args:
        model: Model name to use for evaluations
        datasets_dir: Directory containing datasets
        logs_base_dir: Base directory for logs
        modes: List of evaluation modes to run
        include_control_task: Whether to run the control task evaluation
        fill_ratios: Optional list of fill ratios to include (if None, includes all)
        related_ratios: Optional list of related ratios to include (if None, includes all)
    """
    # Create timestamped log directory with model name
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    # Clean model name for filesystem (replace slashes and special chars)
    clean_model_name = model.replace("/", "_").replace(":", "_").replace(" ", "_")
    sweep_log_dir = os.path.join(logs_base_dir, f"sweep_{timestamp}_{clean_model_name}")
    os.makedirs(sweep_log_dir, exist_ok=True)
    
    print("Director Task Evaluation Sweep")
    print("=" * 50)
    print(f"Model: {model}")
    print(f"Log directory: {sweep_log_dir}")
    print(f"Evaluation modes: {', '.join(modes)}")
    print()
    
    # Discover datasets
    datasets = discover_datasets(datasets_dir, fill_ratios, related_ratios)
    print(f"Discovered {len(datasets)} datasets:")
    for dataset in datasets:
        fill_info = f"fill_prop={dataset['fill_prop']}" if dataset['fill_prop'] is not None else "no fill_prop"
        print(f"  - {dataset['name']} (related_prop={dataset['related_prop']}, {fill_info})")
    print()
    
    # Track results
    total_evaluations = len(datasets) * len(modes)
    completed_evaluations = 0
    failed_evaluations = []
    
    # Run evaluations for each dataset
    for i, dataset in enumerate(datasets, 1):
        print(f"[{i}/{len(datasets)}] Processing dataset: {dataset['name']}")
        
        for mode in modes:
            print(f"  Mode: {mode}")
            
            # Create log directory for this evaluation
            log_dir = create_log_directory(
                sweep_log_dir, 
                dataset['related_prop'], 
                dataset['fill_prop'], 
                mode
            )
            
            # Run the evaluation
            success, error_msg = run_single_evaluation(dataset, mode, model, log_dir)
            
            if success:
                completed_evaluations += 1
            else:
                failed_evaluations.append({
                    'dataset': dataset['name'],
                    'mode': mode,
                    'error': error_msg
                })
            
            print(f"    Progress: {completed_evaluations}/{total_evaluations} evaluations completed")
        
        print()  # Empty line between datasets
    
    # Run control task evaluation if requested
    if include_control_task:
        print("Running Control Task Evaluation")
        print("-" * 30)
        control_log_dir = os.path.join(sweep_log_dir, "control_task")
        os.makedirs(control_log_dir, exist_ok=True)
        
        control_success, control_error = run_control_task_evaluation(model, datasets_dir, control_log_dir)
        if control_success:
            completed_evaluations += 1
            total_evaluations += 1
            print("✓ Control task completed successfully")
        else:
            failed_evaluations.append({
                'dataset': 'control_task (fill_prop=0.9, related_prop=0.7)',
                'mode': 'ascii_text_only',
                'error': control_error
            })
            total_evaluations += 1
            print("✗ Control task failed")
        print()
    
    # Print summary
    print("=" * 50)
    print("EVALUATION SWEEP SUMMARY")
    print("=" * 50)
    print(f"Total evaluations: {total_evaluations}")
    print(f"Completed successfully: {completed_evaluations}")
    print(f"Failed: {len(failed_evaluations)}")
    print(f"Success rate: {completed_evaluations/total_evaluations*100:.1f}%")
    
    if failed_evaluations:
        print("\nFailed evaluations:")
        for failure in failed_evaluations:
            print(f"  - {failure['dataset']} ({failure['mode']}): {failure['error']}")
    
    print(f"\nLogs saved to: {sweep_log_dir}")


def main():
    """Main entry point for the script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run director task evaluation sweep across datasets with varying related_prop and fill_prop"
    )
    parser.add_argument(
        "--model", 
        default="gpt-4", 
        help="Model to use for evaluations (default: gpt-4)"
    )
    parser.add_argument(
        "--datasets-dir", 
        default="datasets", 
        help="Directory containing datasets (default: datasets)"
    )
    parser.add_argument(
        "--logs-dir", 
        default="logs", 
        help="Base directory for logs (default: logs)"
    )
    parser.add_argument(
        "--modes", 
        nargs="+", 
        default=["default", "ascii"], 
        choices=["default", "ascii"],
        help="Evaluation modes to run (default: default ascii)"
    )
    parser.add_argument(
        "--skip-control-task", 
        action="store_true",
        help="Skip the control task evaluation"
    )
    parser.add_argument(
        "--fill-ratios",
        nargs="+",
        type=float,
        help="Specific fill ratios to include in sweep (e.g., --fill-ratios 0.3 0.5 0.9). If not specified, includes all available ratios"
    )
    parser.add_argument(
        "--related-ratios",
        nargs="+", 
        type=float,
        help="Specific related ratios to include in sweep (e.g., --related-ratios 0.5 0.7). If not specified, includes all available ratios"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Show what would be evaluated without running evaluations"
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("DRY RUN MODE - No evaluations will be performed")
        print()
        datasets = discover_datasets(args.datasets_dir, args.fill_ratios, args.related_ratios)
        print(f"Would evaluate {len(datasets)} datasets with modes: {', '.join(args.modes)}")
        for dataset in datasets:
            fill_info = f"fill_prop={dataset['fill_prop']}" if dataset['fill_prop'] is not None else "no fill_prop"
            print(f"  - {dataset['name']} (related_prop={dataset['related_prop']}, {fill_info})")
        total_evals = len(datasets) * len(args.modes)
        if not args.skip_control_task:
            print("  + Control task (fill_prop=0.9, related_prop=0.7) - ASCII text only")
            total_evals += 1
        print(f"Total evaluations that would be run: {total_evals}")
    else:
        run_evaluation_sweep(
            model=args.model,
            datasets_dir=args.datasets_dir,
            logs_base_dir=args.logs_dir,
            modes=args.modes,
            include_control_task=not args.skip_control_task,
            fill_ratios=args.fill_ratios,
            related_ratios=args.related_ratios
        )


if __name__ == "__main__":
    main()