import os
import pandas as pd
import glob
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import re

path = os.getcwd()

## load results
experiment_dir = os.path.join(path, "director_task")
results_dir = os.path.join(experiment_dir, "results")
plot_dir = os.path.join(experiment_dir, "plots")

models = ["gpt-4o","gpt-4o-mini","o4-mini","o3"]
df = pd.DataFrame()
for base_model in models:
    pattern = f"ai_data_{base_model}.csv"
    filepaths = glob.glob(os.path.join(results_dir, pattern))
    for filepath in filepaths:
        temp_df = pd.read_csv(filepath, engine="python")
        temp_df = temp_df.map(lambda x: x.replace("\\", "/") if isinstance(x, str) else x)
        temp_df['model'] = base_model
        df = pd.concat([df, temp_df], ignore_index=True)

# extract data from filepath string
def parse_sample_id(df):
    result_df = df.copy()
    result_df['sample_number'] = df['sample_id'].str.extract(r'^(\d+)_').astype(int)
    result_df['task_type'] = df['sample_id'].apply(lambda x: 'control' if 'control_task' in x else 'director')
    result_df['fill_ratio'] = df['sample_id'].str.extract(r'fill_ratio_([0-9.]+)').astype(float)
    result_df['related_ratio'] = df['sample_id'].str.extract(r'related_ratio_([0-9.]+)').astype(float)
    result_df['encoding'] = df['sample_id'].apply(lambda x: 'ascii' if 'ascii' in x else 'default')
    return result_df

def split_selection_rule(value):
    if value.startswith("size"):
        return pd.Series(["size", "none"])
    elif value.startswith("spatial_same"):
        return pd.Series(["spatial", "same"])
    elif value.startswith("spatial_different"):
        return pd.Series(["spatial", "different"])
    elif value == "none":
        return pd.Series(["none", "none"])
    else:
        return pd.Series([None, None])

df2 = parse_sample_id(df)
df2["accuracy"] = df2["score"].replace({"C": 1, "I": 0})
df2["encoding"] = df2["encoding"].replace({"default": "image"})
df2[["selection_rule_type", "spatial_perspective"]] = df2["selection_rule_type"].apply(split_selection_rule)
df2['spatial_rule_and_perspective'] = df2['spatial_perspective'] + "_" + df2['selection_rule']

# set categorical variables
df2["sample_type"] = pd.Categorical(
    df2["sample_type"],
    categories=["control", "test"],
    ordered=True
)
df2["spatial_perspective"] = pd.Categorical(
    df2["spatial_perspective"],
    categories=["none", "same", "different"],
    ordered=True
)
df2["model"] = pd.Categorical(
    df2["model"],
    categories=["gpt-4o", "o4-mini", "o3"],
    ordered=True
)


## Display results
groups = ['spatial_perspective','sample_type','model']
subset = df2.copy()
# subset = df2[df2['selection_rule_type'] == 'spatial']
# subset = subset[subset['encoding'] == 'ascii']

grouped = subset.groupby(groups)['accuracy'].mean().reset_index()

third_levels = grouped[groups[2]].unique()
n_levels = len(third_levels)
fig_width = max(5 * n_levels, 10)
fig, axes = plt.subplots(1, n_levels, figsize=(fig_width, 6), sharey=True)

if n_levels == 1:
    axes = [axes]

for ax, level in zip(axes, third_levels):
    sns.barplot(
        data=grouped[grouped[groups[2]] == level],
        x=groups[0],
        y='accuracy',
        hue=groups[1],
        ax=ax
    )
    ax.set_ylim(0, 1)
    ax.set_ylabel('Mean Accuracy')
    ax.set_xlabel('')
    ax.set_title(f"{level}")

title = f"Mean Accuracy by {groups[0]}, {groups[1]}, and {groups[2]}"
plt.suptitle(title, y=0.98, fontsize=12)
plt.tight_layout()
plt.savefig(
    os.path.join(plot_dir, f"{title}.png"),
    dpi=300,
    bbox_inches="tight"
)
plt.show()

