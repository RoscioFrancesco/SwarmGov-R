from __future__ import annotations

import numpy as np
import pytest

from swarmgov.agents.ucb import AgentError, UCB1Agent


def test_ucb_initialization_selects_every_arm_before_scoring() -> None:
    agent = UCB1Agent(
        num_arms=4,
        exploration_c=1.0,
        rng=np.random.default_rng(7),
    )

    selected: list[int] = []
    for round_index in range(1, 5):
        arm = agent.select_arm(round_index)
        selected.append(arm)
        agent.observe(arm, 1.0 if arm == 2 else 0.0)

    assert sorted(selected) == [0, 1, 2, 3]
    assert np.all(agent.counts == 1)


def test_ucb_tie_breaking_is_deterministic_under_agent_rng() -> None:
    first = UCB1Agent(num_arms=3, exploration_c=0.0, rng=np.random.default_rng(42))
    second = UCB1Agent(num_arms=3, exploration_c=0.0, rng=np.random.default_rng(42))

    first_choices = [first.select_arm(t) for t in range(1, 4)]
    second_choices = [second.select_arm(t) for t in range(1, 4)]

    assert first_choices == second_choices


def test_ucb_with_zero_exploration_prefers_best_empirical_arm() -> None:
    agent = UCB1Agent(num_arms=2, exploration_c=0.0, rng=np.random.default_rng(3))
    agent.observe(0, 1.0)
    agent.observe(1, 0.0)

    assert agent.select_arm(3) == 0


def test_ucb_can_select_from_supplied_statistics_without_mutating_local_state() -> None:
    agent = UCB1Agent(num_arms=2, exploration_c=0.0, rng=np.random.default_rng(3))
    counts = np.asarray([4, 4])
    reward_sums = np.asarray([1.0, 3.0])

    assert agent.select_arm_from_statistics(5, counts, reward_sums) == 1
    assert agent.total_observations == 0


def test_ucb_scores_require_all_arms_observed() -> None:
    agent = UCB1Agent(num_arms=2, exploration_c=1.0, rng=np.random.default_rng(0))
    agent.observe(0, 1.0)

    with pytest.raises(AgentError, match="undefined"):
        agent.ucb_scores(2)


def test_agent_rejects_invalid_rewards() -> None:
    agent = UCB1Agent(num_arms=1, exploration_c=1.0, rng=np.random.default_rng(0))

    with pytest.raises(AgentError, match="reward"):
        agent.observe(0, 2.0)
