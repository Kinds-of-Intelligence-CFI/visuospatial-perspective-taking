"""
Rotating Figure Task Generator

Main script to generate rotating figure task datasets for visual perspective-taking experiments.
Combines stimulus generation and prompt integration into a single command-line interface.
"""

import argparse
import os
from rotating_figure_task.dataset import save_dataset

SYMBOL_CONFIGS = {
    "6_9": {
        "image_file": "im_of_6.jpg",           # Base image file to load from resources
        "rotations": {
            True: "6",    # appears_as_original = True: shows as "6" 
            False: "9"    # appears_as_original = False: rotated 180° shows as "9"
        }
    },
    "u_n": {
        "image_file": "im_of_u.jpg",           # Base image file to load from resources
        "rotations": {
            True: "u",    # appears_as_original = True: shows as "n"
            False: "n"    # appears_as_original = False: rotated 180° shows as "u"
        }
    },
    "p_d": {
        "image_file": "im_of_p.jpg",           # Base image file to load from resources
        "rotations": {
            True: "p",    # appears_as_original = True: shows as "p"
            False: "d"    # appears_as_original = False: rotated 180° shows as "d"
        }
    },
    "m_w": {
        "image_file": "im_of_m.jpg",           # Base image file to load from resources
        "rotations": {
            True: "m",    # appears_as_original = True: shows as "m"
            False: "w"    # appears_as_original = False: rotated 180° shows as "w"
        }
    },
}


def get_argparser():
    parser = argparse.ArgumentParser(description="Generate a rotating figure visual perspective-taking task dataset.")
    
    # Required arguments
    parser.add_argument("--dataset_name", type=str, required=True, 
                       help="Name of the dataset to save - must be unique.")
    
    # Dataset configuration
    parser.add_argument("--dataset_size", type=int, default=100, 
                       help="The number of stimulus images to generate.")
    parser.add_argument("--stimulus_sets", type=str, default="control_1,control_2,level_1,level_2,level_3",
                       help="Comma-separated list of stimulus sets to include (control_1, control_2, control_3, level_1, level_2, level_3).")
    parser.add_argument("--trial_num", type=int, default=1000,
                       help="Trial number for organization and compatibility.")
    parser.add_argument("--output_dir", type=str, default="datasets",
                       help="Base directory to save datasets in.")
    parser.add_argument("--control_proportion", type=float, default=1/3,
                        help="The ratio of control samples to the test samples. defaults to 1/3 so generates 1/3rd as many control samples as test samples")
    
    # Stimulus generation parameters
    parser.add_argument("--use_number", action="store_true", default=False,
                       help="Use actual number images instead of blank placeholders.")
    parser.add_argument("--use_arrow", action="store_true", default=False,
                       help="Use arrow figure instead of human figures.")
    parser.add_argument("--image_size", type=int, nargs=2, default=[400, 400],
                       help="Output image size as width height (default: 400 400).")
    parser.add_argument("--figure_scale", type=float, default=1,
                       help="Scale factor for figure size.")
    parser.add_argument("--margin", type=int, default=200,
                       help="Margin around edges for number placement.")
    parser.add_argument("--fov_angle", type=int, default=60,
                       help="Field of view angle in degrees for placement zones.")
    parser.add_argument("--view_distance", type=int, default=5000,
                       help="View distance for field of view calculations.")
    
    # Placement and rotation parameters
    parser.add_argument("--placement_locations", type=str, 
                       default="left,right,front,behind,front_left,front_right",
                       help="Comma-separated list of placement zones (left, right, front, behind, front_left, etc.).")
    parser.add_argument("--rotation_min", type=int, default=0,
                       help="Minimum rotation angle for figures.")
    parser.add_argument("--rotation_max", type=int, default=360,
                       help="Maximum rotation angle for figures.")
    parser.add_argument("--jitter_range", type=int, default=20,
                       help="Jitter range for number rotation in degrees.")
    
    # Resource paths
    parser.add_argument("--resource_path", type=str, default="resources",
                       help="Path to resource directory containing background and figure images.")
    parser.add_argument("--background_image", type=str, default="background_with_colours.jpg",
                       help="Background image filename.")
    
    # Generation options
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed for reproducible generation.")
    
    return parser


