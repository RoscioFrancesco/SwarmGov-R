# SwarmGov-R Decision Log

This log records project decisions that affect scope, research validity,
implementation assumptions, or reproducibility.

## 2026-08-25 - Initial Scope And Milestone Boundary

- Decision: complete Milestone 0 and Milestone 1 only.
- Rationale: the user explicitly requested research framing and repository
  foundation while stopping before Byzantine attacks and large experiments.
- Consequence: no Bernoulli environment, UCB1 agent, Byzantine attack,
  aggregator, graph generator, or experiment runner is implemented in this
  milestone.

## 2026-08-25 - Default Research Question

- Decision: adopt the project's default research question:
  "Under which combinations of communication topology, Byzantine fraction, and
  graph change does robust decentralized aggregation outperform both ordinary
  consensus and independent learning?"
- Rationale: aligns the project with decentralized learning, adversarial
  information, and graph structure.
- Consequence: future changes to this question require a dated decision.

## 2026-08-25 - Primary Extension

- Decision: keep dynamic communication topology as the primary extension.
- Rationale: required by the project scope and central to the intended
  contribution.
- Consequence: reputation weighting and adaptive attacks remain optional and
  deferred.

## 2026-08-25 - Threat Model Baseline

- Decision: start with controlled value-corruption Byzantine messages, not a
  fully arbitrary-message model.
- Rationale: preserves hand-verifiability and separates simulator ground truth
  from declared message values.
- Consequence: any later arbitrary-message threat model must be documented and
  reported separately.

## 2026-08-25 - Centralized Clean-Information Baseline

- Decision: label the default centralized clean-information baseline as using
  honest data.
- Rationale: avoids silently removing Byzantine data in a way that would make
  comparisons misleading.
- Consequence: any all-data, Byzantine-aware, or omniscient zero-regret
  reference must be explicitly named and kept separate from learning
  algorithms.

## 2026-08-25 - Reproducibility Foundation

- Decision: derive component random streams from a master integer seed using
  `numpy.random.SeedSequence`.
- Rationale: matches the reproducibility policy and makes environment, graph, agent,
  attack, simulation, and analysis randomness separable.
- Consequence: all future stochastic code should receive injected
  `numpy.random.Generator` instances rather than using global randomness.

## 2026-08-25 - Configuration Loader

- Decision: implement typed dataclass configuration loading from YAML using
  PyYAML.
- Rationale: the project needs reproducible non-interactive runs and a simple
  validated config format before simulation code exists.
- Consequence: `configs/smoke.yaml` validates only the foundation fields needed
  before Milestone 2; experiment execution remains intentionally unavailable.

## 2026-08-25 - Milestone 2 Single-Agent Boundary

- Decision: implement only a single-agent Bernoulli bandit run using
  Independent UCB1.
- Rationale: the user explicitly requested Milestone 2 only, whose deliverables
  are the Bernoulli environment, UCB1 agent, regret metrics, deterministic and
  stochastic tests, and a single-run CLI.
- Consequence: `swarmgov run` rejects configurations with more than one agent,
  communication enabled, Byzantine fractions above zero, topology changes, or
  algorithms other than `independent_ucb1`.

## 2026-08-25 - Run Seed Derivation

- Decision: derive per-run component streams from the master seed with
  `SeedSequence(master_seed, spawn_key=(run_seed,))`, then spawn named
  component streams.
- Rationale: this uses the existing master-seed contract while making
  `experiment.seeds` meaningful for reproducible single runs.
- Consequence: result files record both resolved configuration seeds and
  run-specific component seeds.

## 2026-08-25 - Milestone 3 Clean Multi-Agent Boundary

- Decision: implement graph generation, typed messages, clean communication,
  independent multi-agent UCB1, a centralized pooled shared-action UCB1
  baseline, and one-hop weighted pooling UCB1 only.
- Rationale: the user requested Milestone 3 only; Byzantine attacks, robust
  aggregation, and dynamic topology start in later milestones.
