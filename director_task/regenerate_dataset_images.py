"""
Script to regenerate images for an existing dataset.

This script loads a dataset JSON file and regenerates all images by:
1. Reconstructing Grid objects from the dataset
2. Using GridRenderer2D to render each grid
3. Saving the rendered images to their original paths

Usage:
    python regenerate_dataset_images.py <dataset_path>

Example:
    python regenerate_dataset_images.py datasets/my_dataset/my_dataset.json
"""

import argparse
import os
import sys
from director_task.dataset import load_dataset
from director_task.renderer_2d import GridRenderer2D
from director_task.grid import Grid
from director_task.item import Item


def regenerate_dataset_images(dataset_path: str, verbose: bool = True):
    """
    Regenerate all images for a dataset.

    Args:
        dataset_path: Path to the dataset JSON file
        verbose: Whether to print progress information
    """
    # Validate dataset path
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    # Load the dataset
    if verbose:
        print(f"Loading dataset from: {dataset_path}")
    dataset = load_dataset(dataset_path)

    # Get dataset directory for resolving relative paths
    dataset_dir = os.path.dirname(os.path.abspath(dataset_path))

    # Load items for renderer cache warmup
    items_path = "director_task/items.json"
    if verbose:
        print(f"Loading items from: {items_path}")

    try:
        items = Item.load_from_json(items_path, validate=False)
        # Create a lookup dictionary for items by name
        items_by_name = {item.name: item for item in items}
        if verbose:
            print(f"Loaded {len(items)} items")
    except FileNotFoundError:
        print(f"Warning: Could not load items from {items_path}")
        print("Continuing without item lookup (will use dataset item data)...")
        items = None
        items_by_name = {}

    # Initialize renderer with items for cache warmup
    if verbose:
        print("Initializing renderer...")
    renderer = GridRenderer2D(items=items if items else None)

    # Process each sample
    total_samples = len(dataset['samples'])
    if verbose:
        print(f"\nRegenerating {total_samples} images...\n")

    for i, sample_data in enumerate(dataset['samples'], 1):
        # Create empty grid with correct dimensions
        grid_data = sample_data['grid']
        grid = Grid(grid_data['width'], grid_data['height'])

        # Populate grid from flattened items array
        for item_data in grid_data['items']:
            x = item_data['position']['x']  # column
            y = item_data['position']['y']  # row
            is_blocked = item_data['is_blocked']

            # Set blocked status
            if is_blocked:
                grid.blocks[y][x] = 1  # Grid access: [row][col] = [y][x]

            # Create and place item if present
            if item_data['item'] is not None:
                item_info = item_data['item']
                item_name = item_info['name']

                # Try to use current item from items.json (with updated offsets)
                if item_name in items_by_name:
                    item = items_by_name[item_name]
                else:
                    # Fallback: create item from dataset data if not in items.json
                    if verbose:
                        print(f"Warning: Item '{item_name}' not found in items.json, using dataset data")
                    item = Item(
                        name=item_info['name'],
                        image_path=item_info['image_path'],
                        boolean_properties=item_info['boolean_properties'],
                        scalar_properties=item_info['scalar_properties']
                    )
                grid.item_grid[y][x] = item  # Grid access: [row][col] = [y][x]

        # Render the grid
        rendered_image = renderer.render_grid(grid)

        # Construct full image path (sample image_path is relative to dataset dir)
        image_relative_path = sample_data['image_path']
        image_full_path = os.path.join(dataset_dir, image_relative_path)

        # Ensure the directory exists (should already exist, but just in case)
        image_dir = os.path.dirname(image_full_path)
        os.makedirs(image_dir, exist_ok=True)

        # Save the rendered image
        rendered_image.save(image_full_path)

        if verbose:
            sample_id = sample_data.get('sample_id', i-1)
            sample_type = sample_data.get('sample_type', 'unknown')
            print(f"[{i}/{total_samples}] Regenerated {sample_type} sample {sample_id}: {image_relative_path}")

    if verbose:
        print(f"\nSuccessfully regenerated all {total_samples} images!")
        print(f"Dataset: {dataset['dataset_name']}")
        print(f"Location: {dataset_dir}")


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Regenerate images for an existing dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python regenerate_dataset_images.py datasets/my_dataset/my_dataset.json
  python regenerate_dataset_images.py path/to/dataset.json --quiet
        """
    )

    parser.add_argument(
        "dataset_path",
        help="Path to the dataset JSON file"
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress output"
    )

    args = parser.parse_args()

    try:
        regenerate_dataset_images(args.dataset_path, verbose=not args.quiet)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
