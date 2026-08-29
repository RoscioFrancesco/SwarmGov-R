"""Build a static HTML viewer for generated SwarmGov-R artifacts."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path

DEFAULT_PROCESSED_DIR = Path("results/processed/milestone7-pilot")
DEFAULT_FIGURE_DIR = Path("results/figures/milestone7-pilot")
DEFAULT_OUTPUT = Path("results/viewer/milestone7/index.html")
DEFAULT_MANIFEST = Path("experiments/manifests/confirmatory_m8_manifest.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-dir", default=str(DEFAULT_PROCESSED_DIR))
    parser.add_argument("--figure-dir", default=str(DEFAULT_FIGURE_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()

    processed_dir = Path(args.processed_dir)
    figure_dir = Path(args.figure_dir)
    output_path = Path(args.output)
    manifest_path = Path(args.manifest)

    data = ViewerData.from_paths(
        processed_dir=processed_dir,
        figure_dir=figure_dir,
        output_path=output_path,
        manifest_path=manifest_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_viewer(data), encoding="utf-8")
    print(f"viewer={output_path}")
    return 0


class ViewerData:
    def __init__(
        self,
        *,
        processed_dir: Path,
        figure_dir: Path,
        output_path: Path,
        manifest_path: Path,
        summary_rows: list[dict[str, object]],
        paired_rows: list[dict[str, object]],
        pilot_summary: dict[str, object],
        runtime_estimate: dict[str, object],
        manifest: dict[str, object] | None,
        figures: dict[str, str],
        overview_figure: str | None,
    ) -> None:
        self.processed_dir = processed_dir
        self.figure_dir = figure_dir
        self.output_path = output_path
        self.manifest_path = manifest_path
        self.summary_rows = summary_rows
        self.paired_rows = paired_rows
        self.pilot_summary = pilot_summary
        self.runtime_estimate = runtime_estimate
        self.manifest = manifest
        self.figures = figures
        self.overview_figure = overview_figure

    @classmethod
    def from_paths(
        cls,
        *,
        processed_dir: Path,
        figure_dir: Path,
        output_path: Path,
        manifest_path: Path,
    ) -> ViewerData:
        _require_file(processed_dir / "final_regret_summary.csv")
        _require_file(processed_dir / "paired_differences.csv")
        _require_file(processed_dir / "pilot_summary.json")
        _require_file(processed_dir / "runtime_estimate.json")
        if not figure_dir.exists():
            raise FileNotFoundError(f"figure directory not found: {figure_dir}")

        summary_rows = _read_csv(processed_dir / "final_regret_summary.csv")
        paired_rows = _read_csv(processed_dir / "paired_differences.csv")
        pilot_summary = _read_json(processed_dir / "pilot_summary.json")
        runtime_estimate = _read_json(processed_dir / "runtime_estimate.json")
        manifest = _read_json(manifest_path) if manifest_path.exists() else None
        figures = _curve_figure_map(
            summary_rows=summary_rows,
            figure_dir=figure_dir,
            output_path=output_path,
        )
        overview = figure_dir / "exploratory_final_regret_overview.svg"
        overview_figure = (
            _relative_path(overview, output_path.parent) if overview.exists() else None
        )

        return cls(
            processed_dir=processed_dir,
            figure_dir=figure_dir,
            output_path=output_path,
            manifest_path=manifest_path,
            summary_rows=summary_rows,
            paired_rows=paired_rows,
            pilot_summary=pilot_summary,
            runtime_estimate=runtime_estimate,
            manifest=manifest,
            figures=figures,
            overview_figure=overview_figure,
        )


def render_viewer(data: ViewerData) -> str:
    summary = _normalized_summary(data.summary_rows)
    paired = _normalized_paired(data.paired_rows)
    metadata = _metadata(data)
    payload = {
        "summary": summary,
        "paired": paired,
        "figures": data.figures,
        "overviewFigure": data.overview_figure,
        "metadata": metadata,
    }
    payload_json = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).replace("</", "<\\/")
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>SwarmGov-R Milestone 7 Viewer</title>",
            "<style>",
            _css(),
            "</style>",
            "</head>",
            "<body>",
            '<main class="shell">',
            _header(metadata),
            _overview_section(),
            _explorer_section(),
            _tables_section(),
            _runtime_section(),
            _provenance_section(metadata),
            "</main>",
            f'<script id="viewer-data" type="application/json">{payload_json}</script>',
            "<script>",
            _javascript(),
            "</script>",
            "</body>",
            "</html>",
        ]
    )


def _metadata(data: ViewerData) -> dict[str, object]:
    pilot = data.pilot_summary
    runtime = data.runtime_estimate
    projection = runtime.get("confirmatory_projection")
    manifest = data.manifest or {}
    return {
        "title": "SwarmGov-R Milestone 7 Viewer",
        "stage": "Stage B exploratory pilot",
        "warning": "Exploratory pilot only - not confirmatory evidence",
        "plannedRuns": pilot.get("planned_runs"),
        "completedRuns": pilot.get("completed_runs"),
        "failedRuns": pilot.get("failed_runs"),
        "runtimeSeconds": runtime.get("total_runtime_seconds"),
        "meanRuntimeSeconds": runtime.get("mean_runtime_seconds_per_run"),
        "seedCount": runtime.get("pilot_seed_count"),
        "pilotHorizon": runtime.get("pilot_horizon"),
        "pilotAgents": runtime.get("pilot_agents"),
        "processedDir": str(data.processed_dir),
        "figureDir": str(data.figure_dir),
        "manifest": str(data.manifest_path),
        "m8PrimaryRuns": _nested_get(
            manifest,
            "run_count_estimate",
            "primary_planned_runs",
        ),
        "m8TotalRuns": _nested_get(
            manifest,
            "run_count_estimate",
            "total_planned_runs",
        ),
        "m8PrimaryHours": _nested_get(
            projection,
            "estimated_primary_runtime_hours_single_process",
        ),
        "m8TotalHours": _nested_get(
            projection,
            "estimated_total_runtime_hours_single_process",
        ),
    }


def _header(metadata: dict[str, object]) -> str:
    metrics = [
        ("Completed runs", _format_int(metadata["completedRuns"])),
        ("Failed runs", _format_int(metadata["failedRuns"])),
        ("Pilot seeds", _format_int(metadata["seedCount"])),
        ("Runtime", _format_seconds(metadata["runtimeSeconds"])),
    ]
    metric_html = "\n".join(
        f'<section class="metric"><span>{html.escape(label)}</span>'
        f"<strong>{html.escape(value)}</strong></section>"
        for label, value in metrics
    )
    return "\n".join(
        [
            '<header class="hero">',
            '<div class="hero-copy">',
            f"<p>{html.escape(str(metadata['stage']))}</p>",
            f"<h1>{html.escape(str(metadata['title']))}</h1>",
            f"<strong>{html.escape(str(metadata['warning']))}</strong>",
            "</div>",
            f'<div class="metrics">{metric_html}</div>',
            "</header>",
        ]
    )


def _overview_section() -> str:
    return "\n".join(
        [
            '<section class="band" aria-labelledby="overview-title">',
            '<div class="section-head">',
            '<h2 id="overview-title">Overview</h2>',
            '<p>Final regret overview across the Milestone 7 pilot grid.</p>',
            "</div>",
            '<figure class="figure-frame">',
            '<img id="overview-figure" alt="Exploratory final regret overview">',
            "</figure>",
            "</section>",
        ]
    )


def _explorer_section() -> str:
    return "\n".join(
        [
            '<section class="band" aria-labelledby="explorer-title">',
            '<div class="section-head">',
            '<h2 id="explorer-title">Regret Curves</h2>',
            '<p>Mean honest cumulative regret curves for one selected condition.</p>',
            "</div>",
            '<form class="controls" id="controls">',
            _select("topology", "Topology"),
            _select("condition", "Condition"),
            _select("topologyMode", "Topology mode"),
            "</form>",
            '<figure class="figure-frame">',
            '<img id="curve-figure" alt="Selected exploratory regret curve">',
            '<figcaption id="curve-caption"></figcaption>',
            "</figure>",
            "</section>",
        ]
    )


def _select(identifier: str, label: str) -> str:
    escaped_id = html.escape(identifier)
    return "\n".join(
        [
            '<label class="control">',
            f'<span>{html.escape(label)}</span>',
            f'<select id="{escaped_id}" name="{escaped_id}"></select>',
            "</label>",
        ]
    )


def _tables_section() -> str:
    return "\n".join(
        [
            '<section class="band" aria-labelledby="tables-title">',
            '<div class="section-head">',
            '<h2 id="tables-title">Tables</h2>',
            '<p>Filtered summary rows and paired exploratory differences.</p>',
            "</div>",
            '<div class="table-block">',
            "<h3>Final Regret Summary</h3>",
            '<div class="table-wrap"><table id="summary-table"></table></div>',
            "</div>",
            '<div class="table-block">',
            "<h3>Paired Differences</h3>",
            '<div class="table-wrap"><table id="paired-table"></table></div>',
            "</div>",
            "</section>",
        ]
    )


def _runtime_section() -> str:
    return "\n".join(
        [
            '<section class="band" aria-labelledby="runtime-title">',
            '<div class="section-head">',
            '<h2 id="runtime-title">Runtime Planning</h2>',
            '<p>Observed pilot runtime and linear Milestone 8 planning estimate.</p>',
            "</div>",
            '<div class="metrics runtime-metrics" id="runtime-metrics"></div>',
            "</section>",
        ]
    )


def _provenance_section(metadata: dict[str, object]) -> str:
    lines = [
        ("Processed data", metadata["processedDir"]),
        ("Figures", metadata["figureDir"]),
        ("Manifest", metadata["manifest"]),
    ]
    items = "\n".join(
        f"<li><span>{html.escape(label)}</span><code>{html.escape(str(value))}</code></li>"
        for label, value in lines
    )
    return "\n".join(
        [
            '<section class="band provenance" aria-labelledby="provenance-title">',
            '<div class="section-head">',
            '<h2 id="provenance-title">Provenance</h2>',
            '<p>Local files used to regenerate this viewer.</p>',
            "</div>",
            f"<ul>{items}</ul>",
            "<pre><code>"
            "python3 experiments/scripts/build_static_viewer.py"
            "</code></pre>",
            "</section>",
        ]
    )


def _css() -> str:
    return """
