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

def split_selection_rule(value):
    if value.startswith("size"):
        return pd.Series(["size", "none"])
    elif value.startswith("spatial_same"):
        return pd.Series(["spatial", "vertical"])
    elif value.startswith("spatial_different"):
        return pd.Series(["spatial", "horizontal"])
    elif value == "none":
        return pd.Series(["none", "none"])
    else:
        return pd.Series([None, None])

df = pd.read_csv(os.path.join(results_dir, "combined_director_task_logs.csv"))
df['model'] = df['model'].str.split('/').str[-1]
df['target_value'] = df['target'].str.replace(r'[\[\]"\']', '', regex=True).str.strip()
df['accuracy'] = (df['model_answer'] == df['target_value']).astype(int)
df['format'] = np.where(df['ascii_image'], 'ascii', 'image')
df[["relative_adjective", "spatial_adjective"]] = df["selection_rule_type"].apply(split_selection_rule)
df['perspective_reversal'] = np.where(df['is_reversed'], 'reversed', 'not_reversed')
df['visual_perspective'] = np.where(df['sample_type'] == "control", 'visual-shared', 'visual-different')
df['spatial_perspective'] = np.where(
    (df['spatial_adjective'] == "horizontal") &
    (df['perspective_reversal'] == "reversed"), 'spatial-different', 'spatial-shared')

df["model"] = pd.Categorical(
    df["model"],
    categories=["o3","o4-mini","gpt-4o","gpt-4o-mini"],
    ordered=True
)

# remove control task
df = df[df['task_name'] != 'control_task']

# save
df.to_csv(os.path.join(results_dir, "director_task_processed.csv"), index=False)



## Display results: visual perspective
df_vpt = df[df['spatial_adjective'] != 'horizontal']
df_vpt = df_vpt[df_vpt['perspective_reversal'] == 'reversed']

groups = ['visual_perspective','format','model']
ax_labels = {'visual_perspective':'Visual Perspective',
                'format':'Task Format',
                'model':'AI Model'}
vis_persp_labels = {
    'visual-shared': 'Visual-shared',
    'visual-different': 'Visual-different'
}
format_labels = {
    'ascii': 'ASCII',
    'image': 'Image',
}
subset = df_vpt.copy()
subset['combined'] = (
    subset['visual_perspective'].map(vis_persp_labels) + '\n' +
    subset['format'].map(format_labels)
)
subset["visual_perspective"] = pd.Categorical(
    subset["visual_perspective"],
    categories=["Visual-shared", "Visual-different"],
    ordered=True
)
subset["format"] = pd.Categorical(
    subset["format"],
    categories=["ASCII", "Image"],
    ordered=True
)

fig, ax = plt.subplots(figsize=(10, 8))
sns.barplot(
    data=subset,
    x='combined',
    y='accuracy',
    hue=groups[2],
    ax=ax,
    errorbar='ci',
    capsize=0.1,
    err_kws={'linewidth': 1.5},
    palette=sns.color_palette("tab20"),
)

ax.set_ylim(0, 1)
ax.set_ylabel('Mean Accuracy', fontsize=18)
ax.set_xlabel(f'{ax_labels[groups[0]]} × {ax_labels[groups[1]]}', fontsize=18, labelpad=15)
ax.legend(title='', bbox_to_anchor=(0.70, 1), loc='upper left',fontsize=18)

title = f"Mean Accuracy by {ax_labels[groups[0]]}, {ax_labels[groups[1]]}, and {ax_labels[groups[2]]}"
# plt.title(title, fontsize=14, pad=20)
plt.xticks(fontsize=18)
plt.yticks(fontsize=18)
plt.tight_layout()
plt.savefig(
    os.path.join(plot_dir, f"{title}.png"),
    dpi=300,
    bbox_inches="tight"
)
plt.show()

## Display results: spatial perspective
df_spt = df[df['relative_adjective'] == 'spatial']
df_spt = df_spt[df_spt['visual_perspective'] == 'visual-shared']