- Consequence: `swarmgov run` rejects multi-agent configurations with Byzantine
  fraction above zero or topology changes enabled. The Byzantine part of this
  consequence is superseded by the Milestone 4 attack-scope decisions below.

## 2026-08-25 - One-Hop Weighted Pooling Baseline Semantics

- Decision: define the Milestone 3 collaborative mean-based baseline as
  one-hop count-weighted pooling of an agent's local sufficient statistics with
  one local-statistics message from each current graph neighbor.
- Rationale: this is hand-checkable, avoids double-counting propagated
  aggregate statistics, and provides an ordinary non-robust collaborative
  baseline before robust aggregation exists.
- Consequence: messages contain local counts, local reward sums, and derived
  empirical means. Agents use pooled counts and reward sums for arm selection,
  but local learning state remains based only on their own rewards. The
  algorithm is named `one_hop_weighted_pooling_ucb1`, not
  `mean_consensus_ucb1`, because it does not perform iterative information
  diffusion.

## 2026-08-25 - Centralized Pooled Shared-Action Semantics

- Decision: implement the Milestone 3 centralized clean baseline as a single
  UCB1 learner that chooses one shared arm per round for all honest agents and
  then aggregates all honest rewards from that round.
- Rationale: this provides a clean-information upper reference while avoiding
  Byzantine filtering assumptions before Byzantine agents exist.
- Consequence: the algorithm is labelled
  `centralized_pooled_shared_action_ucb1`. It is not a deployable decentralized
  agent and is not an omniscient zero-expected-regret oracle.

## 2026-08-25 - NetworkX As Runtime Dependency

- Decision: move NetworkX into core project dependencies.
- Rationale: static complete, ring, Watts-Strogatz, and Barabasi-Albert graph
  generation are Milestone 3 runtime functionality, not only offline analysis.
- Consequence: a fresh install must include `networkx>=3.2`.

## 2026-08-25 - Clean Message Authoritative Fields

- Decision: treat `counts` and `reward_sums` as the authoritative transmitted
  clean-message fields.
- Rationale: one authoritative sufficient-statistics pair avoids inconsistently
  trusting both empirical means and raw support in later attack models.
- Consequence: `empirical_means` are derived from `reward_sums / counts` for
  diagnostics and JSON records. Clean aggregation ignores `empirical_means`.

## 2026-08-25 - Synchronous Lossless Communication And No Arm Collisions

- Decision: Milestone 3 assumes synchronous, instantaneous, lossless
  communication at configured communication rounds and no arm collisions.
- Rationale: the current milestone validates graph/message plumbing and clean
  baselines before communication noise, adversaries, or resource contention.
- Consequence: messages sent after round `t` observations are available for the
  next arm-selection step; multiple agents pulling the same arm receive
  independent Bernoulli rewards from that arm.

## 2026-08-25 - Milestone 3 Artifact Renaming

- Decision: rename the Milestone 3 smoke algorithm identifiers before starting
  Milestone 4.
- Rationale: `mean_consensus_ucb1` overstated the implementation because there
  is no iterative diffusion, and `centralized_ucb_oracle` risked confusing a
  learning baseline with an omniscient oracle.
- Consequence: existing raw smoke artifacts using the old names are deprecated
  technical artifacts and should not be used as current evidence.

## 2026-08-25 - Milestone 4 Attack Scope

- Decision: implement only the Milestone 4 message-level attacks requested for
  this step: `no_attack`, `constant_inflation`, and `coordinated_target`.
- Rationale: the current milestone is attack plumbing and validation, not the
  full adversarial benchmark or robust aggregation study.
- Consequence: sign/order inversion, adaptive attacks, arbitrary-message
  attacks, median aggregation, trimmed mean, reputation weighting, dynamic
  topology, and large sweeps remain deferred.

## 2026-08-25 - Controlled Value-Corruption Fields

