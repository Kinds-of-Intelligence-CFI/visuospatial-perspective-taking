"""
Create a balanced human dataset by sampling from one or more AI task datasets.

Accepts multiple --datasets paths. Each dataset is auto-assigned to the stimulus
sets it contributes:
  - If a dataset contains level_3 samples → only level_3 samples are used from it.
  - Otherwise → level_1 and level_2 samples are used.

Output CSV matches the online-experiment format (RFT_JP) with block structure,
response options, and trial prompts.
"""

import argparse
import csv
import itertools
import json
import os
import random
import shutil

SYMBOL_CONFIGS = {
    "6_9": {"image_file": "im_of_6.jpg", "rotations": {True: "6", False: "9"}},
    "u_n": {"image_file": "im_of_u.jpg", "rotations": {True: "u", False: "n"}},
    "p_d": {"image_file": "im_of_p.jpg", "rotations": {True: "p", False: "d"}},
    "m_w": {"image_file": "im_of_m.jpg", "rotations": {True: "m", False: "w"}},
}


# Master symbol order for option presentation (prevents response-position bias)
MASTER_ORDER = ['6', '9', 'p', 'd', 'n', 'u', 'm', 'w']

# Maps each symbol to its pair's two symbols (in master order)
PAIR_SYMBOLS = {
    '6': ['6', '9'], '9': ['6', '9'],
    'p': ['p', 'd'], 'd': ['p', 'd'],
    'n': ['n', 'u'], 'u': ['n', 'u'],
    'm': ['m', 'w'], 'w': ['m', 'w'],
}

# Which (stimulus_set, question_type) combinations each block contains
BLOCK_SS_QT = {
    '1V':  [('level_1', 'visual')],
    '1S':  [('level_1', 'spatial')],
    '2V':  [('level_2', 'visual')],
    '2S':  [('level_2', 'spatial')],
    '3VS': [('level_3', 'visual')],
}

BLOCK_ORDER = ['1V', '1S', '2V', '2S', '3VS']

BLOCK_PROMPTS = {
    '1V': {
        'correct_answer': 'CAN SEE',
        'question_prompt': 'Can the person see the number or letter?  Respond with either: CAN SEE or CANNOT SEE  ',
        'options': ['CAN SEE', 'CANNOT SEE', None, None],
    },
    '1S': {
        'correct_answer': 'FRONT',
        'question_prompt': 'Is the number or letter in front of or behind the person?  Respond with a single word: FRONT or BEHIND  ',
        'options': ['FRONT', 'BEHIND', None, None],
    },
    '2V': {
        'correct_answer': '6',
        'question_prompt': 'What number or letter can the person see?   Respond with a single number or letter.',
        'options': ['6', '9', None, None],
    },
    '2S': {
        'correct_answer': 'FRONT',
        'question_prompt': "Is the number or letter on the person's left or right?  Respond with a single word: LEFT or RIGHT  ",
        'options': ['LEFT', 'RIGHT', None, None],
    },
    '3VS': {
        'correct_answer': '6',
        'question_prompt': (
            "In this section, there will be two numbers or letters on the floor. "
            "Before each question, you will be told whether to report the one on the person's LEFT or RIGHT.\n"
            "Respond with that single number or letter using the arrow keys."
        ),
        'options': ['6', '9', 'n', 'u'],
    },
}

CSV_COLUMNS = [
    'display', 'sample_id', 'image_path', 'correct_answer',
    'stimulus_set', 'question_type', 'question_prompt',
    'filename', 'image_number', 'figure_type', 'margin_size',
    'fov_angle', 'figure_rotation', 'number_rotation',
    'number_position_x', 'number_position_y',
    'number_location_x', 'number_location_y',
    'relative_location', 'number_appearance_type', 'number_appearance',
    'option_1', 'option_2', 'option_3', 'option_4',
    'block', 'trial_prompt',
]