groups = ['spatial_adjective','perspective_reversal','model']
ax_labels = {'spatial_adjective':'Spatial Perspective',
                'perspective_reversal':'Perspective Reversal',
                'model':'AI Model'}
spatial_adj_labels = {
    'vertical': "Spatial-shared",
    'horizontal': "Spatial-different",
}
persp_rev_labels = {
    'reversed': "Director POV",
    'not_reversed': "Participant POV",
}
subset = df_spt.copy()
subset['combined'] = (
    subset['spatial_adjective'].map(spatial_adj_labels) + '\n' +
    subset['perspective_reversal'].map(persp_rev_labels)
)
combined_order = [
    "Spatial-shared\nParticipant POV",
    "Spatial-shared\nDirector POV",
    "Spatial-different\nParticipant POV",
    "Spatial-different\nDirector POV",
]

fig, ax = plt.subplots(figsize=(10, 8))
sns.barplot(
    data=subset,
    x='combined',
    y='accuracy',
    hue=groups[2],
    order=combined_order,
    ax=ax,
    errorbar='ci',
    capsize=0.1,
    err_kws={'linewidth': 1.5},
    palette=sns.color_palette("tab20"),
)

ax.set_ylim(0, 1)
ax.set_ylabel('Mean Accuracy', fontsize=18)
ax.set_xlabel(f'{ax_labels[groups[0]]} × {ax_labels[groups[1]]}', fontsize=18,labelpad=15)
ax.legend(title='', bbox_to_anchor=(0.02,0.3), loc='upper left', fontsize=18)

title = f"Mean Accuracy by {ax_labels[groups[0]]}, {ax_labels[groups[1]]}, and {ax_labels[groups[2]]}"
# plt.title(title, fontsize=14, pad=20)
plt.xticks(fontsize=18)
plt.yticks(fontsize=18)
plt.tight_layout()
plt.savefig(
    os.path.join(plot_dir, f"{title}.png"),
    dpi=300,
    bbox_inches="tight"
)
plt.show()





## Display results: visual x spatial perspective
df_vspt = df[df['relative_adjective'] == 'spatial']
df_vspt = df_vspt[df_vspt['perspective_reversal'] == 'reversed']

groups = ['visual_perspective','spatial_adjective','model']
ax_labels = {'visual_perspective':'Visual Perspective',
             'spatial_adjective':'Spatial Perspective',
             'model':'AI Model'}
vis_persp_labels = {
    'visual-shared': 'Visual-shared',
    'visual-different': 'Visual-different'
}
spatial_adj_labels = {
    'vertical': "Spatial-shared",
    'horizontal': "Spatial-different",
}
subset = df_vspt.copy()
subset['combined'] = (
    subset['visual_perspective'].map(vis_persp_labels) + '\n' +
    subset['spatial_adjective'].map(spatial_adj_labels)
)
combined_order = [
    "Visual-shared\nSpatial-shared",
    "Visual-shared\nSpatial-different",
    "Visual-different\nSpatial-shared",
    "Visual-different\nSpatial-different",
]

fig, ax = plt.subplots(figsize=(10, 8))
sns.barplot(
    data=subset,
    x='combined',
    y='accuracy',
    hue=groups[2],
    order=combined_order,
    ax=ax,
    errorbar='ci',
    capsize=0.1,
    err_kws={'linewidth': 1.5},
    palette=sns.color_palette("tab20"),
)

ax.set_ylim(0, 1)
ax.set_ylabel('Mean Accuracy', fontsize=18)
ax.set_xlabel(f'{ax_labels[groups[0]]} × {ax_labels[groups[1]]}', fontsize=18,labelpad=15)
ax.legend(title='', bbox_to_anchor=(0.70, 1), loc='upper left', fontsize=18)

title = f"Mean Accuracy by {ax_labels[groups[0]]}, {ax_labels[groups[1]]}, and {ax_labels[groups[2]]}"
# plt.title("Imag", fontsize=14, pad=20)
plt.xticks(fontsize=18)
plt.yticks(fontsize=18)
plt.tight_layout()
plt.savefig(
    os.path.join(plot_dir, f"{title}.png"),
    dpi=300,
    bbox_inches="tight"
)
plt.show()