- Decision: keep `counts` truthful and allow Byzantine strategies to modify
  only outgoing `reward_sums`; `empirical_means` are always derived by
  `Message`.
- Rationale: this creates a hand-verifiable controlled corruption model while
  preserving the simulator's ground-truth local observations.
- Consequence: Byzantine senders cannot invent support for an unobserved arm in
  the core model. Corrupted sums must remain in `[0, count]`, and attacks do
  not mutate rewards, local agent state, graph structure, RNG state, metadata,
  sender/receiver identity, or stored observations.

## 2026-08-25 - Byzantine Placement Semantics

- Decision: convert Byzantine fraction to node count with
  `floor(fraction * number_of_agents)`, reject positive fractions that select
  zero nodes, and require at least one honest node.
- Rationale: the actual Byzantine count never exceeds the configured fraction
  and remains deterministic across runs.
- Consequence: small smoke/test populations must choose fractions large enough
  to select at least one attacker. The actual Byzantine count is recorded with
  every multi-agent result.

## 2026-08-25 - Random And Degree-Centrality Placement

- Decision: random placement samples without replacement from the `attack`
  seed stream and records sorted node IDs; degree-centrality placement selects
  highest-degree nodes with smaller node IDs breaking ties.
- Rationale: placement must be deterministic, reproducible, and hand-checkable
  on tiny graphs.
- Consequence: future centrality policies must be named separately and tested
  without changing the semantics of `degree_centrality`.

## 2026-08-25 - Honest-Agent Evaluation Under Byzantine Runs

- Decision: multi-agent regret and best-arm identification rates are computed
  over honest nodes when Byzantine nodes exist.
- Rationale: the documented evaluation policy says Byzantine actions should not improve or
  worsen honest-agent regret unless a separate population metric is reported.
- Consequence: result records now include `honest_nodes` and `byzantine_nodes`
  so per-agent metrics can be interpreted correctly.

## 2026-08-25 - Centralized Baseline Remains Clean-Only

- Decision: reject Byzantine configurations for
  `centralized_pooled_shared_action_ucb1` until an explicit Byzantine
  information model is defined for that reference.
- Rationale: otherwise the centralized pooled learner could silently mix honest
  and Byzantine observations or become an implicit filtering oracle.
- Consequence: Milestone 4 attacks are validated through the message-level
  decentralized interface. A future clean/honest-data centralized reference
  under Byzantine conditions needs its own documented decision.

## 2026-08-25 - Attack Diagnostics

- Decision: add optional per-message diagnostics recording original and
  corrupted messages for Byzantine outgoing messages.
- Rationale: Stage A validation needs hand-verifiable evidence that attacks
  modify only permitted fields.
- Consequence: diagnostics are disabled by default and should not be used as a
  large-sweep logging default because they can become verbose.

## 2026-08-25 - Milestone 5 Robust Aggregation Scope

- Decision: implement count-weighted mean, unweighted per-source median, and
  unweighted per-source symmetric trimmed mean as one-hop aggregation baselines.
- Rationale: the user requested empirical robust-aggregation baselines without
  claiming unproven Byzantine safety.
- Consequence: these methods are not multi-hop consensus, reputation weighting,
  adaptive defenses, dynamic topology, or confirmatory experiments.

## 2026-08-25 - Robust Source Construction

- Decision: median and trimmed mean include the receiver's local estimate once
  when available and at most one latest valid estimate per direct neighbour per
  arm.
- Rationale: source-level robust statistics should not weight a sender multiple
  times because it has more local observations.
- Consequence: unavailable arm estimates are excluded rather than interpreted
  as zero, and empirical estimates are always derived from authoritative
  `counts` and `reward_sums`.

## 2026-08-25 - Robust UCB Effective Support

- Decision: robust median and trimmed-mean decision statistics use a
  source-count effective support rule.
- Rationale: no inspected paper-faithful confidence rule has been frozen yet,
  and source-count support makes the heuristic explicit and conservative under
  heterogeneous neighbour sample counts.
