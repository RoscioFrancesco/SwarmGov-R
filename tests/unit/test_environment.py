from __future__ import annotations

import numpy as np
import pytest

from swarmgov.environment import BernoulliBanditEnvironment, EnvironmentError


def test_deterministic_bernoulli_rewards_match_boundary_means() -> None:
    environment = BernoulliBanditEnvironment.from_means([1.0, 0.0])
    rng = np.random.default_rng(0)

    assert [environment.sample(0, rng) for _ in range(5)] == [1.0] * 5
    assert [environment.sample(1, rng) for _ in range(5)] == [0.0] * 5


def test_stochastic_bernoulli_rewards_are_reproducible_for_same_seed() -> None:
    environment = BernoulliBanditEnvironment.from_means([0.75])
    first_rng = np.random.default_rng(123)
    second_rng = np.random.default_rng(123)

    first = [environment.sample(0, first_rng) for _ in range(12)]
    second = [environment.sample(0, second_rng) for _ in range(12)]

    assert first == second


def test_environment_rejects_invalid_arm_mean() -> None:
    with pytest.raises(EnvironmentError, match="\\[0, 1\\]"):
        BernoulliBanditEnvironment.from_means([0.5, 1.2])


def test_environment_rejects_invalid_arm_index() -> None:
    environment = BernoulliBanditEnvironment.from_means([0.5])

    with pytest.raises(EnvironmentError, match="outside"):
        environment.sample(1, np.random.default_rng(0))
