"""Render the README radar charts from the official demo's category scores.

Requires matplotlib and numpy. Run this script with --language en or zh.
For Chinese labels, pass --font /path/to/a/CJK/font.ttf if needed.
"""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=["en", "zh"], default="en")
    parser.add_argument("--font", help="Optional CJK font file")
    parser.add_argument("--preview-dir", type=Path, help="Optional PNG preview directory")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    with (root / "seven_category_scores_raw.csv").open(newline="") as stream:
        reader = csv.reader(stream)
        next(reader)
        scores = {row[0]: np.array([float(x) for x in row[1:]]) for row in reader}
    all_scores = np.stack(list(scores.values()))
    low, high = all_scores.min(axis=0), all_scores.max(axis=0)
    baseline = np.max([v for k, v in scores.items() if not k.startswith("Index-")], axis=0)
    chinese = args.language == "zh"
    font = FontProperties(fname=args.font) if args.font else FontProperties(family="DejaVu Sans")
    labels = (["指令遵循", "书籍翻译", "字幕翻译", "社交与文化", "FLORES", "WMT", "小语种翻译"]
              if chinese else ["Instructions", "Books", "Subtitles", "Social & cultural", "FLORES", "WMT", "Low-resource"])
    baseline_name = "非 Index 最优（逐维）" if chinese else "Best non-Index (per category)"
    series = [
        ("Index-Translate-9B", scores["Index-Translate-9B"], "#E45B81", "-", 2.9),
        ("Index-Translate-2B", scores["Index-Translate-2B"], "#3CA5B6", "-", 2.4),
        ("DeepSeek-V4.1-Flash", scores["deepseek_v4.1_flash"], "#6E69BA", "-", 1.8),
        ("GPT-5.6-Sol", scores["gpt-5.6-sol"], "#D49B34", "-", 1.8),
        (baseline_name, baseline, "#6C7785", "--", 1.6),
    ]
    plt.rcParams.update({"font.size": 12, "svg.fonttype": "path", "svg.hashsalt": "index-translate-readme"})
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False)
    closed = np.r_[angles, angles[0]]
    fig = plt.figure(figsize=(10, 7.1), facecolor="white")
    ax = fig.add_axes([.15, .22, .7, .60], polar=True)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 104)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=9, color="#929AA5")
    ax.set_rlabel_position(335)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontproperties=font, fontsize=14, color="#243044")
    ax.tick_params(axis="x", pad=12)
    ax.grid(color="#DFE4EC", linewidth=.8)
    ax.spines["polar"].set_visible(False)
    handles = []
    for name, values, color, style, width in reversed(series):
        scaled = (values - low) / (high - low) * 100
        line, = ax.plot(closed, np.r_[scaled, scaled[0]], color=color, linestyle=style,
                        linewidth=width, marker="o" if name.startswith("Index-") else None,
                        markersize=4, label=name, zorder=4 if name.endswith("9B") else 3)
        if name.startswith("Index-"):
            ax.fill(closed, np.r_[scaled, scaled[0]], color=color, alpha=.055)
        handles.append(line)
    handles.reverse()
    title = "文本翻译能力七维评测" if chinese else "Text Translation Across Seven Categories"
    subtitle = "INDEX-TRANSLATE  /  DEMO BENCHMARK OVERVIEW"
    fig.text(.5, .965, title, ha="center", va="top", fontproperties=font, fontsize=20, color="#16223A")
    fig.text(.5, .908, subtitle, ha="center", fontsize=10, color="#747F8F")
    fig.legend(handles[:4], [h.get_label() for h in handles[:4]], loc="lower center",
               bbox_to_anchor=(.5, .062), ncol=2, frameon=False, fontsize=11, columnspacing=2.2)
    fig.legend(handles[4:], [baseline_name], loc="lower center", bbox_to_anchor=(.5, .017),
               prop=font, frameon=False)
    output = root / f"benchmark-radar.{args.language}.svg"
    fig.savefig(output, facecolor="white", metadata={"Date": None})
    # Matplotlib emits trailing spaces in path data; keep generated files Git-clean.
    output.write_text("\n".join(line.rstrip() for line in output.read_text().splitlines()) + "\n")
    if args.preview_dir:
        args.preview_dir.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.preview_dir / f"benchmark-radar.{args.language}.png", dpi=150, facecolor="white")
    plt.close(fig)
    print(output)


if __name__ == "__main__":
    main()