- Consequence: median and trimmed mean are labelled heuristic robust one-hop
  UCB baselines; no standard UCB regret guarantee is claimed. Count-weighted
  mean keeps the existing summed-count behaviour as a regression baseline.

## 2026-08-25 - Trimmed-Mean Small-Neighbourhood Policy

- Decision: implement `median_fallback` when requested symmetric trimming
  would remove every source estimate.
- Rationale: this avoids silently reverting to ordinary mean while keeping
  small neighbourhoods deterministic and hand-checkable.
- Consequence: aggregation diagnostics record fallback usage per arm and a
  lightweight result summary counts fallback events.

## 2026-08-25 - Milestone 5 Exploratory Pilot Boundary

- Decision: add a bounded Milestone 5 pilot using 20 seeds, independent UCB,
  one-hop mean, one-hop median, one-hop trimmed mean, clean and coordinated
  target attack conditions, complete and ring graphs, and static topology only.
- Rationale: the milestone asks for exploratory technical evidence after
  tests pass, while avoiding a confirmatory sweep.
- Consequence: pilot outputs must be labelled exploratory and must not be used
  to change hypotheses or make confirmatory claims.

## 2026-08-25 - Milestone 5 Reduced Pilot Execution

- Decision: allow the pilot runner to execute the first `N` configured seeds
  with `--max-seeds` while preserving the full topology, condition, and
  aggregation grid for those seeds.
- Rationale: the full 20-seed Milestone 5 pilot is useful but can take several
  minutes because robust complete-graph runs perform source-level aggregation
  every round. A reduced run is sufficient as technical validation after the
  deterministic unit and integration tests pass.
- Consequence: reduced pilot outputs are labelled with the executed seed set
  and remain exploratory only. They cannot be used as confirmatory evidence or
  to tune hypotheses.

## 2026-08-26 - Milestone 6 Dynamic Topology Scope

- Decision: implement one configured edge-rewiring event for
  `one_hop_weighted_pooling_ucb1` runs only.
- Rationale: topology change matters through communication; independent UCB and
  the centralized pooled shared-action baseline do not use neighbour messages.
- Consequence: dynamic topology configurations for non-communication baselines
  are rejected instead of producing misleading no-effect dynamic runs.

## 2026-08-26 - Dynamic Event Timing

- Decision: apply the topology event at `change_round` after local actions,
  rewards, and local statistic updates, but before message construction for
  that round.
- Rationale: this keeps paired static/dynamic actions and rewards identical
  through the change round while allowing the changed graph to affect
  communication at the configured event.
- Consequence: post-change effects can appear only after the altered
  communication influences decision statistics; tests compare matched
  static/dynamic trajectories through the change round.

## 2026-08-26 - Rewiring And Connectivity Rule

- Decision: remove and add
  `max(1, floor(rewire_fraction * current_edge_count))` undirected edges,
  preserve node count, and retry when `preserve_connectivity=true` until the
  post-change graph is connected or the attempt limit is exhausted.
- Rationale: the process is deterministic, hand-checkable, and keeps
  communication budget changes attributable to graph structure rather than node
  count.
- Consequence: disconnected components are recorded when connectivity is not
  required. Added edges must be absent before the event, so removed edges are
  not re-added in the same event. Configurations that request more additions
  than the pre-change non-edge set allows fail loudly. Complete graphs are
  rejected for dynamic rewiring under this rule because they have no absent
  edges to add without reverting to the original complete graph.

## 2026-08-26 - Fixed Byzantine Identities Under Graph Change

- Decision: select Byzantine nodes from the initial graph and keep that set
  fixed after topology change.
- Rationale: Milestone 6 isolates topology churn from attacker placement
  changes.
- Consequence: dynamic topology may alter Byzantine neighbourhood exposure, but
  it does not re-run placement or give attackers graph-control capability.

## 2026-08-26 - Initial Recovery-Time Metric

