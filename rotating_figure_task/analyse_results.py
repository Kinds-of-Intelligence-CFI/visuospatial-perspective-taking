import os
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

# Progress messages contain degree/arrow glyphs; force UTF-8 so they don't
# crash on Windows consoles using a legacy (cp1252) code page.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

path = os.getcwd()

## load results
experiment_dir = os.path.join(path, "rotating_figure_task")
results_dir = os.path.join(experiment_dir, "results")
plot_dir = os.path.join(experiment_dir, "plots")
os.makedirs(plot_dir, exist_ok=True)

df = pd.read_csv(os.path.join(results_dir, "combined_vpt_task_logs.csv"))

# Clean model names
df['model'] = df['model'].str.split('/').str[-1]

# ===========================================
# Load and append human baseline data
# ===========================================
human_results_path = os.path.join(path, "datasets", "human_rft_48", "rft_48_human_results.csv")
if os.path.exists(human_results_path):
    raw = pd.read_csv(human_results_path, low_memory=False)

    # Keep only actual test response rows (one response row per trial per participant)
    human = raw[
        (raw['Spreadsheet: display'] == 'test') &
        (raw['Screen'] == 'test') &
        (raw['Response'].notna())
    ].copy()

    human_df = pd.DataFrame({
        'stimulus_set':       human['Spreadsheet: stimulus_set'].values,
        'question_type':      human['Spreadsheet: question_type'].values,
        'figure_rotation':    human['Spreadsheet: figure_rotation'].values,
        'number_appearance':  human['Spreadsheet: number_appearance'].values,
        'relative_location':  human['Spreadsheet: relative_location'].values,
        'target':             human['Spreadsheet: correct_answer'].astype(str).values,
        'model_answer':       human['Response'].astype(str).values,
        'model':              'human',
        'participant_id':     human['Participant Public ID'].values,
        'filename':           human['Spreadsheet: filename'].values,
        'rt':                 human['Reaction Time'].values,
    })

    df = pd.concat([df, human_df], ignore_index=True)
    print(f"Human baseline: {len(human_df)} trials from {raw['Participant Public ID'].nunique()} participants")

# Calculate accuracy
df['model_answer_clean'] = df['model_answer'].str.upper().str.strip()
df['target_clean'] = df['target'].str.upper().str.strip()
df['accuracy'] = (df['model_answer_clean'] == df['target_clean']).astype(int)

# Identify valid responses (based on all possible targets)
valid_responses = set(df['target_clean'].unique())
df['is_valid_response'] = df['model_answer_clean'].isin(valid_responses).astype(int)
df['is_invalid_response'] = 1 - df['is_valid_response']

# ===========================================
# Create VPT-relevant variables
# ===========================================

# VPT Level: None (controls) → Level 1 (visibility) → Level 2 (appearance/integrated)
def get_vpt_level(stimulus_set):
    if stimulus_set in ['control_1', 'control_2']:
        return 'None'
    elif stimulus_set == 'level_1':
        return 'Level 1'
    else:  # level_2, level_3
        return 'Level 2'

df['vpt_level'] = df['stimulus_set'].apply(get_vpt_level)

# Condition type with descriptive labels
condition_labels = {
    'control_1': 'Control 1:\nSymbol ID',
    'control_2': 'Control 2:\nFigure Orientation',
    'level_1': 'Test 1:\nVisibility (L1 VPT)',
    'level_2': 'Test 2:\nAppearance (L2 VPT)',
    'level_3': 'Test 3:\nIntegrated (L2 VPT)'
}
df['condition'] = df['stimulus_set'].map(condition_labels)

# Short condition labels for plots
condition_short = {
    'control_1': 'Control 1',
    'control_2': 'Control 2',
    'level_1': 'Test 1 (L1)',
    'level_2': 'Test 2 (L2)',
    'level_3': 'Test 3 (L2)'
}
df['condition_short'] = df['stimulus_set'].map(condition_short)

# Question type labels
question_labels = {
    'visual': 'Visual',
    'spatial': 'Spatial'
}

# Test 3 (level_3) has only one content type recorded as 'visual' but is actually visuospatial
def get_question_type_label(row):
    if row['stimulus_set'] == 'level_3' and row['question_type'] == 'visual':
        return 'Visuospatial'
    return question_labels.get(row['question_type'], row['question_type'])

df['question_type_label'] = df.apply(get_question_type_label, axis=1)

# Set factor orders
df["model"] = pd.Categorical(
    df["model"],
    categories=["o3", "o4-mini", "gpt-4o", "gpt-4o-mini", "human"],
    ordered=True
)

df["stimulus_set"] = pd.Categorical(
    df["stimulus_set"],
    categories=['control_1', 'control_2', 'level_1', 'level_2', 'level_3'],
    ordered=True
)

