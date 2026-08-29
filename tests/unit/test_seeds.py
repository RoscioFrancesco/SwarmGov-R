from __future__ import annotations

import numpy as np
import pytest

from swarmgov.seeds import derive_component_seeds, derive_run_component_seeds, make_rngs


def test_component_seed_derivation_is_reproducible() -> None:
    first = derive_component_seeds(1234)
    second = derive_component_seeds(1234)

    assert first.keys() == second.keys()
    assert first["environment"].state == second["environment"].state
    assert first["environment"].spawn_key == second["environment"].spawn_key

    first_draws = first["environment"].rng().integers(0, 1000, size=5)
    second_draws = second["environment"].rng().integers(0, 1000, size=5)
    np.testing.assert_array_equal(first_draws, second_draws)


def test_component_streams_are_independent_by_construction() -> None:
    seeds = derive_component_seeds(1234)

    assert seeds["environment"].spawn_key != seeds["graph"].spawn_key
    assert seeds["environment"].state != seeds["graph"].state


def test_rng_factory_reconstructs_named_streams() -> None:
    rngs = make_rngs(99, ("environment", "graph"))

    assert tuple(rngs) == ("environment", "graph")
    assert all(isinstance(rng, np.random.Generator) for rng in rngs.values())


def test_seed_derivation_rejects_duplicate_stream_names() -> None:
    with pytest.raises(ValueError, match="unique"):
        derive_component_seeds(1, ("environment", "environment"))


def test_seed_derivation_rejects_negative_master_seed() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        derive_component_seeds(-1)


def test_run_component_seed_derivation_uses_run_seed() -> None:
    first = derive_run_component_seeds(1234, 0)
    second = derive_run_component_seeds(1234, 0)
    different_run = derive_run_component_seeds(1234, 1)

    assert first["environment"].state == second["environment"].state
    assert first["environment"].spawn_key != different_run["environment"].spawn_key
    assert first["environment"].state != different_run["environment"].state