METADATA_FIELDS = [
    'filename', 'image_number', 'figure_type', 'margin_size',
    'fov_angle', 'figure_rotation', 'number_rotation',
    'number_position_x', 'number_position_y',
    'number_location_x', 'number_location_y',
    'relative_location', 'number_appearance_type', 'number_appearance',
]


def infer_symbol_config(number_appearance, symbol_offset, question_type, offsets):
    """Return the SYMBOL_CONFIGS key for a given number_appearance."""
    na = number_appearance.lower()
    if na == 'none':
        key = 'symbol_offset_' + question_type
        idx = offsets[key] % len(SYMBOL_CONFIGS)
        offsets[key] += 1
        return list(SYMBOL_CONFIGS.keys())[idx]
    for config_key, config_data in SYMBOL_CONFIGS.items():
        possible = [s.lower() for s in config_data['rotations'].values()]
        if na in possible:
            return config_key
    raise ValueError(f"Cannot find symbol_config for number_appearance: {number_appearance!r}")


def get_block(stimulus_set, question_type):
    for block, ss_qt_list in BLOCK_SS_QT.items():
        if (stimulus_set, question_type) in ss_qt_list:
            return block
    return None


def get_options(sample):
    ss = sample['stimulus_set']
    qt = sample['question_type']
    meta = sample['metadata']

    if ss == 'level_1':
        if qt == 'visual':
            return ['CAN SEE', 'CANNOT SEE', None, None]
        else:
            return ['FRONT', 'BEHIND', None, None]
    elif ss == 'level_2':
        if qt == 'visual':
            appearance = str(meta.get('number_appearance', '6')).lower()
            pair = PAIR_SYMBOLS.get(appearance, ['6', '9'])
            return [pair[0], pair[1], None, None]
        else:
            return ['LEFT', 'RIGHT', None, None]
    elif ss == 'level_3':
        appearance = str(meta.get('number_appearance', '6')).lower()
        alternate = str(meta.get('alternate_number', '')).lower()
        pair1 = set(PAIR_SYMBOLS.get(appearance, ['6', '9']))
        pair2 = set(PAIR_SYMBOLS.get(alternate, ['6', '9']))
        ordered = [s for s in MASTER_ORDER if s in pair1 | pair2]
        return ordered[:4]
    return [None, None, None, None]


def get_trial_prompt(sample):
    if sample['stimulus_set'] == 'level_3':
        rel_loc = str(sample['metadata'].get('relative_location', '')).lower()
        return 'LEFT' if 'left' in rel_loc else 'RIGHT'
    return None


def format_prompt(prompt):
    """Replace newlines with spaces to match the online-experiment format."""
    return prompt.replace('\n', ' ') if prompt else ''


def make_block_prompt_row(block):
    bp = BLOCK_PROMPTS[block]
    opts = bp['options']
    return {
        'display': 'block_prompt',
        'sample_id': '',
        'image_path': '',
        'correct_answer': bp['correct_answer'],
        'stimulus_set': '',
        'question_type': '',
        'question_prompt': bp['question_prompt'],
        'filename': '', 'image_number': '', 'figure_type': '',
        'margin_size': '', 'fov_angle': '', 'figure_rotation': '',
        'number_rotation': '', 'number_position_x': '', 'number_position_y': '',
        'number_location_x': '', 'number_location_y': '',
        'relative_location': '', 'number_appearance_type': '', 'number_appearance': '',
        'option_1': opts[0], 'option_2': opts[1],
        'option_3': opts[2], 'option_4': opts[3],
        'block': '',
        'trial_prompt': None,
    }


def make_instructions_row():
    return {col: ('instructions' if col == 'display' else '') for col in CSV_COLUMNS}


def make_transition_row():
    return {col: ('test_transition' if col == 'display' else '') for col in CSV_COLUMNS}