df["vpt_level"] = pd.Categorical(
    df["vpt_level"],
    categories=['None', 'Level 1', 'Level 2'],
    ordered=True
)

df["condition_short"] = pd.Categorical(
    df["condition_short"],
    categories=['Control 1', 'Control 2', 'Test 1 (L1)', 'Test 2 (L2)', 'Test 3 (L2)'],
    ordered=True
)

# ===========================================
# Create rotation columns with different reference frames
# ===========================================
# Original system: 0° = right, 90° = forward, 180° = left, 270° = behind

# rotation_forward: 0° = forward, 90° = right, 180° = behind, 270° = left
df['rotation_forward'] = (90 - df['figure_rotation']) % 360

# rotation_egocentric: -90° = left, 0° = forward, 90° = right, 180° = behind
# Range: (-90, 270) so the wrap point is at left, not behind
df['rotation_egocentric'] = df['rotation_forward'].apply(
    lambda x: x - 360 if x > 270 else x
)

# Save processed data
df.to_csv(os.path.join(results_dir, "vpt_task_processed.csv"), index=False)

# ===========================================
# Control Conditions Comparison (excluding corner rotations for control_2)
# ===========================================

# Define corner rotation ranges to exclude (in original figure_rotation reference frame)
# These are ambiguous angles near the corners of the colored walls
corner_ranges = [
    (35, 55),    # right-front corner (between 0°=right and 90°=forward)
    (125, 145),  # left-front corner (between 90°=forward and 180°=left)
    (205, 225),  # left-back corner (between 180°=left and 270°=behind)
    (305, 325),  # right-back corner (between 270°=behind and 360°=right)
]

def is_corner_rotation(angle):
    """Check if angle falls within any corner range."""
    for low, high in corner_ranges:
        if low <= angle <= high:
            return True
    return False

# Create filtered control_2 data (excluding corners)
df['is_corner'] = df['figure_rotation'].apply(is_corner_rotation)

# Build comparison dataframe with all three conditions:
# 1. Control 1 (all)
# 2. Control 2 (all - original)
# 3. Control 2 (corners removed)

# Control 1 data
df_control1 = df[df['stimulus_set'] == 'control_1'].copy()
df_control1['control_condition'] = df_control1['question_type'].apply(
    lambda q: f"Control 1\n({q.title()})"
)

# Control 2 original (all rotations)
df_control2_all = df[df['stimulus_set'] == 'control_2'].copy()
df_control2_all['control_condition'] = df_control2_all['question_type'].apply(
    lambda q: f"Control 2\n({q.title()})"
)

# Control 2 corners removed
df_control2_filtered = df[(df['stimulus_set'] == 'control_2') & (~df['is_corner'])].copy()
df_control2_filtered['control_condition'] = df_control2_filtered['question_type'].apply(
    lambda q: f"Control 2\nNo Corners\n({q.title()})"
)

# Combine all
df_control_comparison = pd.concat([df_control1, df_control2_all, df_control2_filtered], ignore_index=True)

# Set order for conditions
condition_order = [
    'Control 1\n(Visual)', 'Control 1\n(Spatial)',
    'Control 2\n(Visual)', 'Control 2\n(Spatial)',
    'Control 2\nNo Corners\n(Visual)', 'Control 2\nNo Corners\n(Spatial)'
]
df_control_comparison['control_condition'] = pd.Categorical(
    df_control_comparison['control_condition'],
    categories=condition_order,
    ordered=True
)

# Plot: Control conditions comparison (AI only — humans have no control trials)
df_control_comparison_ai = df_control_comparison[df_control_comparison['model'] != 'human'].copy()
df_control_comparison_ai['model'] = df_control_comparison_ai['model'].cat.remove_unused_categories()
fig, ax = plt.subplots(figsize=(14, 6))
sns.barplot(
    data=df_control_comparison_ai,
    x='control_condition',
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
ax.set_xlabel('Condition', fontsize=12)
ax.legend(title='Subject', bbox_to_anchor=(1.02, 1), loc='upper left')

# Add chance lines
ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5, label='Chance (binary)')
ax.axhline(y=0.25, color='gray', linestyle=':', alpha=0.5, label='Chance (4-way)')

