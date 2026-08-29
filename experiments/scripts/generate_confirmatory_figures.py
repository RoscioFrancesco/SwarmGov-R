"""Generate report-ready SVG figures and tables from confirmatory summaries."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import sys
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPO_ROOT / "experiments" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from summarize_confirmatory_results import (  # noqa: E402
    CONDITION_SUMMARY_FILE,
    CURVE_SUMMARY_FILE,
    PAIRED_SUMMARY_FILE,
    STATISTICS_SCHEMA_VERSION,
    STATISTICS_SUMMARY_FILE,
)

FIGURE_SCHEMA_VERSION = "confirmatory_figures_v1"
DEFAULT_STATISTICS_DIR = Path("results/processed/confirmatory-m8")
DEFAULT_OUTPUT_DIR = Path("results/figures/confirmatory-m8")

FINAL_REGRET_FIGURE = "final_regret_by_algorithm.svg"
CURVE_FIGURE = "mean_regret_curves.svg"
PAIRED_FIGURE = "paired_regret_differences.svg"
FAIRNESS_FIGURE = "fairness_worst_decile.svg"
COMMUNICATION_FIGURE = "communication_vs_regret.svg"
FINAL_REGRET_TABLE_CSV = "final_regret_table.csv"
PAIRED_TABLE_CSV = "paired_regret_table.csv"
REPORT_TABLES_MD = "report_tables.md"
FIGURE_SUMMARY_JSON = "figure_summary.json"

ALGORITHM_COLOURS = {
    "independent": "#4c78a8",
    "centralized_clean_reference": "#72b7b2",
    "mean": "#f58518",
    "median": "#54a24b",
    "trimmed_mean": "#b279a2",
}
FALLBACK_COLOURS = ("#4c78a8", "#f58518", "#54a24b", "#e45756", "#b279a2")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default=str(DEFAULT_STATISTICS_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing generated figure/table artifacts.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    planned_outputs = _planned_output_paths(output_dir)
    _ensure_can_write(planned_outputs, overwrite=args.overwrite)
    _validate_statistics_summary(input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    condition_rows = _read_csv(input_dir / CONDITION_SUMMARY_FILE)
    curve_rows = _read_csv(input_dir / CURVE_SUMMARY_FILE)
    paired_rows = _read_csv(input_dir / PAIRED_SUMMARY_FILE)

    final_regret_rows = _metric_rows(condition_rows, "mean_per_agent_regret")
    fairness_rows = _metric_rows(condition_rows, "worst_decile_honest_regret")
    communication_rows = _metric_rows(condition_rows, "messages_sent")
    paired_regret_rows = _paired_metric_rows(
        paired_rows,
        "mean_per_agent_regret_difference",
    )
    selected_curve_rows = _select_curve_rows(curve_rows)

    _write_text(
        output_dir / FINAL_REGRET_FIGURE,
        _bar_chart_svg(
            rows=final_regret_rows,
            title="Final Mean Honest-Agent Regret",
            subtitle="Mean with 95% CI across seeds",
            value_label="cumulative regret",
            value_key="mean",
            low_key="ci95_low",
            high_key="ci95_high",
            group_label_key="condition_label",
        ),
    )
    _write_text(
        output_dir / FAIRNESS_FIGURE,
        _bar_chart_svg(
            rows=fairness_rows,
            title="Worst-Decile Honest-Agent Regret",
            subtitle="Fairness summary with 95% CI across seeds",
            value_label="cumulative regret",
            value_key="mean",
            low_key="ci95_low",
            high_key="ci95_high",
            group_label_key="condition_label",
        ),
    )
    _write_text(
        output_dir / PAIRED_FIGURE,
        _bar_chart_svg(
            rows=paired_regret_rows,
            title="Paired Regret Differences",
            subtitle="Target minus baseline; negative means target lower regret",
            value_label="regret difference",
            value_key="mean_difference",
            low_key="ci95_low",
            high_key="ci95_high",
            group_label_key="pair_label",
            zero_line=True,
        ),
    )
    _write_text(
        output_dir / CURVE_FIGURE,
        _line_chart_svg(
            rows=selected_curve_rows,
            title="Mean Regret Curves",
            subtitle=_curve_subtitle(selected_curve_rows),
        ),
    )
    _write_text(
        output_dir / COMMUNICATION_FIGURE,
        _scatter_svg(
            regret_rows=final_regret_rows,
            communication_rows=communication_rows,
            title="Communication Cost Versus Regret",
            subtitle="Condition means; x=messages sent, y=mean regret",
        ),
    )

    final_table = _final_regret_table_rows(final_regret_rows)
    paired_table = _paired_table_rows(paired_regret_rows)
    _write_csv(output_dir / FINAL_REGRET_TABLE_CSV, final_table)
    _write_csv(output_dir / PAIRED_TABLE_CSV, paired_table)
    _write_text(
        output_dir / REPORT_TABLES_MD,
        _report_tables_markdown(final_table, paired_table),
    )

    summary = {
        "schema_version": FIGURE_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "statistics_schema_version": STATISTICS_SCHEMA_VERSION,
        "source_rows": {
            "condition_summary": len(condition_rows),
            "curve_summary": len(curve_rows),
            "paired_summary": len(paired_rows),
        },
        "selected_curve_condition": _curve_condition(selected_curve_rows),
        "outputs": {name: str(path) for name, path in planned_outputs.items()},
        "notes": (
            "Figures are generated from statistical summaries only. Canary or "
            "partial inputs are technical validation artifacts, not final "
            "scientific evidence."
        ),
    }
    _write_json(output_dir / FIGURE_SUMMARY_JSON, summary)

    print("figure_status=completed")
    print(f"final_regret_rows={len(final_regret_rows)}")
    print(f"paired_regret_rows={len(paired_regret_rows)}")
    print(f"curve_rows={len(selected_curve_rows)}")
    print(f"summary={output_dir / FIGURE_SUMMARY_JSON}")
    return 0


def _planned_output_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "final_regret": output_dir / FINAL_REGRET_FIGURE,
        "curves": output_dir / CURVE_FIGURE,
        "paired_differences": output_dir / PAIRED_FIGURE,
        "fairness": output_dir / FAIRNESS_FIGURE,
        "communication": output_dir / COMMUNICATION_FIGURE,
        "final_regret_table": output_dir / FINAL_REGRET_TABLE_CSV,
        "paired_regret_table": output_dir / PAIRED_TABLE_CSV,
        "report_tables": output_dir / REPORT_TABLES_MD,
        "summary": output_dir / FIGURE_SUMMARY_JSON,
    }


def _ensure_can_write(paths: dict[str, Path], *, overwrite: bool) -> None:
    existing = [path for path in paths.values() if path.exists()]
    if existing and not overwrite:
        names = ", ".join(str(path) for path in existing)
        raise FileExistsError(
            "figure/table artifacts already exist; pass --overwrite "
            f"to replace them: {names}"
        )


def _validate_statistics_summary(input_dir: Path) -> None:
    summary_path = input_dir / STATISTICS_SUMMARY_FILE
    if not summary_path.exists():
        raise FileNotFoundError(f"missing statistics summary: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(summary, dict):
        raise ValueError("statistics summary must be a JSON object")
    if summary.get("schema_version") != STATISTICS_SCHEMA_VERSION:
        raise ValueError("unsupported statistics schema version")
    for filename in (CONDITION_SUMMARY_FILE, CURVE_SUMMARY_FILE, PAIRED_SUMMARY_FILE):
        path = input_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"missing statistics table: {path}")


def _metric_rows(rows: list[dict[str, str]], metric: str) -> list[dict[str, str]]:
    selected = [row for row in rows if row.get("metric") == metric]
    for row in selected:
        row["condition_label"] = _condition_label(row)
    return selected


def _paired_metric_rows(
    rows: list[dict[str, str]],
    metric: str,
) -> list[dict[str, str]]:
    selected = [row for row in rows if row.get("metric") == metric]
    for row in selected:
        row["pair_label"] = _pair_label(row)
    return selected


def _select_curve_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    mean_rows = [row for row in rows if row.get("metric") == "mean_regret"]
    if not mean_rows:
        return []
    grouped: dict[tuple[str, str, str, str, str, str, str], list[dict[str, str]]] = (
        defaultdict(list)
    )
    for row in mean_rows:
        key = (
            row.get("group_name", ""),
            row.get("topology", ""),
            row.get("topology_mode", ""),
            row.get("attack_strategy", ""),
            row.get("byzantine_placement", ""),
            row.get("target_arm", ""),
            row.get("inflated_mean", ""),
        )
        grouped[key].append(row)
    preferred = sorted(
        grouped,
        key=lambda key: (
            key[0] != "clean_static_all_topologies",
            key[2] != "static",
            key[1],
            key,
        ),
    )[0]
    return sorted(
        grouped[preferred],
        key=lambda row: (
            row.get("algorithm_label", ""),
            _float_or_none(row.get("round")) or 0.0,
        ),
    )


def _bar_chart_svg(
    *,
    rows: list[dict[str, str]],
    title: str,
    subtitle: str,
    value_label: str,
    value_key: str,
    low_key: str,
    high_key: str,
    group_label_key: str,
    zero_line: bool = False,
) -> str:
    width = 1180
    height = 640
    margin = {"top": 74, "right": 34, "bottom": 170, "left": 88}
    plot_width = width - margin["left"] - margin["right"]
    plot_height = height - margin["top"] - margin["bottom"]
    chart_rows = rows[:24]
    values = [_float_or_none(row.get(value_key)) for row in chart_rows]
    lows = [_float_or_none(row.get(low_key)) for row in chart_rows]
    highs = [_float_or_none(row.get(high_key)) for row in chart_rows]
    numeric = [value for value in (*values, *lows, *highs) if value is not None]
    if not numeric:
        return _empty_svg(title, subtitle, "No rows available for this figure.")
    y_min = min(0.0, min(numeric)) if zero_line else 0.0
    y_max = max(numeric)
    if math.isclose(y_min, y_max):
        y_min -= 1.0
        y_max += 1.0
    padding = (y_max - y_min) * 0.08
    if zero_line:
        y_min -= padding
    y_max += padding

    bar_gap = 8
    bar_width = max(
        12,
        (plot_width - bar_gap * (len(chart_rows) + 1)) / len(chart_rows),
    )
    pieces = [_svg_header(width, height), _title(title, subtitle)]
    pieces.append(_axis_frame(margin, plot_width, plot_height))
    if zero_line and y_min < 0 < y_max:
        y_zero = _scale(0.0, y_min, y_max, margin["top"] + plot_height, margin["top"])
        pieces.append(
            f'<line x1="{margin["left"]}" y1="{y_zero:.2f}" '
            f'x2="{margin["left"] + plot_width}" y2="{y_zero:.2f}" '
            'stroke="#5f6b7a" stroke-width="1" stroke-dasharray="4 4"/>'
        )
    for tick in _ticks(y_min, y_max, 5):
        y = _scale(tick, y_min, y_max, margin["top"] + plot_height, margin["top"])
        pieces.append(
            f'<line x1="{margin["left"] - 6}" y1="{y:.2f}" '
            f'x2="{margin["left"]}" y2="{y:.2f}" stroke="#5f6b7a"/>'
            f'<text x="{margin["left"] - 10}" y="{y + 4:.2f}" '
            'text-anchor="end" class="tick">'
            f"{html.escape(_format_number(tick))}</text>"
        )
    for index, row in enumerate(chart_rows):
        value = values[index]
        if value is None:
            continue
        low = lows[index] if lows[index] is not None else value
        high = highs[index] if highs[index] is not None else value
        x = margin["left"] + bar_gap + index * (bar_width + bar_gap)
        bar_value = max(value, 0.0) if zero_line else value
        y = _scale(
            bar_value,
            y_min,
            y_max,
            margin["top"] + plot_height,
            margin["top"],
        )
        y_base = (
            _scale(0.0, y_min, y_max, margin["top"] + plot_height, margin["top"])
            if zero_line and y_min < 0 < y_max
            else margin["top"] + plot_height
        )
        bar_y = min(y, y_base)
        bar_h = max(1.0, abs(y_base - y))
        colour = _algorithm_colour(row.get("algorithm_label", ""), index)
        err_low = _scale(
            float(low),
            y_min,
            y_max,
            margin["top"] + plot_height,
            margin["top"],
        )
        err_high = _scale(
            float(high),
            y_min,
            y_max,
            margin["top"] + plot_height,
            margin["top"],
        )
        pieces.append(
            f'<rect x="{x:.2f}" y="{bar_y:.2f}" width="{bar_width:.2f}" '
            f'height="{bar_h:.2f}" fill="{colour}" rx="2"/>'
        )
        pieces.append(
            f'<line x1="{x + bar_width / 2:.2f}" y1="{err_low:.2f}" '
            f'x2="{x + bar_width / 2:.2f}" y2="{err_high:.2f}" '
            'stroke="#1f2933" stroke-width="1.3"/>'
        )
        label = row.get(group_label_key) or row.get("algorithm_label", "")
        pieces.append(
            f'<text transform="translate({x + bar_width / 2:.2f},'
            f'{margin["top"] + plot_height + 18}) rotate(58)" '
            'text-anchor="start" class="tick">'
            f"{html.escape(_shorten(label, 42))}</text>"
        )
    pieces.append(
        f'<text x="{margin["left"] + plot_width / 2}" y="{height - 18}" '
        'text-anchor="middle" class="axis-label">condition / algorithm</text>'
    )
    pieces.append(
        f'<text transform="translate(24,{margin["top"] + plot_height / 2}) '
        'rotate(-90)" text-anchor="middle" class="axis-label">'
        f"{html.escape(value_label)}</text>"
    )
    pieces.append("</svg>")
    return "\n".join(pieces)


def _line_chart_svg(
    *,
    rows: list[dict[str, str]],
    title: str,
    subtitle: str,
) -> str:
    width = 1180
    height = 620
    margin = {"top": 74, "right": 210, "bottom": 82, "left": 88}
    plot_width = width - margin["left"] - margin["right"]
    plot_height = height - margin["top"] - margin["bottom"]
    if not rows:
        return _empty_svg(title, subtitle, "No curve rows available.")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("algorithm_label", "unknown")].append(row)
    points_by_algorithm: dict[str, list[tuple[float, float]]] = {}
    all_x: list[float] = []
    all_y: list[float] = []
    for algorithm, group_rows in grouped.items():
        points = []
        for row in sorted(
            group_rows,
            key=lambda item: _float_or_none(item.get("round")) or 0.0,
        ):
            x = _float_or_none(row.get("round"))
            y = _float_or_none(row.get("mean"))
            if x is None or y is None:
                continue
            points.append((x, y))
            all_x.append(x)
            all_y.append(y)
        points_by_algorithm[algorithm] = points
    if not all_x or not all_y:
        return _empty_svg(title, subtitle, "No numeric curve rows available.")

    x_min, x_max = min(all_x), max(all_x)
    y_min, y_max = 0.0, max(all_y)
    if math.isclose(x_min, x_max):
        x_min -= 1.0
        x_max += 1.0
    if math.isclose(y_min, y_max):
        y_max += 1.0
    y_max *= 1.08

    pieces = [_svg_header(width, height), _title(title, subtitle)]
    pieces.append(_axis_frame(margin, plot_width, plot_height))
    for tick in _ticks(y_min, y_max, 5):
        y = _scale(tick, y_min, y_max, margin["top"] + plot_height, margin["top"])
        pieces.append(
            f'<line x1="{margin["left"] - 6}" y1="{y:.2f}" '
            f'x2="{margin["left"]}" y2="{y:.2f}" stroke="#5f6b7a"/>'
            f'<text x="{margin["left"] - 10}" y="{y + 4:.2f}" '
            'text-anchor="end" class="tick">'
            f"{html.escape(_format_number(tick))}</text>"
        )
    for tick in _ticks(x_min, x_max, 5):
        x = _scale(tick, x_min, x_max, margin["left"], margin["left"] + plot_width)
        pieces.append(
            f'<line x1="{x:.2f}" y1="{margin["top"] + plot_height}" '
            f'x2="{x:.2f}" y2="{margin["top"] + plot_height + 6}" '
            'stroke="#5f6b7a"/>'
            f'<text x="{x:.2f}" y="{margin["top"] + plot_height + 24}" '
            'text-anchor="middle" class="tick">'
            f"{html.escape(_format_number(tick))}</text>"
        )
    for index, (algorithm, points) in enumerate(sorted(points_by_algorithm.items())):
        if not points:
            continue
        colour = _algorithm_colour(algorithm, index)
        path_parts = []
        for point_index, (x_value, y_value) in enumerate(points):
            command = "M" if point_index == 0 else "L"
            scaled_x = _scale(
                x_value,
                x_min,
                x_max,
                margin["left"],
                margin["left"] + plot_width,
            )
            scaled_y = _scale(
                y_value,
                y_min,
                y_max,
                margin["top"] + plot_height,
                margin["top"],
            )
            path_parts.append(f"{command}{scaled_x:.2f},{scaled_y:.2f}")
        path = " ".join(path_parts)
        pieces.append(
            f'<path d="{path}" fill="none" stroke="{colour}" stroke-width="2.4"/>'
        )
        legend_y = margin["top"] + 18 + index * 24
        pieces.append(
            f'<rect x="{width - margin["right"] + 30}" y="{legend_y - 10}" '
            f'width="14" height="14" fill="{colour}" rx="2"/>'
            f'<text x="{width - margin["right"] + 52}" y="{legend_y + 2}" '
            'class="tick">'
            f"{html.escape(algorithm)}</text>"
        )
    pieces.append(
        f'<text x="{margin["left"] + plot_width / 2}" y="{height - 24}" '
        'text-anchor="middle" class="axis-label">round</text>'
    )
    pieces.append(
        f'<text transform="translate(24,{margin["top"] + plot_height / 2}) '
        'rotate(-90)" text-anchor="middle" class="axis-label">'
        "mean regret</text>"
    )
    pieces.append("</svg>")
    return "\n".join(pieces)


def _scatter_svg(
    *,
    regret_rows: list[dict[str, str]],
    communication_rows: list[dict[str, str]],
    title: str,
    subtitle: str,
) -> str:
    width = 980
    height = 620
    margin = {"top": 74, "right": 34, "bottom": 92, "left": 88}
    plot_width = width - margin["left"] - margin["right"]
    plot_height = height - margin["top"] - margin["bottom"]
    comm_by_key = {_row_key(row): row for row in communication_rows}
    points = []
    for row in regret_rows:
        comm = comm_by_key.get(_row_key(row))
        if comm is None:
            continue
        x = _float_or_none(comm.get("mean"))
        y = _float_or_none(row.get("mean"))
        if x is None or y is None:
            continue
        points.append((x, y, row))
    if not points:
        return _empty_svg(title, subtitle, "No matching communication/regret rows.")
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    x_min, x_max = min(0.0, min(x_values)), max(x_values)
    y_min, y_max = min(0.0, min(y_values)), max(y_values)
    if math.isclose(x_min, x_max):
        x_max += 1.0
    if math.isclose(y_min, y_max):
        y_max += 1.0
    x_max *= 1.08 if x_max > 0 else 1.0
    y_max *= 1.08 if y_max > 0 else 1.0

    pieces = [_svg_header(width, height), _title(title, subtitle)]
    pieces.append(_axis_frame(margin, plot_width, plot_height))
    for tick in _ticks(x_min, x_max, 5):
        x = _scale(tick, x_min, x_max, margin["left"], margin["left"] + plot_width)
        pieces.append(
            f'<text x="{x:.2f}" y="{margin["top"] + plot_height + 24}" '
            'text-anchor="middle" class="tick">'
            f"{html.escape(_format_number(tick))}</text>"
        )
    for tick in _ticks(y_min, y_max, 5):
        y = _scale(tick, y_min, y_max, margin["top"] + plot_height, margin["top"])
        pieces.append(
            f'<text x="{margin["left"] - 10}" y="{y + 4:.2f}" '
            'text-anchor="end" class="tick">'
            f"{html.escape(_format_number(tick))}</text>"
        )
    for index, (x_value, y_value, row) in enumerate(points):
        x = _scale(x_value, x_min, x_max, margin["left"], margin["left"] + plot_width)
        y = _scale(y_value, y_min, y_max, margin["top"] + plot_height, margin["top"])
        colour = _algorithm_colour(row.get("algorithm_label", ""), index)
        pieces.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="{colour}" '
            'stroke="#1f2933" stroke-width="0.7">'
            f"<title>{html.escape(_condition_label(row))}</title></circle>"
        )
    pieces.append(
        f'<text x="{margin["left"] + plot_width / 2}" y="{height - 24}" '
        'text-anchor="middle" class="axis-label">messages sent</text>'
    )
    pieces.append(
        f'<text transform="translate(24,{margin["top"] + plot_height / 2}) '
        'rotate(-90)" text-anchor="middle" class="axis-label">'
        "mean regret</text>"
    )
    pieces.append("</svg>")
    return "\n".join(pieces)


def _final_regret_table_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        output.append(
            {
                "condition": _condition_label(row),
                "algorithm": row.get("algorithm_label", ""),
                "n": row.get("n", ""),
                "mean_regret": row.get("mean", ""),
                "ci95_low": row.get("ci95_low", ""),
                "ci95_high": row.get("ci95_high", ""),
                "ci_method": row.get("ci_method", ""),
            }
        )
    return output


def _paired_table_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        output.append(
            {
                "comparison": _pair_label(row),
                "n_pairs": row.get("n_pairs", ""),
                "mean_difference": row.get("mean_difference", ""),
                "ci95_low": row.get("ci95_low", ""),
                "ci95_high": row.get("ci95_high", ""),
                "ci_method": row.get("ci_method", ""),
            }
        )
    return output


def _report_tables_markdown(
    final_table: list[dict[str, object]],
    paired_table: list[dict[str, object]],
) -> str:
    return "\n".join(
        [
            "# Confirmatory Result Tables",
            "",
            "Generated from statistical summary CSV files. Canary or partial "
            "inputs are technical validation artifacts only.",
            "",
            "## Final Mean Regret",
            "",
            _markdown_table(
                final_table,
                ("condition", "algorithm", "n", "mean_regret", "ci95_low", "ci95_high"),
                limit=30,
            ),
            "",
            "## Paired Mean-Regret Differences",
            "",
            _markdown_table(
                paired_table,
                ("comparison", "n_pairs", "mean_difference", "ci95_low", "ci95_high"),
                limit=30,
            ),
            "",
        ]
    )


def _markdown_table(
    rows: list[dict[str, object]],
    columns: Sequence[str],
    *,
    limit: int,
) -> str:
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows[:limit]:
        body.append(
            "| "
            + " | ".join(_markdown_value(row.get(column, "")) for column in columns)
            + " |"
        )
    if len(rows) > limit:
        body.append(
            "| "
            + " | ".join("..." if index == 0 else "" for index, _ in enumerate(columns))
            + " |"
        )
    return "\n".join([header, divider, *body])


def _markdown_value(value: object) -> str:
    text = str(value)
    return text.replace("|", "\\|")


def _condition_label(row: dict[str, str]) -> str:
    parts = [
        row.get("group_name", ""),
        row.get("topology", ""),
        row.get("topology_mode", ""),
        row.get("attack_strategy", ""),
        row.get("byzantine_placement", ""),
        row.get("algorithm_label", ""),
    ]
    return " / ".join(part for part in parts if part)


def _pair_label(row: dict[str, str]) -> str:
    return " / ".join(
        part
        for part in (
            row.get("group_name", ""),
            row.get("topology", ""),
            row.get("topology_mode", ""),
            row.get("comparison", ""),
            f"{row.get('target_algorithm_label', '')} vs "
            f"{row.get('baseline_algorithm_label', '')}",
        )
        if part
    )


def _curve_subtitle(rows: list[dict[str, str]]) -> str:
    condition = _curve_condition(rows)
    return condition if condition else "Selected condition from curve summary"


def _curve_condition(rows: list[dict[str, str]]) -> str | None:
    if not rows:
        return None
    first = rows[0]
    return " / ".join(
        part
        for part in (
            first.get("group_name", ""),
            first.get("topology", ""),
            first.get("topology_mode", ""),
            first.get("attack_strategy", ""),
            first.get("byzantine_placement", ""),
        )
        if part
    )


def _row_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row.get("group_kind", ""),
        row.get("group_name", ""),
        row.get("topology", ""),
        row.get("topology_mode", ""),
        row.get("algorithm_label", ""),
        row.get("aggregation", ""),
        row.get("attack_strategy", ""),
        row.get("byzantine_fraction", ""),
        row.get("byzantine_placement", ""),
        row.get("target_arm", ""),
        row.get("inflated_mean", ""),
    )


def _svg_header(width: int, height: int) -> str:
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" role="img">',
            "<style>",
            "text{font-family:Inter,Arial,sans-serif;fill:#17202a}",
            ".title{font-size:22px;font-weight:700}",
            ".subtitle{font-size:13px;fill:#52606d}",
            ".tick{font-size:11px;fill:#3e4c59}",
            ".axis-label{font-size:12px;font-weight:600;fill:#243b53}",
            "</style>",
            '<rect width="100%" height="100%" fill="#ffffff"/>',
        ]
    )


def _title(title: str, subtitle: str) -> str:
    return (
        f'<text x="28" y="34" class="title">{html.escape(title)}</text>'
        f'<text x="28" y="56" class="subtitle">{html.escape(subtitle)}</text>'
    )


def _axis_frame(margin: dict[str, int], plot_width: int, plot_height: int) -> str:
    x0 = margin["left"]
    y0 = margin["top"]
    x1 = margin["left"] + plot_width
    y1 = margin["top"] + plot_height
    return (
        f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" '
        'stroke="#1f2933" stroke-width="1.2"/>'
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" '
        'stroke="#1f2933" stroke-width="1.2"/>'
    )


def _empty_svg(title: str, subtitle: str, message: str) -> str:
    width = 920
    height = 360
    return "\n".join(
        [
            _svg_header(width, height),
            _title(title, subtitle),
            f'<text x="40" y="150" class="axis-label">{html.escape(message)}</text>',
            "</svg>",
        ]
    )


def _scale(
    value: float,
    source_min: float,
    source_max: float,
    target_min: float,
    target_max: float,
) -> float:
    if math.isclose(source_min, source_max):
        return (target_min + target_max) / 2.0
    ratio = (value - source_min) / (source_max - source_min)
    return target_min + ratio * (target_max - target_min)


def _ticks(minimum: float, maximum: float, count: int) -> list[float]:
    if count <= 1:
        return [minimum]
    step = (maximum - minimum) / (count - 1)
    return [minimum + index * step for index in range(count)]


def _algorithm_colour(algorithm: str, index: int) -> str:
    return ALGORITHM_COLOURS.get(
        algorithm,
        FALLBACK_COLOURS[index % len(FALLBACK_COLOURS)],
    )


def _format_number(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}"
    return f"{value:.2f}"


def _shorten(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "..."


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    columns = tuple(rows[0]) if rows else ("empty",)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
