import argparse
import csv
import os
from typing import List, Dict, Any

from inspect_ai.log import read_eval_log
from inspect_ai.model import ContentText
import pandas as pd



def main():
    # make the parser
    parser = argparse.ArgumentParser(description="Log data to a CSV file.")
    parser.add_argument(
        "--output_file",
        type=str,
        required=True,
        help="Path to the output CSV file",
    )
    parser.add_argument(
        "--log_path",
        type=str,
        nargs='+',
        required=True,
        help="the path to the log file(s)",
    )
    args = parser.parse_args()

    # create the dataframe to hold the data
    output_df = pd.DataFrame(columns=["sample_id", "score", "target", "sample_type", "selection_rule_type", "is_physics", "is_reversed", "selection_rule", "full_question", "director_answer_coordinates", "participant_coordinates", "output"])

    for log_path in args.log_path:
        if os.path.isdir(log_path):
            # recursively find all .eval files in the directory
            log_files = []
            for root, _, files in os.walk(log_path):
                for file in files:
                    if file.endswith(".eval"):
                        log_files.append(os.path.join(root, file))
        else:
            log_files = [log_path]

        for log_file in log_files:
            log = read_eval_log(log_file, resolve_attachments=False)
            for sample in log.samples:
                sample_id = f"{sample.id}_{log_file}"
                score = sample.score.value
                target = sample.target
                sample_type = sample.metadata["sample_type"]
                selection_rule_type = sample.metadata["selection_rule_type"]
                is_physics = sample.metadata["is_physics"]
                is_reversed = sample.metadata["is_reversed"]
                selection_rule = sample.metadata["question"]["selection_rule"]
                full_question = sample.metadata["question"]["full_question"]
                director_answer_coordinates = ""
                for answer in sample.metadata["director_answer_coordinates"]:
                    director_answer_coordinates += f"[{answer[0]}-{answer[1]}]"

                participant_coordinates = ""
                for answer in sample.metadata["participant_coordinates"]:
                    participant_coordinates += f"[{answer[0]}-{answer[1]}]"


                if not isinstance(sample.output.message.content, str):
                    answer = None
                    for output in sample.output.message.content:
                        if isinstance(output, str):
                            answer = output.strip()
                        elif isinstance(output, ContentText):
                            answer = output.text.strip()
                        else:
                            continue
                    if answer is None:
                        print(f"Warning: No valid string found in output content: {sample.output.message.content}")
                        continue
                else:
                    answer = sample.output.message.content.strip()

                output = answer[:2]

                output_df = pd.concat([output_df, pd.DataFrame([{
                    "sample_id": sample_id,
                    "score": score,
                    "target": target,
                    "sample_type": sample_type,
                    "selection_rule_type": selection_rule_type,
                    "is_physics": is_physics,
                    "is_reversed": is_reversed,
                    "selection_rule": selection_rule,
                    "full_question": full_question,
                    "director_answer_coordinates": director_answer_coordinates,
                    "participant_coordinates": participant_coordinates,
                    "output": output
                }])], ignore_index=True)
                
    # save the dataframe to a csv file
    output_df.to_csv(args.output_file, index=False)



if __name__ == "__main__":
    main()