# Add annotation about corner exclusion
n_excluded = df[(df['stimulus_set'] == 'control_2') & (df['is_corner'])].shape[0]
n_total_control2 = df[df['stimulus_set'] == 'control_2'].shape[0]
ax.text(0.02, 0.98, f'Corners excluded: {corner_ranges}\n({n_excluded}/{n_total_control2} trials, {100*n_excluded/n_total_control2:.1f}%)',
        transform=ax.transAxes, fontsize=9, verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.title('Control Conditions Accuracy Comparison')
plt.tight_layout()
plt.savefig(
    os.path.join(plot_dir, "Control Conditions Comparison (with and without corners).png"),
    dpi=300,
    bbox_inches="tight"
)
plt.show()

# Print summary statistics
print("\n" + "="*60)
print("CONTROL CONDITIONS COMPARISON")
print("="*60)
print(f"\nCorner ranges excluded: {corner_ranges}")
print(f"Control 2 trials excluded: {n_excluded}/{n_total_control2} ({100*n_excluded/n_total_control2:.1f}%)")
print("\nAccuracy by condition and model:")
comparison_summary = df_control_comparison.groupby(['control_condition', 'model'])['accuracy'].mean().unstack()
print(comparison_summary.round(3))

# ===========================================
# LaTeX Table: Control Conditions Mean Accuracy
# ===========================================

# Build table data: rows = models, columns = conditions (Control 1 Visual/Spatial, Control 2 Visual/Spatial, Control 2 No Corners Visual/Spatial)
latex_table_data = {}

ai_model_categories = [m for m in df['model'].cat.categories if m != 'human']
for model in ai_model_categories:
    row_data = {}

    # Control 1
    for q_type in ['visual', 'spatial']:
        mask = (df_control1['model'] == model) & (df_control1['question_type'] == q_type)
        acc = df_control1.loc[mask, 'accuracy'].mean()
        invalid_rate = df_control1.loc[mask, 'is_invalid_response'].mean()
        row_data[f'Control 1 {q_type.title()}'] = acc
        row_data[f'Control 1 {q_type.title()} Invalid'] = invalid_rate

    # Control 2 (all)
    for q_type in ['visual', 'spatial']:
        mask = (df_control2_all['model'] == model) & (df_control2_all['question_type'] == q_type)
        acc = df_control2_all.loc[mask, 'accuracy'].mean()
        row_data[f'Control 2 {q_type.title()}'] = acc

    # Control 2 (corners removed)
    for q_type in ['visual', 'spatial']:
        mask = (df_control2_filtered['model'] == model) & (df_control2_filtered['question_type'] == q_type)
        acc = df_control2_filtered.loc[mask, 'accuracy'].mean()
        row_data[f'Control 2 CR {q_type.title()}'] = acc

    latex_table_data[model] = row_data

latex_df = pd.DataFrame(latex_table_data).T

# Generate LaTeX table
print("\n" + "="*60)
print("LATEX TABLE: Control Conditions Mean Accuracy")
print("="*60)

latex_output = r"""\begin{table}[!h]
\centering
\caption{\label{tab:control_accuracy}Mean accuracy in control conditions by model and question type}
\centering
\resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{
\begin{tabular}[t]{lcccccccc}
\toprule
 & \multicolumn{4}{c}{Control 1} & \multicolumn{4}{c}{Control 2} \\
 & \multicolumn{2}{c}{Accuracy} & \multicolumn{2}{c}{Invalid} & \multicolumn{2}{c}{Accuracy} & \multicolumn{2}{c}{Accuracy (CR)} \\
Model & Visual & Spatial & Visual & Spatial & Visual & Spatial & Visual & Spatial \\
\midrule
"""

for model in ai_model_categories:
    row = latex_df.loc[model]
    latex_output += f"{model} & {row['Control 1 Visual']:.3f} & {row['Control 1 Spatial']:.3f} & "
    latex_output += f"{row['Control 1 Visual Invalid']:.3f} & {row['Control 1 Spatial Invalid']:.3f} & "
    latex_output += f"{row['Control 2 Visual']:.3f} & {row['Control 2 Spatial']:.3f} & "
    latex_output += f"{row['Control 2 CR Visual']:.3f} & {row['Control 2 CR Spatial']:.3f} \\\\\n"

latex_output += r"""\bottomrule
\multicolumn{9}{l}{\textsuperscript{} CR = corners removed (trials within \ang{10} of a corner [21.8\%] excluded)}\\
\multicolumn{9}{l}{\textsuperscript{} Invalid = proportion of responses not matching any valid answer option}\\
\end{tabular}}
\end{table}
"""

print(latex_output)

# Save LaTeX table to file
latex_table_path = os.path.join(results_dir, "control_accuracy_table.tex")
with open(latex_table_path, 'w') as f:
    f.write(latex_output)
print(f"\nLaTeX table saved to: {latex_table_path}")


# ===========================================
# Plot 3: Condition × Question Type × Model
# ===========================================

fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)

