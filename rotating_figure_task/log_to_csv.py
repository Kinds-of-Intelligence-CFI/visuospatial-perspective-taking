import argparse
import csv
import os

from inspect_ai.log import read_eval_log


FIELDNAMES = [
    "stimulus_set",
    "question_type",
    "sample_id",
    "image_path",
    "filename",
    "figure_type",
    "figure_rotation",
    "number_rotation",
    "number_position_x",
    "number_position_y",
    "number_location_x",
    "number_location_y",
    "relative_location",
    "number_appearance_type",
    "number_appearance",
    "target",
    "model_answer",
    "model",
]


def collect_eval_files(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                for n in names:
                    if n.endswith(".eval"):
                        files.append(os.path.join(root, n))
        elif os.path.isfile(p):
            files.append(p)
        else:
            print(f"WARN: path does not exist, skipping: {p}")
    return files


def _normalise_target(raw):
    # Inspect can hand back a str or list[str]; lowercase to match the
    # combined_vpt_task_logs.csv convention and the ROTATION_MAP keys
    # used in answer_distribution_analysis.ipynb.
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    return str(raw).lower()


def row_from_sample(sample, model):
    stim = sample.metadata.get("stimulus_metadata", {}) or {}
    return {
        "stimulus_set": sample.metadata.get("stimulus_set", ""),
        "question_type": sample.metadata.get("question_type", ""),
        "sample_id": sample.id,
        "image_path": sample.metadata.get("image_path", ""),
        "filename": stim.get("filename", ""),
        "figure_type": stim.get("figure_type", ""),
        "figure_rotation": stim.get("figure_rotation", ""),
        "number_rotation": stim.get("number_rotation", ""),
        "number_position_x": stim.get("number_position_x", ""),
        "number_position_y": stim.get("number_position_y", ""),
        "number_location_x": stim.get("number_location_x", ""),
        "number_location_y": stim.get("number_location_y", ""),
        "relative_location": stim.get("relative_location", ""),
        "number_appearance_type": stim.get("number_appearance_type", ""),
        "number_appearance": stim.get("number_appearance", ""),
        "target": _normalise_target(sample.target),
        # Comma-strip mirrors the convention in Combine_logs.ipynb so free-form
        # completions don't break the CSV columns.
        "model_answer": sample.output.completion.replace(",", " "),
        "model": model,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Convert rotating-figure-task .eval logs to a CSV matching combined_vpt_task_logs.csv."
    )
    parser.add_argument(
        "--output_file",
        type=str,
        required=True,
        help="Path to the output CSV file.",
    )
    parser.add_argument(
        "--log_path",
        type=str,
        nargs="+",
        required=True,
        help="One or more .eval files or directories. Directories are searched recursively.",
    )
    args = parser.parse_args()

    eval_files = collect_eval_files(args.log_path)
    print(f"Found {len(eval_files)} .eval file(s).")
    if not eval_files:
        return

    total_written = 0
    total_skipped = 0
    with open(args.output_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

        for path in eval_files:
            log = read_eval_log(path, resolve_attachments=False)
            model = log.eval.model
            n_samples = len(log.samples) if log.samples else 0
            print(f"  {path}: {n_samples} samples (model={model})")

            written_here = 0
            skipped_here = 0
            for sample in log.samples or []:
                if sample.output is None or not isinstance(sample.output.completion, str):
                    print(f"    WARN: skipping sample {sample.id} - no string completion")
                    skipped_here += 1
                    continue
                writer.writerow(row_from_sample(sample, model))
                written_here += 1

            total_written += written_here
            total_skipped += skipped_here
            del log

    print(
        f"Wrote {total_written} row(s) to {args.output_file}"
        + (f" ({total_skipped} skipped)" if total_skipped else "")
    )


if __name__ == "__main__":
    main()
