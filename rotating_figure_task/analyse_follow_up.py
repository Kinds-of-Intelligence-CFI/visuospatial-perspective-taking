"""
Follow-up analysis: M/W/E/3 rotation task (E3).

Loads vpt_follow_up.csv and produces:
  1. Accuracy by figure rotation  — single combined plot matching the format
     used in analyse_combined_results.py (all models on one axis, egocentric
     rotation convention, n_bins bins, error bars).
  2. Net rotation polar plot  — 2×2 polar histogram per model showing
     net_rotation = (home_angle[answer] - number_rotation) mod 360.
     Values near 0° indicate the model named the glyph currently shown
     upright (viewer-perspective heuristic).
  3. Heuristic strategy plot  — 2×2 panel per model showing the proportion
     of each rotation-bucket response (upright / left / flipped / right)
     vs figure rotation.

Run from the repo root:
    python rotating_figure_task/analyse_follow_up.py
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import seaborn as sns

# Progress messages contain degree/arrow glyphs; force UTF-8 so they don't
# crash on Windows consoles using a legacy (cp1252) code page.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "rotating_figure_task", "results")
PLOT_DIR    = os.path.join(ROOT, "rotating_figure_task", "plots")
os.makedirs(PLOT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Load & preprocess
# ---------------------------------------------------------------------------
df = pd.read_csv(os.path.join(RESULTS_DIR, "vpt_follow_up.csv"))

df["model"]       = df["model"].str.split("/").str[-1]
df["answer_norm"] = df["model_answer"].astype(str).str.strip().str.lower()
df["target_norm"] = df["target"].astype(str).str.strip().str.lower()
df["accuracy"]    = (df["answer_norm"] == df["target_norm"]).astype(int)

# Rotation conventions (matching analyse_combined_results.py)
df["rotation_forward"]    = (90 - df["figure_rotation"]) % 360
df["rotation_egocentric"] = df["rotation_forward"].apply(
    lambda x: x - 360 if x > 270 else x
)
df["angular_disparity"] = df["rotation_forward"].apply(
    lambda r: 360 - r if r > 180 else r
)

# Use the same model order and colours as the main analysis script so plots
# are visually consistent across the paper.
MAIN_MODEL_ORDER = ["o3", "o4-mini", "gpt-4o", "gpt-4o-mini"]
MODEL_COLORS     = {m: c for m, c in zip(MAIN_MODEL_ORDER, sns.color_palette("tab20"))}

df["model"] = pd.Categorical(df["model"], categories=MAIN_MODEL_ORDER, ordered=True)

print(f"Loaded {len(df)} rows, {df['model'].nunique()} models")
print(df.groupby(["model", "target_norm"], observed=True)["accuracy"]
        .agg(["mean", "count"]).round(3))

# ---------------------------------------------------------------------------
# Shared rotation-axis settings (mirrors ROTATION_SETTINGS in the main script)
# ---------------------------------------------------------------------------
ROT_RANGE      = (-90, 270)
ROT_TICKS      = [-90, 0, 90, 180, 270]
ROT_TICKLABELS = ["-90°\n(Left)", "0°\n(Fwd)", "90°\n(Right)", "180°\n(Back)", "270°\n(Left)"]
ROT_LABEL      = "Figure Rotation (°)"

N_BINS         = 6  # 30° per bin; matches resolution used in main script for test conditions
BIN_EDGES      = np.linspace(*ROT_RANGE, N_BINS + 1)
BIN_CENTERS    = (BIN_EDGES[:-1] + BIN_EDGES[1:]) / 2

df["rot_bin_idx"] = pd.cut(
    df["rotation_egocentric"], bins=BIN_EDGES, labels=False, include_lowest=True
)
df["rot_bin_center"] = df["rot_bin_idx"].map(
    {i: BIN_CENTERS[int(i)] for i in range(N_BINS)}
)

# ---------------------------------------------------------------------------
# Plot 1: Accuracy by figure rotation — combined, all models on one axis
# ---------------------------------------------------------------------------
acc_agg = (
    df.groupby(["model", "rot_bin_center"], observed=True)["accuracy"]
    .agg(["mean", "sem", "count"])
    .reset_index()
    .rename(columns={"mean": "accuracy", "sem": "se"})
)

fig, ax = plt.subplots(figsize=(8, 5))

for model in MAIN_MODEL_ORDER:
    sub = acc_agg[acc_agg["model"] == model]
    if sub.empty:
        continue
    ax.errorbar(
        sub["rot_bin_center"], sub["accuracy"],
        yerr=sub["se"],
        marker="o", linewidth=2, markersize=5,
        capsize=3, label=model, color=MODEL_COLORS[model],
    )

ax.axhline(y=0.25, color="gray", linestyle="--", alpha=0.5, linewidth=1)
ax.set_xlim(ROT_RANGE)
ax.set_ylim(0, 1)
ax.set_xticks(ROT_TICKS)
ax.set_xticklabels(ROT_TICKLABELS)
ax.grid(True, alpha=0.3)
ax.set_xlabel(ROT_LABEL, fontsize=14, labelpad=15)
ax.set_ylabel("Mean Accuracy", fontsize=14)
ax.legend(title="Model", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=12)

plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "follow_up_accuracy_by_rotation_e3.png"),
            dpi=300, bbox_inches="tight")
plt.close()
print("Saved: follow_up_accuracy_by_rotation_e3.png")

# ---------------------------------------------------------------------------
# Plot 2: Net rotation polar plot
# net_rotation = (home_angle[answer] - number_rotation) mod 360
# home angles: m=0, e=90, w=180, 3=270
# A model responding to the visually upright glyph lands near 0°.
# ---------------------------------------------------------------------------
ANSWER_ANGLE_MAP  = {"m": 0, "e": 90, "w": 180, "3": 270}
CANONICAL_GLYPHS  = set(ANSWER_ANGLE_MAP)

df_radial = df[df["answer_norm"].isin(CANONICAL_GLYPHS)].copy()
df_radial["net_rotation"] = (
    df_radial["answer_norm"].map(ANSWER_ANGLE_MAP) - df_radial["number_rotation"]
) % 360

n_dropped = len(df) - len(df_radial)
print(f"\nNet rotation: {n_dropped} rows dropped (answer not in canonical set)")
print(f"Per-model rows kept: {df_radial.groupby('model', observed=True).size().to_dict()}")

N_POLAR_BINS      = 36
polar_edges       = np.linspace(0, 360, N_POLAR_BINS + 1)
polar_bin_centers = np.deg2rad((polar_edges[:-1] + polar_edges[1:]) / 2)
polar_bin_width   = np.deg2rad(360.0 / N_POLAR_BINS)

# Two groups, each with two overlaid models using tab20 dark/light pairs
tab20 = sns.color_palette("tab20")
POLAR_GROUPS = [
    ("o3 & o4-mini",         [("o3",      tab20[0]), ("o4-mini",      tab20[1])]),
    ("GPT-4o & GPT-4o-mini", [("gpt-4o",  tab20[2]), ("gpt-4o-mini",  tab20[3])]),
]

# Pre-compute per-model proportions; find shared y_max across all
model_props = {}
y_max = 0.0
for model in MAIN_MODEL_ORDER:
    grp = df_radial[df_radial["model"] == model]
    vals = grp["net_rotation"].dropna().to_numpy()
    counts, _ = np.histogram(vals, bins=polar_edges)
    props = counts / counts.sum() if counts.sum() > 0 else np.zeros(N_POLAR_BINS)
    model_props[model] = (props, len(grp))
    y_max = max(y_max, props.max())

fig, axes = plt.subplots(
    2, 1, figsize=(4.5, 8),
    subplot_kw={"projection": "polar"},
)

for ax, (group_label, model_specs) in zip(axes, POLAR_GROUPS):
    for model_name, color in model_specs:
        props, n_values = model_props[model_name]
        ax.bar(
            polar_bin_centers, props,
            width=polar_bin_width,
            align="center",
            color=color,
            edgecolor="none",
            alpha=0.6,
            label=f"{model_name} (n={n_values})",
        )
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_xticks(np.deg2rad([0, 90, 180, 270]))
    ax.set_xticklabels(["0°\n(upright)", "90°", "180°\n(flipped)", "270°"], fontsize=10)
    ax.set_ylim(0, y_max * 1.08)
    ax.set_yticklabels([])
    ax.set_title(group_label, pad=14, fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.15),
              fontsize=9, framealpha=0.8)

plt.tight_layout(h_pad=2.5)
plt.savefig(os.path.join(PLOT_DIR, "follow_up_net_rotation_e3.png"),
            dpi=300, bbox_inches="tight")
plt.close()
print("Saved: follow_up_net_rotation_e3.png")

# Quick wedge summary (mirrors the notebook's diagnostic print)
print("\nNet rotation — proportion in each 90° wedge:")
for model in MAIN_MODEL_ORDER:
    grp = df_radial[df_radial["model"] == model]
    wedge = (((grp["net_rotation"] + 45) // 90) % 4).astype(int) * 90
    frac  = wedge.value_counts().reindex([0, 90, 180, 270], fill_value=0) / len(grp)
    print(f"  {model:12s}  ~0°: {frac[0]:.2f}  ~90°: {frac[90]:.2f}  "
          f"~180°: {frac[180]:.2f}  ~270°: {frac[270]:.2f}")

# ---------------------------------------------------------------------------
# Plot 3: Heuristic strategy — rotation buckets by figure rotation, per model
# ---------------------------------------------------------------------------
# Classify responses relative to what the VIEWER sees (the displayed glyph).
# ANSWER_ANGLE_MAP uses CCW-positive convention (m=0, e=90 CCW, w=180, 3=270 CW),
# so in the task's convention: CCW = left, CW = right.
#   net ~  0°: upright — model names the glyph as it appears to the viewer
#   net ~ 90°: left    — 90° CCW from displayed (left rotation in task convention)
#   net ~180°: flipped — 180° flip of displayed
#   net ~270°: right   — 90° CW from displayed (right rotation in task convention)
def viewer_bucket(answer, number_rotation):
    if answer not in ANSWER_ANGLE_MAP:
        return "other"
    net = (ANSWER_ANGLE_MAP[answer] - float(number_rotation)) % 360
    if net < 45 or net >= 315:
        return "upright"
    if net < 135:
        return "left"
    if net < 225:
        return "flipped"
    return "right"

df["bucket"] = [
    viewer_bucket(a, nr)
    for a, nr in zip(df["answer_norm"], df["number_rotation"])
]

BUCKET_ORDER  = ["upright", "flipped", "left", "right", "other"]
BUCKET_COLORS = {
    "upright": "black",
    "flipped": "tab:red",
    "left":    "tab:blue",
    "right":   "tab:green",
    "other":   "gray",
}
BUCKET_LABELS = {
    "upright": "As displayed (viewer upright)",
    "flipped": "180° flip",
    "left":    "90° left",
    "right":   "90° right",
    "other":   "Other",
}

# Strategies on y-axis, rotation on x-axis, colour = proportion.
# 4 cardinal bins centred at -90°(left), 0°(fwd), 90°(right), 180°(back).
# Values in [225, 270] wrap around to the -90° bin.
HMAP_ORDER   = ["flipped", "left", "upright", "right"]
HMAP_LABELS  = ["180°", "-90°", "0°", "90°"]
CARD_EDGES   = np.array([-135., -45., 45., 135., 225.])
CARD_CENTERS = np.array([-90., 0., 90., 180.])
CARD_LABELS  = ["Left\n(-90°)", "Fwd\n(0°)", "Right\n(90°)", "Back\n(180°)"]

df_hmap = df.copy()
df_hmap["rot_card"] = df_hmap["rotation_egocentric"].apply(
    lambda r: r - 360 if r >= 225 else r
)
df_hmap["card_bin"] = pd.cut(
    df_hmap["rot_card"], bins=CARD_EDGES,
    labels=CARD_CENTERS, include_lowest=True,
).astype(float)

hmap_mats = {}
vmax_hmap = 0.0
for model in MAIN_MODEL_ORDER:
    sub = df_hmap[df_hmap["model"] == model]
    bc = (
        sub.groupby(["card_bin", "bucket"], observed=True)
        .size().unstack(fill_value=0)
    )
    bc = bc.reindex(index=CARD_CENTERS, fill_value=0)
    bc = bc.reindex(columns=HMAP_ORDER, fill_value=0)
    bp = bc.div(bc.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    mat = bp[HMAP_ORDER].values.T   # shape: (4 strategies, 4 rotations)
    hmap_mats[model] = mat
    vmax_hmap = max(vmax_hmap, mat.max())

fig, axes = plt.subplots(2, 2, figsize=(8, 7), sharex=True, sharey=True,
                         constrained_layout=True)
axes_flat = axes.flatten()

y_edges = np.arange(len(HMAP_ORDER) + 1) - 0.5
im = None
for ax, model in zip(axes_flat, MAIN_MODEL_ORDER):
    im = ax.pcolormesh(
        CARD_EDGES, y_edges, hmap_mats[model],
        cmap="Blues", vmin=0, vmax=vmax_hmap,
    )
    ax.set_yticks(range(len(HMAP_ORDER)))
    ax.set_yticklabels(HMAP_LABELS, fontsize=16)
    ax.set_xticks(CARD_CENTERS)
    ax.set_xticklabels(CARD_LABELS, fontsize=16)
    ax.set_xlim(CARD_EDGES[0], CARD_EDGES[-1])
    ax.set_title(model, fontsize=16)
    # Bold border on each diagonal cell (correct response strategy)
    for col_i, row_i in enumerate([3, 2, 1, 0]):
        rect = mpatches.Rectangle(
            (CARD_EDGES[col_i], row_i - 0.5),
            CARD_EDGES[col_i + 1] - CARD_EDGES[col_i], 1.0,
            linewidth=1.5, edgecolor="black", facecolor="none",
        )
        ax.add_patch(rect)

fig.supxlabel("Figure facing direction", fontsize=18)
fig.supylabel("Response strategy", fontsize=18)

cbar = fig.colorbar(im, ax=axes_flat.tolist(), pad=0.02)
cbar.ax.tick_params(labelsize=16)
cbar.set_label("Proportion of responses", fontsize=16)

plt.savefig(os.path.join(PLOT_DIR, "follow_up_heuristic_strategies_e3.png"),
            dpi=300, bbox_inches="tight")
plt.close()
print("Saved: follow_up_heuristic_strategies_e3.png")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\nOverall accuracy by model:")
print(df.groupby("model", observed=True)["accuracy"].agg(["mean", "count"]).round(3))

print("\nBucket breakdown by model (%):")
print(
    df.groupby(["model", "bucket"], observed=True)
    .size()
    .unstack(fill_value=0)
    .reindex(columns=BUCKET_ORDER, fill_value=0)
    .apply(lambda r: r / r.sum() * 100, axis=1)
    .round(1)
)