- Decision: define recovery using per-round increments of mean honest
  cumulative regret, a 5-round pre-change reference window ending at the change
  round, a 5-round sustained post-change window, and tolerance `0.05` expected
  regret per round.
- Rationale: cumulative regret cannot decrease, so recovery must be measured on
  per-round performance. A fixed rule is needed before pilot comparisons.
- Consequence: the metric is recorded for dynamic runs but should be
  sensitivity-checked before confirmatory claims.

## 2026-08-26 - Milestone 7 Exploratory Pilot Grid

- Decision: run the Milestone 7 pilot as a bounded Stage B grid with 20 seeds,
  10 agents, 5 Bernoulli arms, 120 rounds, ring/small-world/scale-free
  topologies, clean/coordinated-random/coordinated-degree conditions,
  independent static UCB, and mean/median/trimmed one-hop aggregation under
  both static and dynamic topology.
- Rationale: the pilot must validate the static/dynamic pipeline, attacker
  placement ablation, robust aggregation, runtime, and figure-generation path
  without becoming a confirmatory sweep.
- Consequence: pilot results are exploratory only. They may be used for runtime
  planning and bug detection, but not as scientific evidence for the final
  claims.

## 2026-08-26 - Frozen Confirmatory Seed Set

- Decision: freeze confirmatory seeds as `1000..1099`.
- Rationale: the confirmatory protocol requires at least 100 predetermined seeds per
  primary condition and paired comparisons across algorithms.
- Consequence: seeds cannot be removed after confirmatory execution starts
  unless failures are logged and handled according to the frozen analysis plan.

## 2026-08-26 - Bounded Milestone 8 Primary Matrix

- Decision: freeze the Milestone 8 primary matrix in
  `docs/experiment-plan.md` and
  `experiments/manifests/confirmatory_m8_manifest.json` with `horizon=2000`,
  25 agents, 5 arms, all required static topologies for clean reference runs,
  dynamic ring/small-world/scale-free runs, coordinated-target attack as the
  primary adversarial condition, and constant-inflation as a static sensitivity
  condition.
- Rationale: the full canonical Cartesian product would be too large for the
  current simulator and deadline. The bounded matrix preserves the required
  ablations while keeping confirmatory compute feasible.
- Consequence: complete-graph dynamic rewiring, attacked centralized baselines,
  adaptive attacks, reputation weighting, and arbitrary-message attacks remain
  excluded. Changing the matrix after confirmatory execution begins requires a
  new dated decision.

## 2026-08-26 - Confirmatory Horizon

- Decision: use `2000` rounds rather than the initial canonical `10000` rounds
  for the frozen Milestone 8 primary matrix.
- Rationale: current result records preserve per-round action and reward data,
  and the pilot runtime indicates that the canonical horizon would make the
  full required ablation set unnecessarily expensive before final engineering
  optimizations.
- Consequence: final claims must be scoped to the frozen 2000-round horizon.
  Longer-horizon sensitivity runs may be added later, but they must be
  reported separately.

## 2026-08-26 - Milestone 7 Pilot Completion And Runtime Estimate

- Decision: accept the Milestone 7 pilot as completed technical validation
  after `1260/1260` configured runs finished with zero failures.
- Rationale: the pilot exercised clean, coordinated-random, and
  coordinated-degree conditions across ring, small-world, and scale-free
  graphs with static and dynamic one-hop aggregation.
- Consequence: the generated CSV/JSON/SVG outputs remain exploratory only. The
  observed runtime projects to approximately `42.3` single-process hours for
  the primary Milestone 8 matrix and `48.2` hours including the static
  constant-inflation sensitivity group, so Milestone 8 should start by adding a
  compact manifest runner with parallel execution.

## 2026-08-26 - Static Artifact Viewer

- Decision: add a regenerable static HTML viewer for Milestone 7 processed
  CSV/JSON outputs and SVG figure prototypes.
- Rationale: the project owner needs a quick graphical way to inspect produced
  artifacts without adding a server, dashboard framework, frontend dependency,
  or new scientific workflow.
