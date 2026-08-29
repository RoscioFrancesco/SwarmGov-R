"""Deterministic random seed derivation for reproducible experiments."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

DEFAULT_STREAM_NAMES = (
    "environment",
    "graph",
    "agents",
    "attack",
    "simulation",
    "analysis",
)


@dataclass(frozen=True)
class ComponentSeed:
    """Serializable metadata for a deterministic component RNG stream."""

    name: str
    entropy: int
    spawn_key: tuple[int, ...]
    state: tuple[int, ...]

    def seed_sequence(self) -> np.random.SeedSequence:
        return np.random.SeedSequence(self.entropy, spawn_key=self.spawn_key)

    def rng(self) -> np.random.Generator:
        return np.random.default_rng(self.seed_sequence())

    def to_record(self) -> dict[str, object]:
        return {
            "entropy": self.entropy,
            "spawn_key": list(self.spawn_key),
            "state": list(self.state),
        }


def derive_component_seeds(
    master_seed: int,
    stream_names: Iterable[str] = DEFAULT_STREAM_NAMES,
    *,
    state_words: int = 4,
) -> dict[str, ComponentSeed]:
    """Derive stable child seed streams from a master seed.

    The returned records are ordered by ``stream_names``. Reconstructing a
    ``ComponentSeed`` with the same entropy and spawn key yields the same RNG
    sequence without mutating shared global state.
    """

    master = _seed_sequence_from_master(master_seed)
    return _derive_children(
        parent=master,
        entropy=master_seed,
        stream_names=stream_names,
        state_words=state_words,
    )


def derive_run_component_seeds(
    master_seed: int,
    run_seed: int,
    stream_names: Iterable[str] = DEFAULT_STREAM_NAMES,
    *,
    state_words: int = 4,
) -> dict[str, ComponentSeed]:
    """Derive component streams for one run seed under a master seed."""

    _seed_sequence_from_master(master_seed)
    if not isinstance(run_seed, int) or isinstance(run_seed, bool) or run_seed < 0:
        raise ValueError("run_seed must be a non-negative integer")
    parent = np.random.SeedSequence(master_seed, spawn_key=(run_seed,))
    return _derive_children(
        parent=parent,
        entropy=master_seed,
        stream_names=stream_names,
        state_words=state_words,
    )


def _derive_children(
    *,
    parent: np.random.SeedSequence,
    entropy: int,
    stream_names: Iterable[str],
    state_words: int,
) -> dict[str, ComponentSeed]:
    names = _validate_stream_names(stream_names)
    if state_words <= 0:
        raise ValueError("state_words must be positive")

    children = parent.spawn(len(names))
    return {
        name: ComponentSeed(
            name=name,
            entropy=entropy,
            spawn_key=tuple(int(part) for part in child.spawn_key),
            state=tuple(int(part) for part in child.generate_state(state_words)),
        )
        for name, child in zip(names, children, strict=True)
    }


def make_rngs(
    master_seed: int,
    stream_names: Iterable[str] = DEFAULT_STREAM_NAMES,
) -> dict[str, np.random.Generator]:
    component_seeds = derive_component_seeds(master_seed, stream_names)
    return {
        name: component_seed.rng()
        for name, component_seed in component_seeds.items()
    }


def _seed_sequence_from_master(master_seed: int) -> np.random.SeedSequence:
    if not isinstance(master_seed, int) or isinstance(master_seed, bool):
        raise ValueError("master_seed must be an integer")
    if master_seed < 0:
        raise ValueError("master_seed must be non-negative")
    return np.random.SeedSequence(master_seed)


def _validate_stream_names(stream_names: Iterable[str]) -> tuple[str, ...]:
    names = tuple(stream_names)
    if not names:
        raise ValueError("at least one stream name is required")
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("stream names must be non-empty strings")
    normalized = tuple(name.strip() for name in names)
    if len(set(normalized)) != len(normalized):
        raise ValueError("stream names must be unique")
    return normalized