## side-by-side version

formats = ['ascii', 'image']
# Base filtering (shared across both plots)
df_vspt = df[
    (df['relative_adjective'] == 'spatial') &
    (df['perspective_reversal'] == 'reversed') &
    (df['format'].isin(formats))
].copy()
groups = ['visual_perspective', 'spatial_adjective', 'model']
ax_labels = {
    'visual_perspective': 'Visual Perspective',
    'spatial_adjective': 'Spatial Perspective',
    'model': 'AI Model'
}
vis_persp_labels = {
    'visual-shared': 'Visual-shared',
    'visual-different': 'Visual-different'
}
spatial_adj_labels = {
    'vertical': "Spatial-shared",
    'horizontal': "Spatial-different",
}
df_vspt['combined'] = (
    df_vspt['visual_perspective'].map(vis_persp_labels) + '\n' +
    df_vspt['spatial_adjective'].map(spatial_adj_labels)
)
combined_order = [
    "Visual-shared\nSpatial-shared",
    "Visual-shared\nSpatial-different",
    "Visual-different\nSpatial-shared",
    "Visual-different\nSpatial-different",
]

# ---- Plot ----
fig, axes = plt.subplots(1, 2, figsize=(13, 6), sharey=True)
for ax, fmt in zip(axes, formats):
    subset = df_vspt[df_vspt['format'] == fmt]
    sns.barplot(
        data=subset,
        x='combined',
        y='accuracy',
        hue='model',
        order=combined_order,
        ax=ax,
        errorbar='ci',
        capsize=0.1,
        err_kws={'linewidth': 1.5},
        palette=sns.color_palette("tab20"),
    )
    ax.set_ylim(0, 1)
    ax.set_xlabel(f"{ax_labels[groups[0]]} × {ax_labels[groups[1]]}")
    ax.set_title(f"Format: {fmt.upper()}")
    # Only keep legend on the right plot
    if fmt == 'ascii':
        ax.get_legend().remove()
axes[0].set_ylabel('Mean Accuracy')

# Shared legend
# handles, labels = axes[1].get_legend_handles_labels()
# fig.legend(
#     handles, labels,
#     title='Model',
#     bbox_to_anchor=(1.02, 0.9),
#     loc='upper left'
# )
# fig.suptitle(
#     f"Mean Accuracy by {ax_labels[groups[0]]}, "
#     f"{ax_labels[groups[1]]}, and {ax_labels[groups[2]]}",
#     fontsize=14
# )
plt.tight_layout()
plt.savefig(
    os.path.join(plot_dir, "Mean Accuracy by Perspective and Format.png"),
    dpi=300,
    bbox_inches="tight"
)
plt.show()



## just model and format

## Display results: model × format (no visual perspective)

df_vpt = df[df['spatial_adjective'] != 'horizontal']
df_vpt = df_vpt[df_vpt['perspective_reversal'] == 'reversed']

format_labels = {
    'ascii': 'ASCII',
    'image': 'Image',
}

subset = df_vpt.copy()
subset['format_label'] = subset['format'].map(format_labels)

subset["format_label"] = pd.Categorical(
    subset["format_label"],
    categories=["ASCII", "Image"],
    ordered=True
)

fig, ax = plt.subplots(figsize=(8, 6))
sns.barplot(
    data=subset,
    x='format_label',
    y='accuracy',
    hue='model',
    ax=ax,
    errorbar='ci',
    capsize=0.1,
    err_kws={'linewidth': 1.5},
    palette=sns.color_palette("tab20"),
)

ax.set_ylim(0, 1)
ax.set_ylabel('Mean Accuracy', fontsize=12)
ax.set_xlabel('Task Format', fontsize=12)
ax.legend(title='Model', bbox_to_anchor=(1.02, 1), loc='upper left')

title = "Mean Accuracy by Task Format and Model"
plt.tight_layout()
plt.savefig(
    os.path.join(plot_dir, f"{title}.png"),
    dpi=300,
    bbox_inches="tight"
)
plt.show()