- Consequence: `experiments/scripts/build_static_viewer.py` generates
  `results/viewer/milestone7/index.html`. The viewer is local, exploratory, and
  does not alter metrics, seeds, threat-model assumptions, or confirmatory
  analysis.

## 2026-08-27 - Confirmatory Manifest Runner

- Decision: add `experiments/scripts/run_confirmatory_manifest.py` to expand
  and execute the frozen Milestone 8 manifest.
- Rationale: confirmatory experiments must be launched reproducibly from the
  frozen manifest rather than hand-built per-condition commands.
- Consequence: the runner supports dry-run, primary/sensitivity/all group
  selection, named group restriction, bounded canary execution via `--max-runs`
  or `--max-seeds`, per-run compact JSON records, failure records, and resume
  by skipping existing completed JSON files. It does not execute the full
  confirmatory matrix by itself; validation, aggregation, statistics, and final
  figures remain later Step 2+ work.

## 2026-08-27 - Compact Confirmatory Output Schema

- Decision: store Milestone 8 per-run outputs using the versioned
  `confirmatory_compact_v1` payload documented in
  `docs/confirmatory-output-format.md`.
- Rationale: the confirmatory matrix is large enough that storing raw
  per-round actions, raw rewards, agent-state snapshots, and verbose
  diagnostics in every completed record would make storage and downstream
  processing unnecessarily heavy. The compact schema keeps final metrics,
  provenance, graph metadata, topology-change metadata, node identities,
  attack metadata, communication metrics, aggregation summaries, and sampled
  regret curves.
- Consequence: later validation, aggregation, statistics, and plotting code
  must read completed records through `result.schema_version`,
  `result.metrics`, and `result.curves`. Incompatible storage changes require a
  schema-version bump and a new dated decision.

## 2026-08-27 - Confirmatory Result Validation Gate

- Decision: add `experiments/scripts/validate_confirmatory_results.py` as the
  validation gate before Milestone 8 aggregation, statistics, and figure
  generation.
- Rationale: confirmatory evidence must not be aggregated from an incomplete
  or mixed result directory. The validator expands the same frozen manifest as
  the runner and checks for missing, failed, duplicated, unexpected, unreadable,
  or schema-incompatible records.
- Consequence: a result directory is aggregation-ready only when the validator
  reports `passed` for the intended manifest slice. Small canary directories
  may be validated with the same `--max-runs`, `--max-seeds`, or group filters
  used to create them, but those reports are technical validation only and not
  scientific evidence.

## 2026-08-27 - Confirmatory Processed Tables

- Decision: add `experiments/scripts/aggregate_confirmatory_results.py` to
  produce deterministic processed CSV/JSON artifacts from validated compact
  confirmatory records.
- Rationale: later statistics and figure generation need tidy run-level,
  per-agent, curve, and seed-paired comparison tables rather than repeatedly
  parsing raw compact JSON files. The aggregation step must be blocked by the
  validation gate so incomplete or mixed result directories cannot silently
  enter analysis.
- Consequence: processed artifacts use the `confirmatory_aggregate_v1` schema
  documented in `docs/confirmatory-aggregation.md`. The paired-difference table
  stores target-minus-baseline seed-paired differences against independent UCB
  where available and median/trimmed-mean differences against one-hop mean
  where available. These processed rows are inputs for later confidence
  intervals and figures, not final scientific claims.

## 2026-08-27 - Confirmatory Confidence-Interval Summaries

- Decision: add `experiments/scripts/summarize_confirmatory_results.py` to
  compute condition, curve, and paired statistical summaries from validated
  processed tables.
- Rationale: Milestone 8 requires confidence intervals and paired comparisons
  before final figures or claims. Final condition and curve summaries are
  computed across independent seeds, while paired algorithm differences should
  preserve seed matching.