def validate_arguments(args):
    """Validate command line arguments."""
    errors = []
    
    # Check that the dataset name is unique
    dataset_dir = os.path.join(args.output_dir, args.dataset_name)
    if os.path.exists(dataset_dir):
        errors.append(f"Dataset '{args.dataset_name}' already exists at {dataset_dir}")
    
    # Validate stimulus sets
    valid_sets = {"control_1", "control_2", "control_3", "level_1", "level_2", "level_3"}
    requested_sets = set(args.stimulus_sets.split(","))
    invalid_sets = requested_sets - valid_sets
    if invalid_sets:
        errors.append(f"Invalid stimulus sets: {invalid_sets}. Valid sets are: {valid_sets}")
    
    # Validate placement locations
    valid_locations = {"left", "right", "front", "behind", "front_left", "front_right", "behind_left", "behind_right"}
    requested_locations = set(args.placement_locations.split(","))
    invalid_locations = requested_locations - valid_locations
    if invalid_locations:
        errors.append(f"Invalid placement locations: {invalid_locations}. Valid locations are: {valid_locations}")
    
    # Validate numeric ranges
    if args.dataset_size <= 0:
        errors.append("Dataset size must be positive")
    
    if args.rotation_min < 0 or args.rotation_max > 360 or args.rotation_min >= args.rotation_max:
        errors.append("Rotation range must be 0 <= min < max <= 360")
    
    if args.image_size[0] <= 0 or args.image_size[1] <= 0:
        errors.append("Image size dimensions must be positive")
    
    # Check resource paths exist
    if not os.path.exists(args.resource_path):
        errors.append(f"Resource path does not exist: {args.resource_path}")
    else:
        bg_path = os.path.join(args.resource_path, args.background_image)
        if not os.path.exists(bg_path):
            errors.append(f"Background image not found: {bg_path}")
        
        if args.use_number:
            for key, symbol_config in SYMBOL_CONFIGS.items():
                num_path = os.path.join(args.resource_path, symbol_config["image_file"])
                if not os.path.exists(num_path):
                    errors.append(f"Number image not found: {num_path}")
    
    return errors


def main():
    parser = get_argparser()
    args = parser.parse_args()
    
    # Validate arguments
    errors = validate_arguments(args)
    if errors:
        print("Error: Invalid arguments:")
        for error in errors:
            print(f"  - {error}")
        return 1
    
    # Parse stimulus sets and placement locations
    stimulus_sets = [s.strip() for s in args.stimulus_sets.split(",")]
    placement_locations = [loc.strip() for loc in args.placement_locations.split(",")]
    
    print(f"Generating dataset '{args.dataset_name}'...")
    print(f"Configuration:")
    print(f"  - Dataset size: {args.dataset_size} stimuli")
    print(f"  - Stimulus sets: {stimulus_sets}")
    print(f"  - Placement zones: {placement_locations}")
    print(f"  - Use numbers: {args.use_number}")
    print(f"  - Use arrow: {args.use_arrow}")
    print(f"  - Image size: {args.image_size[0]}x{args.image_size[1]}")
    print(f"  - Random seed: {args.seed}")
    
    try:
        # Generate and save the dataset
        save_dataset(
            dataset_name=args.dataset_name,
            dataset_size=args.dataset_size,
            stimulus_sets=stimulus_sets,
            symbol_dict=SYMBOL_CONFIGS, 
            placement_locations=placement_locations,
            trial_num=args.trial_num,
            output_dir=args.output_dir,
            use_number=args.use_number,
            use_arrow=args.use_arrow,
            image_size=tuple(args.image_size),
            figure_scale=args.figure_scale,
            margin=args.margin,
            fov_angle=args.fov_angle,
            view_distance=args.view_distance,
            rotation_min=args.rotation_min,
            rotation_max=args.rotation_max,
            jitter_range=args.jitter_range,
            resource_path=args.resource_path,
            background_image=args.background_image,
            seed=args.seed,
            control_proportion=args.control_proportion,
        )
        
        print(f"Successfully generated dataset '{args.dataset_name}' with {args.dataset_size} stimuli.")
        return 0
        
    except Exception as e:
        print(f"Error generating dataset: {e}")
        return 1


if __name__ == "__main__":
    exit(main())