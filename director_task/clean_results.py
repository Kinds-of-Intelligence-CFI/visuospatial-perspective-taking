"""Select director-task observations and reject ambiguous repeated trials."""

CONTROL_BLOCK_DESCRIPTION = (
    "Each cell in the grid has a backing plate behind the item made of a "
    "specific material. This is used for the inventory management system "
    "to monitor item placement."
)
TRIAL_KEY = ["dataset_path", "image_path", "model", "ascii_image"]


def clean_director_results(df):
    """Exclude control-task runs, then remove identical repeated observations.

    Some historical exports omit task_name. The control prompt identifies those
    runs independently of that field. sample_type='control' is a valid director
    condition and must stay. Conflicting answers must never be chosen silently.
    """
    control = df["task_name"].eq("control_task") | df[
        "block_description"
    ].str.strip().eq(CONTROL_BLOCK_DESCRIPTION)
    result = df.loc[~control].copy()
    result["task_name"] = result["task_name"].fillna("directors_task")
    repeated = result.duplicated(keep="first")
    result = result.loc[~repeated].copy()
    if result[TRIAL_KEY].isna().any().any():
        raise ValueError("Director trial identity contains missing values.")
    conflicts = result.duplicated(TRIAL_KEY, keep=False)
    if conflicts.any():
        raise ValueError(
            f"{conflicts.sum()} rows have conflicting director trial identities; "
            "resolve these observations before running the analysis."
        )
    print(
        f"Excluded {control.sum()} control-task rows; removed "
        f"{repeated.sum()} identical duplicate rows; retained {len(result)} trials."
    )
    return result