for ax, q_type in zip(axes, ['visual', 'spatial']):
    subset = df[df['question_type'] == q_type]
    sns.barplot(
        data=subset,
        x='condition_short',
        y='accuracy',
        hue='model',
        ax=ax,
        errorbar='ci',
        capsize=0.1,
        err_kws={'linewidth': 1.5},
        palette=sns.color_palette("tab20"),
    )
    ax.set_ylim(0, 1)
    ax.set_xlabel('Condition')
    # Visual column includes Visuospatial for Test 3
    title = 'Visual Questions (Visuospatial for Test 3)' if q_type == 'visual' else 'Spatial Questions'
    ax.set_title(title)
    ax.tick_params(axis='x', rotation=30)
    ax.get_legend().remove()

axes[0].set_ylabel('Mean Accuracy')

# Place single legend outside right of the figure
handles, labels = axes[1].get_legend_handles_labels()
fig.legend(handles, labels, title='Subject', bbox_to_anchor=(1.02, 0.5), loc='center left')

plt.tight_layout()
plt.savefig(
    os.path.join(plot_dir, "Mean Accuracy by Condition and Question Type.png"),
    dpi=300,
    bbox_inches="tight"
)
plt.show()


# ===========================================
# Angular Disparity Plotting Configuration and Helper Functions
# ===========================================

# Configuration: Choose rotation column for plots
# Options: 'figure_rotation' (original: 0=left, 90=forward)
#          'rotation_forward' (0=forward, 90=right, 180=behind, 270=left)
#          'rotation_egocentric' (-90=left, 0=forward, 90=right, ±180=behind)
ROTATION_COLUMN = 'rotation_egocentric'  # Change this to switch rotation reference frame

# Rotation column settings
ROTATION_SETTINGS = {
    'figure_rotation': {
        'label': 'Figure Rotation (°)',
        'range': (0, 360),
        'ticks': [0, 90, 180, 270, 360],
        'tick_labels': ['0°\n(Right)', '90°\n(Fwd)', '180°\n(Left)', '270°\n(Back)', '360°\n(Right)'],
        'title_suffix': '(Original Coordinates)',
    },
    'rotation_forward': {
        'label': 'Figure Rotation (°)',
        'range': (0, 360),
        'ticks': [0, 90, 180, 270, 360],
        'tick_labels': ['0°\n(Fwd)', '90°\n(Right)', '180°\n(Back)', '270°\n(Left)', '360°\n(Fwd)'],
        'title_suffix': '(0°=Forward)',
    },
    'rotation_egocentric': {
        'label': 'Figure Rotation (°)',
        'range': (-90, 270),
        'ticks': [-90, 0, 90, 180, 270],
        'tick_labels': ['-90°\n(Left)', '0°\n(Fwd)', '90°\n(Right)', '180°\n(Back)', '270°\n(Left)'],
        'title_suffix': '(Egocentric: 0°=Forward)',
    },
}