- Consequence: `condition_summary.csv` and `curve_summary.csv` use
  normal-approximation 95% intervals across seeds. `paired_summary.csv` uses a
  deterministic paired percentile bootstrap with default seed `20260827` and
  `2000` resamples. Single-seed canaries produce degenerate intervals equal to
  the observed value and remain technical validation only. The statistics
  schema is `confirmatory_statistics_v1`, documented in
  `docs/confirmatory-statistics.md`.

## 2026-08-27 - Confirmatory Figure And Table Generation

- Decision: add `experiments/scripts/generate_confirmatory_figures.py` to
  generate deterministic SVG figures and compact CSV/Markdown report tables
  from Step 5 statistical summaries.
- Rationale: final figures must be regenerated from saved processed data, not
  manually edited or recomputed from raw simulator state. A standard-library SVG
  generator keeps the pipeline reproducible without adding plotting
  dependencies to the core environment.
- Consequence: figure artifacts use the `confirmatory_figures_v1` schema
  documented in `docs/confirmatory-figures.md`. Outputs include final regret,
  selected regret curves, paired regret differences, fairness, communication
  versus regret, and compact report tables. Canary or partial inputs remain
  technical validation artifacts and cannot support final scientific claims.

## 2026-08-27 - End-To-End Confirmatory Canary Pipeline

- Decision: add `experiments/scripts/run_confirmatory_canary_pipeline.py` as a
  bounded one-command wrapper for runner, validator, aggregation, statistics,
  and figure/table generation.
- Rationale: before starting any long Milestone 8 execution, the project needs
  a deterministic technical check that the frozen manifest slice can move
  through every downstream gate without manual handoff.
- Consequence: the default canary uses `--max-runs 2`, writes isolated
  `raw/`, `validation/`, `processed/`, `statistics/`, and `figures/`
  directories under the chosen output root, and records stage commands in
  `canary_pipeline_summary.json`. Canary outputs remain technical validation
  only and do not change the frozen analysis plan or support scientific
  conclusions.

## 2026-08-27 - Parallel Confirmatory Manifest Execution

- Decision: add `--workers` to
  `experiments/scripts/run_confirmatory_manifest.py`, defaulting to sequential
  execution with `--workers 1`.
- Rationale: the frozen primary matrix contains `5700` independent runs. A
  process-level worker pool shortens wall-clock execution while preserving the
  manifest expansion, per-run seeds, compact output schema, and resume
  semantics.
- Consequence: parallel execution is an operational change only. It does not
  change the frozen hypotheses, primary grid, threat model, seed set,
  algorithms, metrics, or statistical analysis. Each worker writes exactly one
  compact record or failure record for a unique run key.

## 2026-08-28 - Unattended Milestone 8 Pipeline

- Decision: add `experiments/scripts/run_milestone8_pipeline.py` as an
  unattended wrapper for the full primary Milestone 8 pipeline.
- Rationale: the project owner wants long confirmatory execution to proceed
  automatically without interactive monitoring. The wrapper runs execution,
  validation, aggregation, statistics, figures, lint, and tests in order while
  writing stage logs and machine-readable status markers.
- Consequence: the wrapper is operational only. It does not alter the frozen
  manifest, seed set, threat model, algorithms, metrics, or analysis plan. Raw
  completed records are resumed rather than overwritten; invalid partial
  records may be repaired explicitly through the runner's
  `--repair-invalid-existing` path. Derived artifacts may be regenerated with
  `--overwrite-derived`.

## 2026-08-29 - Milestone 8 Primary Result Interpretation

- Decision: add `docs/confirmatory-results.md` and `docs/limitations.md`, and
  update the README with a concise interpretation of the completed primary
  confirmatory grid.
- Rationale: before Milestone 9, the saved figures and tables need to be read
  into explicit, evidence-bounded claims. The interpretation must distinguish
  supported conclusions from unsupported generalizations and must not change
  the frozen analysis plan after seeing results.
