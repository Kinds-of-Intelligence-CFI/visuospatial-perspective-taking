"""
Director Task Generator

Main script to generate director task datasets for visual perspective-taking experiments.
"""

import argparse
import os
from director_task.item import Item
from director_task.sample import Sample
from director_task.dataset import save_dataset


def get_argparser():
    parser = argparse.ArgumentParser(description="Generate a director task.")
    parser.add_argument("--grid_width", type=int, default=4, help="The width of the grid.")
    parser.add_argument("--grid_height", type=int, default=4, help="The height of the grid.")
    parser.add_argument("--dataset_name", type=str, required=True, help="Name of the dataset to save - must be unique.")
    parser.add_argument("--dataset_size", type=int, default=1000, help="The number of samples that should be in the dataset.")
    parser.add_argument("--control_portion", type=float, default=0.5, help="The portion of the dataset that should be control samples.")
    parser.add_argument("--items_file", type=str, default="director_task/items.json", help="Path to the items JSON file.")
    parser.add_argument("--size_prop", type=float, default=0.25, help="Proportion of questions that use size constraints (0.0-1.0).")
    parser.add_argument("--spatial_same_prop", type=float, default=0.25, help="Proportion of questions that use spatial constraints from same perspective (0.0-1.0).")
    parser.add_argument("--spatial_diff_prop", type=float, default=0.25, help="Proportion of questions that use spatial constraints from different perspective (0.0-1.0).")
    parser.add_argument("--physics_prop", type=float, default=0.5, help="Proportion of questions that use physics-related constraints (0.0-1.0).")
    parser.add_argument("--test_related_item_prop", type=float, default=0.3, help="Proportion of non-target items that should match filter criteria when generating test questions (0.0-1.0).")
    parser.add_argument("--control_related_item_prop", type=float, default=0.3, help="Proportion of non-target items that should match filter criteria when generating control questions (0.0-1.0).")
    parser.add_argument("--related_blocked_prop", type=float, default=0.5, help="Proportion of related items that should be blocked in the grid (0.0-1.0). (only for test samples).")
    parser.add_argument("--relational", action="store_true", help="Generate relational questions only (ignores all constraint proportions).")
    parser.add_argument("--variable_fill_ratio", action="store_true", help="Changes the generation code to vary the number of filler items in the grid. Only to be used when generating nothing but control samples.")
    parser.add_argument("--item_fill_prop", type=float, default=0.5, help="the proportion of the grid to fill with items.")
    return parser

def generate_variable_fill_ratio(num_samples, grid_width, grid_height, items):
    step_size = 1 /num_samples
    samples = []
    for i in range(num_samples):
        # Calculate the fill ratio for this sample
        fill_ratio = step_size * (i + 1)
        # Generate a sample with the variable fill ratio
        sample = Sample.generate_control_samples(
            items=items,
            grid_width=grid_width,
            grid_height=grid_height,
            num_samples=1,  # Generate one sample at a time
            item_fill_ratio=fill_ratio,
        )
        samples.extend(sample)

    return samples


def main():
    parser = get_argparser()
    args = parser.parse_args()
    
    # Validate that size, spatial_same, and spatial_diff proportions don't exceed 1.0
    if not args.relational:
        total_prop = args.size_prop + args.spatial_same_prop + args.spatial_diff_prop
        if total_prop > 1.0:
            print(f"Error: Size, spatial_same, and spatial_diff proportions cannot exceed 1.0. "
                  f"Got: {args.size_prop} + {args.spatial_same_prop} + {args.spatial_diff_prop} = {total_prop}")
            return 1

    # Check that the dataset name is unique
    dataset_dir = os.path.join("datasets", args.dataset_name)
    if os.path.exists(dataset_dir):
        print(f"Error: Dataset '{args.dataset_name}' already exists at {dataset_dir}")
        return 1
    
    # Load items from JSON file
    print(f"Loading items from {args.items_file}...")
    items = Item.load_from_json(args.items_file)
    print(f"Loaded {len(items)} items.")
    
    # Calculate sample counts
    control_num_samples = int(args.dataset_size * args.control_portion)
    test_num_samples = args.dataset_size - control_num_samples

    if args.variable_fill_ratio:
        print("Warning: Variable fill ratio generation is enabled. This will change the number of filler items in the grid.")
        # This function is not implemented in the provided code, but you can implement it as needed.
        samples = generate_variable_fill_ratio(args.dataset_size, args.grid_width, args.grid_height, items=items)
        print(f"Saving dataset '{args.dataset_name}'...")
        save_dataset(
            dataset_name=args.dataset_name,
            control_samples=samples,
            test_samples=[],
        )
        return
    
    # Generate samples (relational or normal)
    if args.relational:
        # Generate relational question samples
        print(f"Generating {control_num_samples} relational control samples for dataset '{args.dataset_name}'...")
        print("Question type: Relational (spatial relationships between objects)")
        control_samples = Sample.generate_relational_control_samples(
            items=items,
            grid_width=args.grid_width,
            grid_height=args.grid_height,
            num_samples=control_num_samples,
        )
        print(f"Finished generating {len(control_samples)} relational control samples.")

        print(f"Generating {test_num_samples} relational test samples for dataset '{args.dataset_name}'...")
        test_samples = Sample.generate_relational_test_samples(
            items=items,
            grid_width=args.grid_width,
            grid_height=args.grid_height,
            num_samples=test_num_samples,
        )
        print(f"Finished generating {len(test_samples)} relational test samples.")
    else:
        # Generate normal constraint-based samples
        print(f"Generating {control_num_samples} control samples for dataset '{args.dataset_name}'...")
        print(f"Question constraints: {args.size_prop*100:.1f}% size, {args.spatial_same_prop*100:.1f}% spatial-same, "
              f"{args.spatial_diff_prop*100:.1f}% spatial-diff, {args.physics_prop*100:.1f}% physics")
        control_samples = Sample.generate_control_samples(
            items=items,
            grid_width=args.grid_width,
            grid_height=args.grid_height,
            num_samples=control_num_samples,
            size_prop=args.size_prop,
            spatial_same_prop=args.spatial_same_prop,
            spatial_diff_prop=args.spatial_diff_prop,
            physics_prop=args.physics_prop,
            related_item_prop=args.control_related_item_prop,
            item_fill_ratio=args.item_fill_prop,
        )
        print(f"Finished generating {len(control_samples)} control samples.")

        print(f"Generating {test_num_samples} test samples for dataset '{args.dataset_name}'...")
        test_samples = Sample.generate_test_samples(
            items=items,
            grid_width=args.grid_width,
            grid_height=args.grid_height,
            num_samples=test_num_samples,
            size_prop=args.size_prop,
            spatial_same_prop=args.spatial_same_prop,
            spatial_diff_prop=args.spatial_diff_prop,
            physics_prop=args.physics_prop,
            related_item_prop=args.test_related_item_prop,
            related_blocked_prop=args.related_blocked_prop,
            item_fill_ratio=args.item_fill_prop,
        )
        print(f"Finished generating {len(test_samples)} test samples.")

    # Save the dataset
    print(f"Saving dataset '{args.dataset_name}'...")
    save_dataset(
        dataset_name=args.dataset_name,
        control_samples=control_samples,
        test_samples=test_samples,
    )
    
    print(f"Successfully generated dataset '{args.dataset_name}' with {args.dataset_size} total samples.")
    return 0


if __name__ == "__main__":
    exit(main())