:root {
  color-scheme: light;
  --bg: #f7f6f2;
  --panel: #ffffff;
  --ink: #1d252c;
  --muted: #5d6670;
  --line: #d7d9d2;
  --accent: #245c73;
  --accent-soft: #d8e7ec;
  --good: #2f6f54;
  --warn: #8c5b20;
}
* {
  box-sizing: border-box;
}
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
}
.shell {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px;
}
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.8fr);
  gap: 18px;
  align-items: stretch;
  margin-bottom: 18px;
}
.hero-copy,
.band,
.metric {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.hero-copy {
  padding: 24px;
}
.hero-copy p,
.section-head p,
figcaption,
.metric span,
.provenance span {
  color: var(--muted);
}
.hero-copy p {
  margin: 0 0 8px;
  font-size: 0.9rem;
}
h1,
h2,
h3 {
  margin: 0;
  font-weight: 600;
  letter-spacing: 0;
}
h1 {
  font-size: clamp(1.9rem, 4vw, 3.2rem);
}
h2 {
  font-size: 1.35rem;
}
h3 {
  font-size: 1rem;
  margin: 18px 0 10px;
}
.hero-copy strong {
  display: inline-block;
  margin-top: 14px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 0.92rem;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.metric {
  padding: 16px;
}
.metric strong {
  display: block;
  margin-top: 6px;
  font-size: 1.35rem;
  font-weight: 600;
}
.band {
  padding: 20px;
  margin: 18px 0;
}
.section-head {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: end;
  margin-bottom: 16px;
}
.section-head p {
  margin: 0;
  max-width: 560px;
}
.controls {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}
.control span {
  display: block;
  color: var(--muted);
  font-size: 0.86rem;
  margin-bottom: 4px;
}
select {
  width: 100%;
  min-height: 40px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  color: var(--ink);
  padding: 8px 10px;
  font: inherit;
}
.figure-frame {
  margin: 0;
}
.figure-frame img {
  display: block;
  width: 100%;
  min-height: 240px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  object-fit: contain;
}
figcaption {
  min-height: 22px;
  margin-top: 8px;
  font-size: 0.92rem;
}
.table-wrap {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  min-width: 760px;
}
th,
td {
  padding: 9px 10px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
  font-size: 0.92rem;
}
th {
  color: var(--muted);
  font-weight: 600;
}
td.numeric,
th.numeric {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.provenance ul {
  list-style: none;
  padding: 0;
  margin: 0;
}
.provenance li {
  display: grid;
  grid-template-columns: 140px minmax(0, 1fr);
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
}
code,
pre {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
pre {
  overflow-x: auto;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #f0f2ee;
}
@media (max-width: 820px) {
  .shell {
    padding: 14px;
  }
  .hero,
  .metrics,
  .controls,
  .section-head {
    grid-template-columns: 1fr;
    display: grid;
  }
  .provenance li {
    grid-template-columns: 1fr;
  }
}
""".strip()


def _javascript() -> str:
    return """
const payload = JSON.parse(document.getElementById("viewer-data").textContent);
const summary = payload.summary;
const paired = payload.paired;
const figures = payload.figures;
const metadata = payload.metadata;

const selectors = {
  topology: document.getElementById("topology"),
  condition: document.getElementById("condition"),
  topologyMode: document.getElementById("topologyMode")
};

function unique(values) {
  return Array.from(new Set(values)).sort();
}

function fillSelect(select, values) {
  select.innerHTML = "";
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
}

function number(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "";
  }
  return Number(value).toFixed(digits);
}

function percent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "";
  }
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function currentFilter() {
  return {
    topology: selectors.topology.value,
    condition: selectors.condition.value,
    topologyMode: selectors.topologyMode.value
  };
}

function filteredRows(rows) {
  const filter = currentFilter();
  return rows.filter((row) =>
    row.topology === filter.topology &&
    row.condition === filter.condition &&
    row.topology_mode === filter.topologyMode
  );
}

function renderSummaryTable() {
  const rows = filteredRows(summary);
  renderTable(document.getElementById("summary-table"), [
    ["aggregation", "Aggregation", "text"],
    ["completed_runs", "Runs", "numeric"],
    ["mean_final_honest_regret", "Mean regret", "numeric"],
    ["ci95", "95% CI", "text"],
    ["mean_best_arm_identification_rate", "Best arm", "percent"],
    ["mean_worst_decile_honest_regret", "Worst decile", "numeric"],
    ["mean_fallback_frequency", "Fallback", "percent"],
    ["mean_runtime_seconds", "Runtime s", "numeric"]
  ], rows);
}

function renderPairedTable() {
  const rows = filteredRows(paired);
  renderTable(document.getElementById("paired-table"), [
    ["aggregation", "Aggregation", "text"],
    ["baseline", "Baseline", "text"],
    ["paired_seeds", "Seeds", "numeric"],
    ["mean_paired_difference_final_mean_regret", "Mean diff", "numeric"],
    ["ci95", "95% CI", "text"]
  ], rows);
}

function renderTable(table, columns, rows) {
  const head = columns.map(([key, label, type]) =>
    `<th class="${type === "numeric" || type === "percent"
      ? "numeric" : ""}">${label}</th>`
  ).join("");
  const body = rows.map((row) => {
    const cells = columns.map(([key, label, type]) => {
      let value = row[key];
      if (type === "numeric") {
        value = number(value);
      } else if (type === "percent") {
        value = percent(value);
      }
      const klass = type === "numeric" || type === "percent" ? "numeric" : "";
      return `<td class="${klass}">${value ?? ""}</td>`;
    }).join("");
    return `<tr>${cells}</tr>`;
  }).join("");
  table.innerHTML = `<thead><tr>${head}</tr></thead><tbody>${body}</tbody>`;
}

function renderFigures() {
  const overview = document.getElementById("overview-figure");
  if (payload.overviewFigure) {
    overview.src = payload.overviewFigure;
  }
  const filter = currentFilter();
  const key = `${filter.topology}|${filter.condition}|${filter.topologyMode}`;
  const curve = document.getElementById("curve-figure");
  const caption = document.getElementById("curve-caption");
  if (figures[key]) {
    curve.src = figures[key];
    caption.textContent =
      `${filter.topology} / ${filter.condition} / ${filter.topologyMode}`;
  } else {
    curve.removeAttribute("src");
    caption.textContent = "No SVG generated for this selection.";
  }
}

function renderRuntime() {
  const metrics = [
    ["Pilot horizon", metadata.pilotHorizon],
    ["Pilot agents", metadata.pilotAgents],
    ["Mean run time", `${number(metadata.meanRuntimeSeconds, 3)}s`],
    ["M8 primary runs", metadata.m8PrimaryRuns],
    ["M8 primary estimate", `${number(metadata.m8PrimaryHours, 1)}h`],
    ["M8 total estimate", `${number(metadata.m8TotalHours, 1)}h`]
  ];
  document.getElementById("runtime-metrics").innerHTML = metrics.map(([label, value]) =>
    `<section class="metric"><span>${label}</span>` +
    `<strong>${value ?? ""}</strong></section>`
  ).join("");
}

function renderAll() {
  renderFigures();
  renderSummaryTable();
  renderPairedTable();
}

fillSelect(selectors.topology, unique(summary.map((row) => row.topology)));
fillSelect(selectors.condition, unique(summary.map((row) => row.condition)));
fillSelect(selectors.topologyMode, unique(summary.map((row) => row.topology_mode)));

selectors.topology.value = "ring";
selectors.condition.value = "clean";
selectors.topologyMode.value = "static";

for (const select of Object.values(selectors)) {
  select.addEventListener("change", renderAll);
}

renderRuntime();
renderAll();
""".strip()


def _normalized_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for row in rows:
        clean = {
            "topology": str(row["topology"]),
            "condition": str(row["condition"]),
            "topology_mode": str(row["topology_mode"]),
            "aggregation": str(row["aggregation"]),
            "completed_runs": _int_value(row["completed_runs"]),
            "mean_final_honest_regret": _float_value(
                row["mean_final_honest_regret"]
            ),
            "ci95_low": _float_value(row["ci95_low"]),
            "ci95_high": _float_value(row["ci95_high"]),
            "mean_best_arm_identification_rate": _float_value(
                row["mean_best_arm_identification_rate"]
            ),
            "mean_worst_decile_honest_regret": _float_value(
                row["mean_worst_decile_honest_regret"]
            ),
            "mean_fallback_frequency": _float_value(row["mean_fallback_frequency"]),
            "mean_runtime_seconds": _float_value(row["mean_runtime_seconds"]),
        }
        clean["ci95"] = "{} to {}".format(
            _format_number(clean["ci95_low"]),
            _format_number(clean["ci95_high"]),
        )
        normalized.append(clean)
    return normalized


def _normalized_paired(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for row in rows:
        clean = {
            "topology": str(row["topology"]),
            "condition": str(row["condition"]),
            "topology_mode": str(row["topology_mode"]),
            "aggregation": str(row["aggregation"]),
            "baseline": str(row["baseline"]),
            "paired_seeds": _int_value(row["paired_seeds"]),
            "mean_paired_difference_final_mean_regret": _float_value(
                row["mean_paired_difference_final_mean_regret"]
            ),
            "ci95_low": _float_value(row["ci95_low"]),
            "ci95_high": _float_value(row["ci95_high"]),
        }
        clean["ci95"] = "{} to {}".format(
            _format_number(clean["ci95_low"]),
            _format_number(clean["ci95_high"]),
        )
        normalized.append(clean)
    return normalized


def _curve_figure_map(
    *,
    summary_rows: list[dict[str, object]],
    figure_dir: Path,
    output_path: Path,
) -> dict[str, str]:
    combinations: dict[tuple[str, str, str], None] = {}
    for row in summary_rows:
        key = (
            str(row["topology"]),
            str(row["condition"]),
            str(row["topology_mode"]),
        )
        combinations[key] = None

    figures: dict[str, str] = {}
    for topology, condition, topology_mode in combinations:
        filename = (
            f"exploratory_regret_curves_{topology}_{condition}_"
            f"{topology_mode}.svg"
        )
        path = figure_dir / filename
        if path.exists():
            figures[f"{topology}|{condition}|{topology_mode}"] = _relative_path(
                path,
                output_path.parent,
            )
    return figures


def _read_csv(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"expected JSON object in {path}")
    return loaded


def _require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"required viewer input not found: {path}")


def _relative_path(path: Path, start: Path) -> str:
    return os.path.relpath(Path(path).resolve(), Path(start).resolve()).replace(
        os.sep,
        "/",
    )


def _nested_get(mapping: object, *keys: str) -> object | None:
    current = mapping
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _float_value(value: object) -> float:
    return float(value)


def _int_value(value: object) -> int:
    return int(value)


def _format_number(value: object) -> str:
    if value is None:
        return ""
    return f"{float(value):.2f}"


def _format_int(value: object) -> str:
    if value is None:
        return ""
    return f"{int(value):,}"


def _format_seconds(value: object) -> str:
    if value is None:
        return ""
    seconds = float(value)
    if seconds < 120:
        return f"{seconds:.1f}s"
    minutes = seconds / 60.0
    return f"{minutes:.1f}m"


if __name__ == "__main__":
    raise SystemExit(main())