- Consequence: current write-up claims are limited to the completed primary
  grid: `5700` completed runs, `100` seeds per primary condition, easy-gap
  Bernoulli arms, `2000` rounds, coordinated-target primary attack, truthful
  counts, value-only message corruption, and synchronous lossless one-hop
  communication. The unexecuted sensitivity group, hard-gap setting, adaptive
  attacks, arbitrary-message attacks, and reputation weighting remain outside
  the evidence base.

## 2026-08-29 - Milestone 9 Draft Report And Application Material

- Decision: create `report/paper.md`, `report/application-material.md`, and
  report-local copies of the generated confirmatory SVG figures.
- Rationale: the project now needs an externally readable research draft and
  concise application material that trace claims to validated Milestone 8
  artifacts without changing the frozen analysis plan.
- Consequence: the report frames the main contribution as a reproducible
  benchmark and bounded negative finding. It does not claim novelty,
  theoretical regret guarantees, real-world misinformation safety, adaptive
  attack robustness, arbitrary-message Byzantine robustness, or support from
  unexecuted sensitivity/hard-gap experiments. The repository is distributed
  under the MIT License.

## 2026-08-29 - Public Documentation Entry Points

- Decision: make the public repository understandable from public project
  documents by adding `docs/project-overview.md`, linking it from the README,
  and removing wording that depended on private planning notes.
- Rationale: a GitHub reader should be able to understand the research
  question, model, algorithms, attacks, metrics, results, limitations, and
  reproduction path from public project documents alone.
- Consequence: the intended public entry points are `README.md`,
  `docs/project-overview.md`, `report/paper.md`,
  `docs/confirmatory-results.md`, `docs/limitations.md`,
  `docs/experiment-plan.md`, `docs/metrics.md`, and `docs/threat-model.md`.

## 2026-08-29 - Public Artifact Reproducibility Package

- Decision: mark the confirmatory manifest as `completed_primary`, add
  `confirmatory_results_present: true`, add a locked dependency file, add a
  GitHub Actions CI workflow, and document release-artifact reproduction.
- Rationale: an external reader should be able to download archived raw
  records and derived tables, verify checksums, and regenerate processed
  tables and SVG figures without repeating the 5700-run simulation sweep.
- Consequence: raw records and large intermediate tables remain outside the Git
  commit and should be published as release or Zenodo assets under artifact
  version `v0.1.0-m8-primary`. The primary scientific grid, seed set, metrics,
  algorithms, threat model, and statistical protocol are unchanged.

## 2026-08-29 - Public Repository Reproducibility Cleanup

- Decision: publish a repository `.gitignore`, switch the project license to
  MIT, correct the author name to Francesco Roscio Ricon, add automated
  `mypy` and coverage-report checks to CI, and regenerate release checksums
  with asset basenames only.
- Rationale: external readers should be able to install, test, verify, and
  reuse the project without relying on local machine state or ambiguous
  artifact instructions.
- Consequence: the scientific protocol and saved primary results are
  unchanged. The release artifact is kept compact by excluding the largest
  derived table, `regret_curves.csv`, because it is deterministically
  regenerable from the archived raw records. Raw per-run records still cannot
  contain the original generation commit because the confirmatory sweep was run
  before public Git history was initialized; the release manifest records the
  archival source commit instead.

## 2026-08-29 - Public Positioning And v0.2 Roadmap

- Decision: add a README project-status section, replace the main public
  conclusion with a narrower evidence-bounded statement, and create
  `ROADMAP.md` separating completed `v0.1` work from planned `v0.2` work.
- Rationale: external readers should quickly understand that the current
  repository is a reproducible empirical benchmark with documented negative
  results, not a published paper or a new Byzantine-resilient algorithm.
- Consequence: no algorithms, raw data, processed results, figures, tables,
  release assets, or experimental conclusions were changed. The planned
  `v0.2` scope is explicitly limited to a future faithful literature baseline,
  broader threat model, diagnostics, ablations, pilot, confirmatory protocol,
  and separate release.