def bin_rotation_data(df_subset, rotation_col, n_bins=12, print_counts=True, label=""):
    """
    Bin rotation data for smoother visualization.

    Args:
        df_subset: DataFrame to bin
        rotation_col: Name of the rotation column to use
        n_bins: Number of bins
        print_counts: Whether to print sample counts per bin
        label: Optional label for the print output

    Returns:
        DataFrame with rotation_bin_center column added, bin_centers, and bin_counts
    """
    df_copy = df_subset.copy()
    settings = ROTATION_SETTINGS[rotation_col]
    min_val, max_val = settings['range']

    bin_edges = np.linspace(min_val, max_val, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    df_copy['rotation_bin'] = pd.cut(
        df_copy[rotation_col],
        bins=bin_edges,
        labels=False,
        include_lowest=True
    )
    df_copy['rotation_bin_center'] = df_copy['rotation_bin'].map(
        lambda x: bin_centers[int(x)] if pd.notna(x) else np.nan
    )

    # Count samples per bin
    bin_counts = df_copy.groupby('rotation_bin').size()

    if print_counts:
        header = f"Samples per rotation bin ({label})" if label else "Samples per rotation bin"
        print(f"\n{header} (n_bins={n_bins}):")
        for i, center in enumerate(bin_centers):
            count = bin_counts.get(i, 0)
            edge_low = bin_edges[i]
            edge_high = bin_edges[i + 1]
            print(f"  Bin {i:2d}: [{edge_low:6.1f}°, {edge_high:6.1f}°) center={center:6.1f}° → n={count}")
        print(f"  Total: {bin_counts.sum()}")

    return df_copy, bin_centers


def setup_rotation_axis(ax, rotation_col, include_chance=True, chance_level=0.5):
    """Configure axis settings for rotation plots."""
    settings = ROTATION_SETTINGS[rotation_col]
    ax.set_xlim(settings['range'])
    ax.set_ylim(0, 1)
    ax.set_xticks(settings['ticks'])
    if settings['tick_labels']:
        ax.set_xticklabels(settings['tick_labels'])
    ax.grid(True, alpha=0.3)
    if include_chance:
        ax.axhline(y=chance_level, color='gray', linestyle='--', alpha=0.5)


# ===========================================
# Plot 4: Test rotation plots
# ===========================================

# Create consistent color mapping for all plots
model_colors = {model: color for model, color in zip(df['model'].cat.categories, sns.color_palette("tab20"))}

n_bins_test = 6
rotation_col = ROTATION_COLUMN
rot_settings = ROTATION_SETTINGS[rotation_col]

# Filter to test conditions only (where rotation matters for perspective-taking)
df_test = df[df['stimulus_set'].isin(['level_1', 'level_2', 'level_3'])].copy()
df_test, _ = bin_rotation_data(df_test, rotation_col, n_bins_test, label="Test conditions")

# Aggregate
rotation_agg = df_test.groupby(
                    ['rotation_bin_center', 'model', 'stimulus_set']
)['accuracy'].agg(['mean', 'sem', 'count']).reset_index()
rotation_agg.columns = ['rotation', 'model', 'stimulus_set', 'accuracy', 'sem', 'n']

# Plot: Accuracy vs Angular Disparity by Condition
fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
test_conditions = ['level_1', 'level_2', 'level_3']
test_titles = ['Test 1: Visibility (L1 VPT)', 'Test 2: Appearance (L2 VPT)', 'Test 3: Integrated (L2 VPT)']

for ax, cond, title in zip(axes, test_conditions, test_titles):
    subset = rotation_agg[rotation_agg['stimulus_set'] == cond]
    for model in df['model'].cat.categories:
        model_data = subset[subset['model'] == model]
        if len(model_data) > 0:
            ax.errorbar(
                model_data['rotation'], model_data['accuracy'],
                yerr=model_data['sem'],
                marker='o', linewidth=2, markersize=5, label=model,
                capsize=3, color=model_colors[model]
            )

    chance_level = 0.25 if cond == 'level_3' else 0.5
    setup_rotation_axis(ax, rotation_col, include_chance=True, chance_level=chance_level)
    ax.set_xlabel(rot_settings['label'], fontsize=14,labelpad=15)
    ax.set_title(title, fontsize=16)

axes[0].set_ylabel('Mean Accuracy', fontsize=14)
axes[2].legend(title='Subject', bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=12)

# plt.suptitle(f'Accuracy vs Angular Disparity {rot_settings["title_suffix"]}', fontsize=13, y=1.02)
plt.tight_layout()
plt.savefig(
    os.path.join(plot_dir, f"Test Accuracy by Figure Rotation.png"),
    dpi=300,
    bbox_inches="tight"
)
plt.show()


# ===========================================
# Plot 4: Control task Figure Rotation plots
# ===========================================

n_bins_control = 24

# Filter to control 2 only, excluding humans (no control trials)
df_control = df[(df['stimulus_set'] == 'control_2') & (df['model'] != 'human')].copy()
df_control['model'] = df_control['model'].cat.remove_unused_categories()
df_control, _ = bin_rotation_data(df_control, rotation_col, n_bins_control, label="Control 2")

rotation_agg_control_full = df_control.groupby(
    ['rotation_bin_center', 'model', 'stimulus_set', 'question_type']
)['accuracy'].agg(['mean', 'sem']).reset_index()
rotation_agg_control_full.columns = ['rotation', 'model', 'stimulus_set', 'question_type', 'accuracy', 'sem']

fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)

for col, q_type in enumerate(['visual', 'spatial']):
    ax = axes[col]
    subset = rotation_agg_control_full[
        (rotation_agg_control_full['stimulus_set'] == 'control_2') &
        (rotation_agg_control_full['question_type'] == q_type)
    ]
    for model in df_control['model'].cat.categories:
        model_data = subset[subset['model'] == model]
        if len(model_data) > 0:
            ax.errorbar(
                model_data['rotation'], model_data['accuracy'],
                yerr=model_data['sem'],
                marker='o', linewidth=2, markersize=4, label=model,
                capsize=2, color=model_colors[model]
            )

    setup_rotation_axis(ax, rotation_col, include_chance=True, chance_level=0.25)
    ax.set_xticks(np.arange(rot_settings['range'][0], rot_settings['range'][1] + 1, 90))
    ax.set_title(f'{q_type.capitalize()} Questions', fontsize=16)
    ax.set_xlabel(rot_settings['label'], fontsize=14)

axes[0].set_ylabel('Mean Accuracy', fontsize=14)

# Add legend outside right of last plot
axes[1].legend(title='Subject', bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=14)

# plt.suptitle(f'Control 2: Accuracy by Figure Rotation and Question Type', fontsize=13, y=1.02)
plt.tight_layout()
plt.savefig(
    os.path.join(plot_dir, f"Control 2 Accuracy by Figure Rotation.png"),
    dpi=300,
    bbox_inches="tight"
)
plt.show()


