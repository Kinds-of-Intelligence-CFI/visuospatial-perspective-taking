"""
Stimulus Generation Module

Extracted and modularized stimulus generation logic from generate_stimuli.py
for use in the unified dataset generation pipeline.
"""

import os
import random
import math
from typing import Any, Dict, List, Tuple
from PIL import Image
from rotating_figure_task.dataset import StimulusMetadataModel


# === Geometric Utilities ===
def point_in_triangle(px, py, p1, p2, p3):
    """Check if point (px, py) is inside triangle defined by points p1, p2, p3."""
    denom = (p2[1] - p3[1]) * (p1[0] - p3[0]) + (p3[0] - p2[0]) * (p1[1] - p3[1])
    if abs(denom) < 1e-10:
        return False
    a = ((p2[1] - p3[1]) * (px - p3[0]) + (p3[0] - p2[0]) * (py - p3[1])) / denom
    b = ((p3[1] - p1[1]) * (px - p3[0]) + (p1[0] - p3[0]) * (py - p3[1])) / denom
    c = 1 - a - b
    return all(coord >= 0 for coord in (a, b, c))


def is_in_cone(px, py, cx, cy, cone_angle, fov_angle, distance):
    """Check if point (px, py) is within the field of view cone."""
    rot = math.radians(cone_angle)
    half_fov = math.radians(fov_angle) / 2
    apex = (cx, cy)
    left = (cx + distance * math.sin(rot - half_fov), cy + distance * math.cos(rot - half_fov))
    right = (cx + distance * math.sin(rot + half_fov), cy + distance * math.cos(rot + half_fov))
    return point_in_triangle(px, py, apex, left, right)


def get_cone_angle(base_rotation, placement_zone):
    """Get the cone angle for a placement zone relative to base rotation."""
    offsets = {
        "front": 90,
        "behind": -90,
        "left": 180,
        "right": 0,
        "front_left": 125,
        "front_right": 55,
        "behind_left": -125,
        "behind_right": -55,
    }
    if placement_zone not in offsets:
        raise ValueError(f"Unknown placement zone: {placement_zone}")
    return (base_rotation + offsets[placement_zone]) % 360


