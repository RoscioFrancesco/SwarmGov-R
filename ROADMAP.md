# Roadmap

Status: public planning document for work after the completed `v0.1` research
benchmark.

This roadmap distinguishes completed repository functionality from planned
future work. Items in `v0.2` are not implemented in `v0.1`.

## v0.1 - Completed

- Reproducible empirical benchmark for decentralized multi-armed bandits under
  controlled Byzantine value corruption.
- Deterministic simulation pipeline with seeded environment, graph, agent,
  attack, simulation, and analysis streams.
- Unit, integration, regression, lint, type-checking, coverage, validation,
  and canary checks.
- Completed primary confirmatory experiments with `5700/5700` valid runs and
  zero failed runs.
- Public result artifacts, checksums, artifact manifest, release notes, and
  reproduction instructions.
- Documented limitations, negative results, threat model, metrics, and
  unsupported claims.

## v0.2 - Planned

- Define the design contract for a faithful Byzantine-Resilient UCB baseline.
- Implement the baseline faithfully against the selected paper.
- Test implementation components against the paper equations.
- Reproduce the minimal experiments from the original reference work.
- Extend the threat model to include manipulation of both reported values and
  reported counts.
- Add diagnostics for local Byzantine exposure and node degree.
- Compare the literature baseline with independent UCB, one-hop mean, one-hop
  median, and one-hop trimmed mean under controlled matched conditions.
- Ablate consistency filtering, trimming, confidence terms, and topology
  assumptions.
- Run a reduced pilot before any confirmatory execution.
- Define a separate frozen confirmatory protocol for `v0.2`.
- Publish a new release for `v0.2` without modifying the `v0.1` release.