# ===========================================
# Plot 4b: Control task Figure Rotation - Combined (visual + spatial)
# ===========================================

# Aggregate across both question types
rotation_agg_control_combined = df_control.groupby(
    ['rotation_bin_center', 'model', 'stimulus_set']
)['accuracy'].agg(['mean', 'sem']).reset_index()
rotation_agg_control_combined.columns = ['rotation', 'model', 'stimulus_set', 'accuracy', 'sem']

fig, ax = plt.subplots(figsize=(8, 6))

subset = rotation_agg_control_combined[rotation_agg_control_combined['stimulus_set'] == 'control_2']
for model in df_control['model'].cat.categories:
    model_data = subset[subset['model'] == model]
    if len(model_data) > 0:
        ax.errorbar(
            model_data['rotation'], model_data['accuracy'],
            yerr=model_data['sem'],
            marker='o', linewidth=2, markersize=4, label=model,
            capsize=2, color=model_colors[model]
        )

setup_rotation_axis(ax, rotation_col, include_chance=True, chance_level=0.25)
ax.set_xticks(np.arange(rot_settings['range'][0], rot_settings['range'][1] + 1, 90))
ax.set_title('Control 2: Accuracy by Figure Rotation', fontsize=14)
ax.set_xlabel(rot_settings['label'], fontsize=12)
ax.set_ylabel('Mean Accuracy', fontsize=12)
ax.legend(title='Subject', bbox_to_anchor=(1.02, 1), loc='upper left')

plt.tight_layout()
plt.savefig(
    os.path.join(plot_dir, f"Control 2 Accuracy by Figure Rotation (Combined).png"),
    dpi=300,
    bbox_inches="tight"
)
plt.show()


# ===========================================
# Plot 5: Angular Disparity - Detailed by Condition × Question Type (Test 1 & 2 only)
# ===========================================

rotation_agg_full = df_test.groupby(
    ['rotation_bin_center', 'model', 'stimulus_set', 'question_type']
)['accuracy'].agg(['mean', 'sem']).reset_index()
rotation_agg_full.columns = ['rotation', 'model', 'stimulus_set', 'question_type', 'accuracy', 'sem']

# Only Test 1 and Test 2 (excluding Test 3)
test_conditions_12 = ['level_1', 'level_2']
test_titles_12 = ['Test 1: Visibility (L1 VPT)', 'Test 2: Appearance (L2 VPT)']

fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharey=True)

for row, (cond, cond_title) in enumerate(zip(test_conditions_12, test_titles_12)):
    for col, q_type in enumerate(['visual', 'spatial']):
        ax = axes[row, col]
        subset = rotation_agg_full[
            (rotation_agg_full['stimulus_set'] == cond) &
            (rotation_agg_full['question_type'] == q_type)
        ]
        for model in df['model'].cat.categories:
            model_data = subset[subset['model'] == model]
            if len(model_data) > 0:
                ax.errorbar(
                    model_data['rotation'], model_data['accuracy'],
                    yerr=model_data['sem'],
                    marker='o', linewidth=2, markersize=4, label=model,
                    capsize=2, color=model_colors[model]
                )

        setup_rotation_axis(ax, rotation_col, include_chance=True, chance_level=0.5)
        ax.set_xticks(np.arange(rot_settings['range'][0], rot_settings['range'][1] + 1, 90))

        if row == 0:
            col_title = 'Visual Questions' if q_type == 'visual' else 'Spatial Questions'
            ax.set_title(col_title, fontsize=14)
        if col == 0:
            ax.set_ylabel(f'{cond_title.split(":")[0]}\nMean Accuracy', fontsize=12)
        if row == 1:
            ax.set_xlabel(rot_settings['label'], fontsize=12)

# Add legend to last plot
axes[0, 1].legend(title='Subject', bbox_to_anchor=(1.02, 1), loc='upper left')

# plt.suptitle(f'Accuracy by Angular Disparity, Condition, and Question Type {rot_settings["title_suffix"]}', fontsize=13, y=1.01)
plt.tight_layout()
plt.savefig(
    os.path.join(plot_dir, f"Test Accuracy by Figure Rotation and Question Type.png"),
    dpi=300,
    bbox_inches="tight"
)
plt.show()


# ===========================================
# Plot 6: L1 vs L2 VPT Comparison (Test conditions only)
# ===========================================

df_test_vpt = df_test.copy()
df_test_vpt['vpt_level'] = df_test_vpt['stimulus_set'].apply(get_vpt_level)

subset = df_test_vpt.copy()
subset['combined'] = (
    subset['vpt_level'] + '\n' +
    subset['question_type_label']
)