def load_dataset_into_bins(dataset_path, bins, use_stimulus_sets):
    """
    Load samples from a JSON dataset into bins.

    bins: dict keyed by (stimulus_set, question_type, symbol_config) ->
          rotation_bin (0-7) -> list of (sample, dataset_base_dir)

    use_stimulus_sets: set of stimulus_set values to include.
    """
    dataset_base_dir = os.path.dirname(dataset_path)
    offsets = {'symbol_offset_visual': 0, 'symbol_offset_spatial': 0}

    with open(dataset_path, 'r') as f:
        data = json.load(f)

    n_loaded = 0
    for sample in data['samples']:
        ss = sample['stimulus_set']
        qt = sample['question_type']
        if ss not in use_stimulus_sets:
            continue

        na = sample['metadata']['number_appearance']
        symbol_config = infer_symbol_config(na, None, qt, offsets)

        condition = (ss, qt, symbol_config)
        rotation_bin = int(sample['metadata']['figure_rotation'] // 45) % 8

        bins.setdefault(condition, {}).setdefault(rotation_bin, []).append(
            (sample, dataset_base_dir)
        )
        n_loaded += 1

    return n_loaded


def sample_block(bins, block, trials_per_block, rng):
    """
    Randomly select exactly trials_per_block samples for a given block,
    balanced across (stimulus_set, question_type, symbol_config) conditions
    and rotation bins within each condition.
    """
    ss_qt_pairs = BLOCK_SS_QT[block]
    conditions = [
        (ss, qt, sym_key)
        for ss, qt in ss_qt_pairs
        for sym_key in SYMBOL_CONFIGS.keys()
    ]
    available = [c for c in conditions if c in bins]

    if not available:
        print(f"  Warning: no data found for block {block}, skipping.")
        return []

    n_conditions = len(available)
    n_bins = 8  # 8 rotation bins of 45° each

    assert trials_per_block % n_conditions == 0, (
        f"trials_per_block ({trials_per_block}) must be divisible by "
        f"number of symbol conditions in block {block} ({n_conditions})"
    )
    assert trials_per_block % n_bins == 0, (
        f"trials_per_block ({trials_per_block}) must be divisible by "
        f"number of rotation bins ({n_bins})"
    )
    per_condition = trials_per_block // n_conditions  # symbol balance
    per_bin = trials_per_block // n_bins              # rotation balance

    # Build two independent balanced schedules and pair them.
    # This ensures exact marginal balance for both rotation and symbol
    # while leaving their cross-distribution random.
    rotation_schedule = list(range(n_bins)) * per_bin        # each bin exactly per_bin times
    condition_schedule = list(range(n_conditions)) * per_condition  # each condition exactly per_condition times
    rng.shuffle(rotation_schedule)
    rng.shuffle(condition_schedule)

    selected = []
    for cond_idx, bin_idx in zip(condition_schedule, rotation_schedule):
        condition = available[cond_idx]
        bin_samples = bins[condition].get(bin_idx, [])
        if not bin_samples:
            # Rotation bin missing for this condition — fall back to any bin
            bin_samples = [item for bl in bins[condition].values() for item in bl]
        selected.append(rng.choice(bin_samples))

    return selected  # list of (sample, dataset_base_dir)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Sample a balanced human dataset from one or more AI task datasets. "
            "Datasets containing level_3 samples contribute only level_3; "
            "others contribute level_1 and level_2."
        )
    )
    parser.add_argument(
        "--datasets", required=True, nargs="+",
        help="Paths to dataset JSON files."
    )
    parser.add_argument(
        "--trials_per_block", required=True, type=int,
        help="Number of trials per block (1V, 1S, 2V, 2S, 3VS). Must be divisible by the number of conditions in each block."
    )
    parser.add_argument(
        "--dataset_name", required=True,
        help="Output dataset name (also determines output directory)."
    )
    parser.add_argument("--seed", default=42, type=int, help="Random seed.")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    dataset_dir = os.path.join("datasets", args.dataset_name)
    if os.path.exists(dataset_dir):
        print(f"Error: Dataset '{args.dataset_name}' already exists at {dataset_dir}")
        return 1

    # Determine which stimulus sets each dataset contributes
    print("Loading datasets...")
    bins = {}
    for dataset_path in args.datasets:
        with open(dataset_path, 'r') as f:
            probe = json.load(f)
        present = {s['stimulus_set'] for s in probe['samples']}
        if 'level_3' in present:
            use = {'level_3'}
            print(f"  {os.path.basename(dataset_path)}: using level_3 only ({len(probe['samples'])} total samples)")
        else:
            use = {'level_1', 'level_2'}
            print(f"  {os.path.basename(dataset_path)}: using level_1 + level_2 ({len(probe['samples'])} total samples)")
        n = load_dataset_into_bins(dataset_path, bins, use)
        print(f"    -> {n} samples loaded into bins")

    # Sample each block
    print(f"\nSampling {args.trials_per_block} trials per block...")
    selected_by_block = {}
    for block in BLOCK_ORDER:
        block_samples = sample_block(bins, block, args.trials_per_block, rng)
        selected_by_block[block] = block_samples
        print(f"  Block {block}: {len(block_samples)} trials")

    # Copy images and build dataset entries
    os.makedirs(dataset_dir, exist_ok=True)
    images_dir = os.path.join(dataset_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    dataset_samples = []
    new_id = 0

    for block in BLOCK_ORDER:
        for sample, dataset_base_dir in selected_by_block[block]:
            original_image_path = os.path.join(dataset_base_dir, sample['image_path'])
            if not os.path.exists(original_image_path):
                # Try alternate image directories (e.g. images_L3 instead of images)
                alt = sample['image_path'].replace('images/', 'images_L3/', 1)
                original_image_path = os.path.join(dataset_base_dir, alt)
            if not os.path.exists(original_image_path):
                print(f"  Warning: image not found: {sample['image_path']}")
                continue

            ext = os.path.splitext(sample['image_path'])[1]
            new_filename = f"{args.dataset_name}_sample_{new_id:04d}{ext}"
            shutil.copy2(original_image_path, os.path.join(images_dir, new_filename))

            dataset_samples.append({
                "sample_id": new_id,
                "block": block,
                "stimulus_set": sample["stimulus_set"],
                "question_type": sample["question_type"],
                "image_path": os.path.join("images", new_filename),
                "question_prompt": sample["question_prompt"],
                "correct_answer": sample["correct_answer"],
                "metadata": sample["metadata"],
            })
            new_id += 1

    # Save JSON
    dataset_json = {
        "dataset_name": args.dataset_name,
        "total_samples": len(dataset_samples),
        "trials_per_block": args.trials_per_block,
        "samples": dataset_samples,
    }
    json_path = os.path.join(dataset_dir, f"{args.dataset_name}.json")
    with open(json_path, 'w') as f:
        json.dump(dataset_json, f, indent=2)

    # Build CSV with block structure
    csv_rows = [make_instructions_row(), make_transition_row()]

    for block in BLOCK_ORDER:
        block_entries = [s for s in dataset_samples if s["block"] == block]
        if not block_entries:
            continue
        csv_rows.append(make_block_prompt_row(block))
        for s in block_entries:
            opts = get_options(s)
            meta = s['metadata']
            row = {
                'display': 'test',
                'sample_id': str(s['sample_id']),
                'image_path': os.path.basename(s['image_path']),
                'correct_answer': s['correct_answer'],
                'stimulus_set': s['stimulus_set'],
                'question_type': s['question_type'],
                'question_prompt': format_prompt(s['question_prompt']),
                'option_1': opts[0], 'option_2': opts[1],
                'option_3': opts[2], 'option_4': opts[3],
                'block': block,
                'trial_prompt': get_trial_prompt(s),
            }
            for field in METADATA_FIELDS:
                row[field] = meta.get(field, '')
            csv_rows.append(row)

    csv_path = os.path.join(dataset_dir, f"{args.dataset_name}.csv")
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"\nDataset '{args.dataset_name}' created:")
    print(f"  {len(dataset_samples)} total trials")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")
    print(f"  Images: {images_dir}/")

    return 0


if __name__ == "__main__":
    main()
