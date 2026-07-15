



import argparse
import itertools
import os
import random

from director_task.question import SelectionRuleType


def main():
    parser = argparse.ArgumentParser(description="takes a set of datasets and will generate a human dataset that is some even subset of the large datasets.")
    parser.add_argument("--datasets", required=True, nargs="+", type=str, help="The paths to the datasets you want to pull samples from.")
    parser.add_argument("--num_samples", required=True, type=int, help="The number of samples you want in the final dataset.")
    parser.add_argument("--dataset_name", required=True, type=str, help="The name of the dataset to output, used to determine the output path.")
    parser.add_argument("--seed", default=42, type=int, help="seed for the random selection.")
    args = parser.parse_args()

    random.seed(args.seed)
    # first check that no existing dataset has the same name
    dataset_dir = os.path.join("datasets", args.dataset_name)
    if os.path.exists(dataset_dir):
        print(f"Error: Dataset '{args.dataset_name}' already exists at {dataset_dir}")
        return 1

    # next check that the number of samples is divisible by the number of datasets.
    assert args.num_samples % len(args.datasets) == 0, f"num samples: {args.num_samples} is not divisible by number of datasets: {len(args.datasets)}"

    bins = {}
    samples = []
    for dataset in args.datasets:
        samples_per_dataset = args.num_samples / len(args.datasets)
        selection_rule_types = [e.value for e in SelectionRuleType]
        sample_types = ["control", "test"]
        reversed_values = [True, False]
        conditions = list(itertools.product(selection_rule_types, sample_types, reversed_values))
        # check that the number of samples per dataset is divisible by 16 (4 selection rules * 2 control or test * 2 reversed or not)
        assert samples_per_dataset % len(conditions) == 0, f"num samples per dataset: {samples_per_dataset} not divisible by combinations {len(conditions)}"

        # Load and parse the dataset
        import json
        with open(dataset, 'r') as f:
            dataset_data = json.load(f)

        for sample in dataset_data['samples']:
            selection_rule_type = sample["selection_rule_type"]
            sample_type = sample["sample_type"]
            is_reversed = sample["is_reversed"]

            condition = (selection_rule_type, sample_type, is_reversed)

            if condition not in bins:
                bins[condition] = []

            bins[condition].append(sample)

        # now for each condition randomly select some samples
        for condition in conditions:
            selection_rule_type, sample_type, is_reversed = condition
            samples_per_condition = int(samples_per_dataset / len(conditions))

            new_samples = random.choices(bins[condition], k=samples_per_condition)
            samples.extend(new_samples)

    # now create the ne human dataset.
    # Create output directory structure
    os.makedirs(dataset_dir, exist_ok=True)
    images_dir = os.path.join(dataset_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    # Copy images and prepare dataset structure
    dataset_samples = []
    csv_rows = []

    for i, sample in enumerate(samples):
        # Create new sample ID
        new_sample_id = i
        # Get original image path from the sample's dataset directory
        original_image_path = None
        for dataset_path in args.datasets:
            dataset_base_dir = os.path.dirname(dataset_path)
            potential_image_path = os.path.join(dataset_base_dir, sample['image_path'])
            if os.path.exists(potential_image_path):
                original_image_path = potential_image_path
                break

        if original_image_path is None:
            print(f"Warning: Could not find image for sample {sample.get('sample_id', 'unknown')}: {sample['image_path']}")
            continue

        # Create new image filename
        image_extension = os.path.splitext(sample['image_path'])[1]
        new_image_filename = f"{args.dataset_name}_sample_{new_sample_id:04d}{image_extension}"
        new_image_path = os.path.join(images_dir, new_image_filename)

        # Copy the image
        import shutil
        shutil.copy2(original_image_path, new_image_path)

        # Create new sample entry for JSON
        new_sample = {
            "sample_id": new_sample_id,
            "selection_rule_type": sample["selection_rule_type"],
            "sample_type": sample["sample_type"],
            "image_path": os.path.join("images", new_image_filename),
            "question": sample["question"],
            "grid": sample["grid"],
            "answers": sample["answers"],
            "is_physics": sample["is_physics"],
            "is_reversed": sample["is_reversed"]
        }
        dataset_samples.append(new_sample)

        answer = sample["answers"]["director_coordinates"]
        # Extract the target from the answer
        target = chr(ord('A') + answer[0][0]) + str(answer[0][1]+1)  
        # Create CSV row with flattened data
        csv_row = {
            "sample_id": new_sample_id,
            "selection_rule_type": sample["selection_rule_type"],
            "sample_type": sample["sample_type"],
            "image_path": os.path.join("images", new_image_filename),
            "question": sample["question"]["natural_language"],
            "correct_answer": target,
        }
        csv_rows.append(csv_row)


    # Create JSON dataset file
    import json
    dataset_json = {
        "dataset_name": args.dataset_name,
        "total_samples": len(dataset_samples),
        "control_samples": len(dataset_samples)/2,
        "test_samples": len(dataset_samples)/2,
        "samples": dataset_samples,

    }

    json_output_path = os.path.join(dataset_dir, f"{args.dataset_name}.json")
    with open(json_output_path, 'w') as f:
        json.dump(dataset_json, f, indent=2)

    # Create CSV file
    import csv
    csv_output_path = os.path.join(dataset_dir, f"{args.dataset_name}.csv")
    if csv_rows:
        fieldnames = csv_rows[0].keys()
        with open(csv_output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

    print(f"Human dataset '{args.dataset_name}' created successfully!")
    print(f"- {len(dataset_samples)} samples")
    print(f"- JSON file: {json_output_path}")
    print(f"- CSV file: {csv_output_path}")
    print(f"- Images directory: {images_dir}")

    return 0 


if __name__ == "__main__":
    main()