combined_order = [
    "Level 1\nVisual",
    "Level 1\nSpatial",
    "Level 2\nVisual",
    "Level 2\nSpatial",
    "Level 2\nVisuospatial",  # Test 3 only
]

fig, ax = plt.subplots(figsize=(12, 6))
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
ax.set_ylabel('Mean Accuracy', fontsize=12)
ax.set_xlabel('VPT Level × Question Type', fontsize=12)
ax.legend(title='Subject', bbox_to_anchor=(1.02, 1), loc='upper left')

title = "Mean Accuracy by VPT Level and Question Type"
plt.tight_layout()
plt.savefig(
    os.path.join(plot_dir, f"{title}.png"),
    dpi=300,
    bbox_inches="tight"
)
plt.show()

# ===========================================
# Error Analysis
# ===========================================

def analyze_errors(df, model_name, condition, condition_label):
    """Analyze error patterns for a specific model and condition."""
    subset = df[(df['model'] == model_name) & (df['stimulus_set'] == condition)]
    errors = subset[subset['accuracy'] == 0]
    correct = subset[subset['accuracy'] == 1]

    n_total = len(subset)
    n_errors = len(errors)
    n_correct = len(correct)

    print(f"\n{'='*60}")
    print(f"ERROR ANALYSIS: {model_name} on {condition_label}")
    print(f"{'='*60}")
    print(f"Total trials: {n_total}, Correct: {n_correct}, Errors: {n_errors} ({100*n_errors/n_total:.1f}%)")

    if n_errors == 0:
        print("No errors to analyze!")
        return None

    # 1. Error rate by figure rotation (binned)
    print(f"\n--- Error Rate by Figure Rotation ---")
    subset_copy = subset.copy()
    subset_copy['rotation_bin'] = pd.cut(subset_copy['figure_rotation'], bins=8, labels=False)
    bin_edges = np.linspace(0, 360, 9)
    bin_labels = [f"{int(bin_edges[i])}-{int(bin_edges[i+1])}°" for i in range(8)]
    rotation_errors = subset_copy.groupby('rotation_bin')['accuracy'].agg(['mean', 'count'])
    rotation_errors.index = [bin_labels[i] for i in rotation_errors.index]
    rotation_errors['error_rate'] = 1 - rotation_errors['mean']
    print(rotation_errors[['count', 'error_rate']].round(3))

    # 2. Error rate by figure type
    if 'figure_type' in subset.columns:
        print(f"\n--- Error Rate by Figure Type ---")
        fig_errors = subset.groupby('figure_type')['accuracy'].agg(['mean', 'count'])
        fig_errors['error_rate'] = 1 - fig_errors['mean']
        print(fig_errors[['count', 'error_rate']].sort_values('error_rate', ascending=False).round(3))

    # 3. Error rate by relative location
    if 'relative_location' in subset.columns:
        print(f"\n--- Error Rate by Relative Location ---")
        loc_errors = subset.groupby('relative_location')['accuracy'].agg(['mean', 'count'])
        loc_errors['error_rate'] = 1 - loc_errors['mean']
        print(loc_errors[['count', 'error_rate']].sort_values('error_rate', ascending=False).round(3))

    # 4. Error rate by question type
    if 'question_type' in subset.columns:
        print(f"\n--- Error Rate by Question Type ---")
        qt_errors = subset.groupby('question_type')['accuracy'].agg(['mean', 'count'])
        qt_errors['error_rate'] = 1 - qt_errors['mean']
        print(qt_errors[['count', 'error_rate']].round(3))

    # 5. Error rate by target
    if 'number_appearance' in subset.columns:
        print(f"\n--- Error Rate by Target Type ---")
        app_errors = subset.groupby('target')['accuracy'].agg(['mean', 'count'])
        app_errors['error_rate'] = 1 - app_errors['mean']
        print(app_errors[['count', 'error_rate']].sort_values('error_rate', ascending=False).round(3))

    # 6. Confusion analysis - what does the model answer when wrong?
    print(f"\n--- Confusion Analysis (Error Trials Only) ---")
    print("Target → Model Answer:")
    confusion = pd.crosstab(errors['target_clean'], errors['model_answer_clean'], margins=True)
    print(confusion)

    # 6. List specific error trials
    print(f"\n--- Error Trial Details (first 10) ---")
    error_cols = ['sample_id', 'figure_type', 'figure_rotation', 'relative_location',
                  'question_type', 'target', 'model_answer']
    error_cols = [c for c in error_cols if c in errors.columns]
    print(errors[error_cols].head(10).to_string())

    # 7. Invalid responses (responses not matching any valid target)
    invalid = subset[subset['is_invalid_response'] == 1]
    n_invalid = len(invalid)
    print(f"\n--- Invalid Responses ---")
    print(f"Invalid responses: {n_invalid} ({100*n_invalid/n_total:.1f}% of trials)")
    if n_invalid > 0:
        print("\nSample invalid responses (truncated to 100 chars):")
        for i, (_, row) in enumerate(invalid.head(5).iterrows()):
            ans = str(row['model_answer']) if pd.notna(row['model_answer']) else "<empty>"
            truncated = ans[:100] + "..." if len(ans) > 100 else ans
            print(f"  [{row['sample_id']}] Target: {row['target']} → Got: {truncated}")

    return errors