def find_valid_position(bg_size, fg_box, num_size, margin, center, base_rotation, fov, dist, placement_zone):
    """Find a valid position for the number within the specified placement zone."""
    bg_w, bg_h = bg_size
    num_w, num_h = num_size
    cone_angle = get_cone_angle(base_rotation, placement_zone)
    
    for _ in range(2000):
        x = random.randint(margin, bg_w - num_w - margin)
        y = random.randint(margin, bg_h - num_h - margin)
        num_center = (x + num_w // 2, y + num_h // 2)
        num_box = (x, y, x + num_w, y + num_h)
        
        # Check for overlap with figure
        fg_left, fg_top, fg_right, fg_bottom = fg_box
        overlap = not (num_box[2] < fg_left or num_box[0] > fg_right or
                       num_box[3] < fg_top or num_box[1] > fg_bottom)
        
        if overlap:
            continue
        
        # Check if position is within the field of view cone
        if is_in_cone(*num_center, *center, cone_angle, fov, dist):
            return x, y
    
    raise RuntimeError(f"Couldn't find position in '{placement_zone}' zone after many attempts.")


def calculate_number_rotation(base_angle, as_six, location, jitter_range=10):
    """Calculate the rotation angle for the number based on figure perspective."""
    primary = location.split("_")[0]
    offsets = {
        "front": -90 if as_six else 90,
        "behind": 90 if as_six else -90,
        "left": 0 if as_six else 180,
        "right": 180 if as_six else 0,
    }
    offset = offsets.get(primary)
    if offset is None:
        raise ValueError(f"Invalid location: {location}.")
    jitter = random.uniform(-jitter_range, jitter_range)
    return (base_angle + offset + jitter) % 360


def load_image(resource_path, filename):
    """Load an image from the resource directory."""
    return Image.open(os.path.join(resource_path, filename)).convert("RGBA")


def generate_stimulus_images(
    n_images: int,
    placement_locations: List[str],
    images_dir: str,
    stimulus_set: str,
    use_number: bool,
    use_arrow: bool,
    rotate_number: bool,
    image_size: Tuple[int, int],
    figure_scale: float,
    margin: int,
    fov_angle: int,
    view_distance: int,
    rotation_min: int,
    rotation_max: int,
    jitter_range: int,
    resource_path: str,
    background_image: str,
    symbol_dict: Dict[str, Dict],
) -> List[StimulusMetadataModel]:
    """
    Generate stimulus images and return metadata.
    
    This function replicates the core logic from generate_stimuli.py but returns
    structured metadata instead of writing CSV files.
    """
    # Load assets
    background = load_image(resource_path, background_image)
    
    bg_w, bg_h = background.size
    
    # Load figure images
    if use_arrow:
        figure_files = ["arrow.png"]
        figure_path = resource_path
    else:
        figure_path = os.path.join(resource_path, "figures_arrow")
        figure_files = [f for f in os.listdir(figure_path) if f.lower().endswith((".jpg", ".png"))]
    
    if not figure_files:
        raise ValueError(f"No figure images found in {figure_path}")
    
    # Generate stimuli
    stimuli_metadata = []
    
    for i in range(n_images):

        if use_number:
            symbol_key = list(symbol_dict.keys())[i % len(symbol_dict)]
            symbol_config = symbol_dict[symbol_key]
            number = load_image(resource_path, symbol_config["image_file"])
        else:
            number = load_image(resource_path, "blank.png")

        # Randomize properties
        if use_arrow:
            figure_file = "arrow.png"
            figure = Image.open(os.path.join(resource_path, figure_file)).convert("RGBA")
        else:
            figure_file = random.choice(figure_files)
            figure = Image.open(os.path.join(figure_path, figure_file)).convert("RGBA")
        
        # Rotate figure to face upward initially
        figure = figure.transpose(Image.ROTATE_90)
        figure_angle = random.uniform(rotation_min, rotation_max)
        appears_unrotated = random.choice([True, False])
        placement_zone = random.choice(placement_locations)
        
        # Prepare geometry
        fg_w, fg_h = figure.size
        figure = figure.resize((int(fg_w * figure_scale), int(fg_h * figure_scale)), resample=Image.LANCZOS)
        fg_w, fg_h = figure.size  # Update dimensions after scaling
        fg_x, fg_y = (bg_w - fg_w) // 2, (bg_h - fg_h) // 2
        figure_box = (fg_x, fg_y, fg_x + fg_w, fg_y + fg_h)
        figure_center = (fg_x + fg_w // 2, fg_y + fg_h // 2)
        
        # Calculate number rotation
        if rotate_number:
            number_appearance_type = "figure_perspective"
            number_angle = calculate_number_rotation(figure_angle, appears_unrotated, placement_zone, jitter_range)
        else:
            number_appearance_type = "viewer_perspective"
            number_angle = calculate_number_rotation(0, appears_unrotated, "left", jitter_range)
        
        # Find valid position for number
        num_position = find_valid_position(
            (bg_w, bg_h), figure_box, number.size, margin,
            figure_center, figure_angle, fov_angle, view_distance,
            placement_zone
        )
        
        # Compose image
        figure_rotated = figure.rotate(figure_angle, expand=True)
        number_rotated = number.rotate(number_angle, expand=True)
        
        # Center the rotated figure
        fg_x = (bg_w - figure_rotated.size[0]) // 2
        fg_y = (bg_h - figure_rotated.size[1]) // 2
        
        composed = background.copy()
        composed.paste(figure_rotated, (fg_x, fg_y), figure_rotated)
        composed.paste(number_rotated, num_position, number_rotated)

        alternative_number = ""

        # for level 3 we need to place the flipped number in the opposite location
        if stimulus_set == "level_3":
            opposite_location = "front_left" if placement_zone == "front_right" else "front_right"
            valid_keys = list(symbol_dict.keys())
            valid_keys.remove(symbol_key)
            alternate_symbol_config = symbol_dict[random.choice(valid_keys)]
            alternative_number = load_image(resource_path, alternate_symbol_config["image_file"])
            alternate_num_position = find_valid_position(
                (bg_w, bg_h), figure_box, alternative_number.size, margin,
                figure_center, figure_angle, fov_angle, view_distance,
                opposite_location
            )
            flipped_number = alternative_number.rotate(number_angle + 180 % 360, expand=True)
            composed.paste(flipped_number, alternate_num_position, flipped_number)
            alternative_number = alternate_symbol_config["rotations"][appears_unrotated]
        
        # Save image
        appearance = symbol_config["rotations"][appears_unrotated] if use_number else "none"
        filename = f"{stimulus_set}_image_{i:03d}_{placement_zone}.jpg"
        output_path = os.path.join(images_dir, filename)
        
        # Resize to target dimensions
        resized = composed.resize(image_size, resample=Image.LANCZOS)
        resized.convert("RGB").save(output_path)
        
        # Calculate scaled coordinates
        scale_x = image_size[0] / bg_w
        scale_y = image_size[1] / bg_h
        scaled_num_x = round(num_position[0] * scale_x)
        scaled_num_y = round(num_position[1] * scale_y)
        
        # Calculate number location relative to image center
        resized_center_x = image_size[0] // 2
        resized_center_y = image_size[1] // 2
        resized_num_center_x = scaled_num_x + int(number.size[0] * scale_x / 2)
        resized_num_center_y = scaled_num_y + int(number.size[1] * scale_y / 2)
        
        number_location_x = "left" if resized_num_center_x < resized_center_x else "right"
        number_location_y = "top" if resized_num_center_y < resized_center_y else "bottom"
        
        # Extract figure type from filename
        figure_type = figure_file.split(".")[0]
        
        # Create metadata
        stimulus_meta = StimulusMetadataModel(
            filename=filename,
            image_number=i,
            figure_type=figure_type,
            margin_size=margin,
            fov_angle=fov_angle,
            figure_rotation=round(figure_angle, 2),
            number_rotation=round(number_angle, 2),
            number_position_x=scaled_num_x,
            number_position_y=scaled_num_y,
            number_location_x=number_location_x,
            number_location_y=number_location_y,
            relative_location=placement_zone,
            number_appearance_type=number_appearance_type,
            number_appearance=appearance,
            alternate_number=alternative_number,
        )
        
        stimuli_metadata.append(stimulus_meta)
    
    return stimuli_metadata