# Analyze o3 errors on Test 1 (Visibility)
errors_o3_test1 = analyze_errors(df, 'o3', 'level_1', 'Test 1: Visibility (L1 VPT)')

# Analyze o3 errors on Test 2 (Appearance)
errors_o3_test2 = analyze_errors(df, 'o3', 'level_2', 'Test 2: Appearance (L2 VPT)')

# Analyze o3 errors on Test 3 (Integrated)
errors_o3_test3 = analyze_errors(df, 'o3', 'level_3', 'Test 3: Integrated (L2 VPT)')


# ===========================================
# Invalid Response Analysis
# ===========================================

print("\n" + "="*60)
print("INVALID RESPONSE ANALYSIS")
print("="*60)

print(f"\nValid responses: {sorted(valid_responses)}")

# Overall invalid response rate
total_invalid = df['is_invalid_response'].sum()
total_trials = len(df)
print(f"\nOverall: {total_invalid} invalid responses out of {total_trials} trials ({100*total_invalid/total_trials:.2f}%)")

# Invalid response rate by model
print("\n--- Invalid Response Rate by Model ---")
invalid_by_model = df.groupby('model')['is_invalid_response'].agg(['sum', 'count', 'mean'])
invalid_by_model.columns = ['n_invalid', 'n_total', 'invalid_rate']
invalid_by_model['invalid_rate'] = (invalid_by_model['invalid_rate'] * 100).round(2)
print(invalid_by_model)

# Invalid response rate by model and condition
print("\n--- Invalid Response Rate by Model and Condition ---")
invalid_by_model_cond = df.groupby(['model', 'stimulus_set'])['is_invalid_response'].mean().unstack() * 100
print(invalid_by_model_cond.round(2))

# Show examples of invalid responses
print("\n--- Examples of Invalid Responses ---")
invalid_df = df[df['is_invalid_response'] == 1]
if len(invalid_df) > 0:
    # Group by model and show unique invalid responses
    for model in df['model'].cat.categories:
        model_invalid = invalid_df[invalid_df['model'] == model]
        if len(model_invalid) > 0:
            print(f"\n{model} ({len(model_invalid)} invalid):")
            # Show unique invalid answers (truncated)
            unique_invalid = model_invalid['model_answer'].unique()[:5]
            for ans in unique_invalid:
                ans = str(ans)
                truncated = ans[:80] + "..." if len(ans) > 80 else ans
                print(f"  - {truncated}")
else:
    print("No invalid responses found!")

# Plot: Invalid response rate by model and condition
fig, ax = plt.subplots(figsize=(10, 6))
invalid_pivot = df.groupby(['stimulus_set', 'model'])['is_invalid_response'].mean().unstack() * 100

invalid_pivot.plot(kind='bar', ax=ax, width=0.8)
ax.set_ylabel('Invalid Response Rate (%)', fontsize=12)
ax.set_xlabel('Condition', fontsize=12)
ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
ax.legend(title='Subject', bbox_to_anchor=(1.02, 1), loc='upper left')
ax.set_ylim(0, max(10, invalid_pivot.max().max() * 1.2))  # Scale y-axis appropriately

plt.title('Invalid Response Rate by Condition and Model')
plt.tight_layout()
plt.savefig(
    os.path.join(plot_dir, "Invalid Response Rate.png"),
    dpi=300,
    bbox_inches="tight"
)
plt.show()






# ===========================================
# Summary Statistics
# ===========================================

print("\n" + "="*60)
print("SUMMARY STATISTICS")
print("="*60)

# Overall accuracy by condition
print("\nAccuracy by Condition:")
print(df.groupby('stimulus_set')['accuracy'].agg(['mean', 'std', 'count']).round(3))

# Accuracy by model and condition
print("\nAccuracy by Model and Condition:")
summary = df.groupby(['model', 'stimulus_set'])['accuracy'].mean().unstack()
print(summary.round(3))

# Accuracy by VPT level
print("\nAccuracy by VPT Level:")
print(df.groupby('vpt_level')['accuracy'].agg(['mean', 'std', 'count']).round(3))

print("\nAnalysis complete. Plots saved to:", plot_dir)
