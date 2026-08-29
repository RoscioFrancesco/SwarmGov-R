"""Upper-confidence-bound agents."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class AgentError(ValueError):
    """Raised when an agent is configured or updated incorrectly."""


@dataclass
class UCB1Agent:
    """Independent UCB1 learner.

    The agent only observes its own selected arms and rewards. It has no access
    to true arm means, graph neighbors, or messages.
    """

    num_arms: int
    exploration_c: float
    rng: np.random.Generator

    def __post_init__(self) -> None:
        if self.num_arms <= 0:
            raise AgentError("num_arms must be positive")
        if not np.isfinite(self.exploration_c) or self.exploration_c < 0:
            raise AgentError("exploration_c must be a non-negative finite number")
        self.counts = np.zeros(self.num_arms, dtype=np.int64)
        self.reward_sums = np.zeros(self.num_arms, dtype=float)

    @property
    def total_observations(self) -> int:
        return int(self.counts.sum())

    @property
    def empirical_means(self) -> np.ndarray:
        means = np.zeros(self.num_arms, dtype=float)
        observed = self.counts > 0
        means[observed] = self.reward_sums[observed] / self.counts[observed]
        return means

    def select_arm(self, round_index: int) -> int:
        if round_index <= 0:
            raise AgentError("round_index must be one-based and positive")

        untried = np.flatnonzero(self.counts == 0)
        if len(untried) > 0:
            return int(self.rng.choice(untried))

        scores = self.ucb_scores(round_index)
        return _rng_argmax(scores, self.rng)

    def select_arm_from_statistics(
        self,
        round_index: int,
        counts: np.ndarray,
        reward_sums: np.ndarray,
    ) -> int:
        """Select using supplied sufficient statistics without mutating state."""

        if round_index <= 0:
            raise AgentError("round_index must be one-based and positive")
        validated_counts, validated_sums = _validate_statistics(
            counts,
            reward_sums,
            self.num_arms,
        )
        untried = np.flatnonzero(validated_counts == 0)
        if len(untried) > 0:
            return int(self.rng.choice(untried))
        scores = ucb_scores_from_statistics(
            round_index,
            validated_counts,
            validated_sums,
            self.exploration_c,
        )
        return _rng_argmax(scores, self.rng)

    def observe(self, arm: int, reward: float) -> None:
        self._validate_arm(arm)
        if not np.isfinite(reward) or not 0.0 <= reward <= 1.0:
            raise AgentError("reward must be a finite value in [0, 1]")
        self.counts[arm] += 1
        self.reward_sums[arm] += float(reward)

    def ucb_scores(self, round_index: int) -> np.ndarray:
        if round_index <= 0:
            raise AgentError("round_index must be one-based and positive")
        if np.any(self.counts == 0):
            raise AgentError("UCB scores are undefined until every arm is observed")
        bonus = self.exploration_c * np.sqrt(np.log(round_index) / self.counts)
        return self.empirical_means + bonus

    def preferred_arm(self) -> int:
        """Return the empirically best arm, breaking ties with the agent RNG."""

        return _rng_argmax(self.empirical_means, self.rng)

    def preferred_arm_from_statistics(
        self,
        counts: np.ndarray,
        reward_sums: np.ndarray,
    ) -> int:
        validated_counts, validated_sums = _validate_statistics(
            counts,
            reward_sums,
            self.num_arms,
        )
        means = np.zeros(self.num_arms, dtype=float)
        observed = validated_counts > 0
        means[observed] = validated_sums[observed] / validated_counts[observed]
        return _rng_argmax(means, self.rng)

    def snapshot(self) -> dict[str, object]:
        return {
            "counts": self.counts.astype(int).tolist(),
            "reward_sums": self.reward_sums.astype(float).tolist(),
            "empirical_means": self.empirical_means.astype(float).tolist(),
            "total_observations": self.total_observations,
        }

    def _validate_arm(self, arm: int) -> None:
        if not isinstance(arm, int) or isinstance(arm, bool):
            raise AgentError("arm must be an integer")
        if not 0 <= arm < self.num_arms:
            raise AgentError(
                f"arm index {arm} is outside valid range [0, {self.num_arms})"
            )


def _rng_argmax(values: np.ndarray, rng: np.random.Generator) -> int:
    max_value = np.max(values)
    candidates = np.flatnonzero(np.isclose(values, max_value))
    return int(rng.choice(candidates))


def ucb_scores_from_statistics(
    round_index: int,
    counts: np.ndarray,
    reward_sums: np.ndarray,
    exploration_c: float,
) -> np.ndarray:
    if round_index <= 0:
        raise AgentError("round_index must be one-based and positive")
    if not np.isfinite(exploration_c) or exploration_c < 0:
        raise AgentError("exploration_c must be a non-negative finite number")
    validated_counts, validated_sums = _validate_statistics(
        counts,
        reward_sums,
        len(counts),
    )
    if np.any(validated_counts == 0):
        raise AgentError("UCB scores are undefined until every arm is observed")
    empirical_means = validated_sums / validated_counts
    bonus = exploration_c * np.sqrt(np.log(round_index) / validated_counts)
    return empirical_means + bonus


def _validate_statistics(
    counts: np.ndarray,
    reward_sums: np.ndarray,
    num_arms: int,
) -> tuple[np.ndarray, np.ndarray]:
    validated_counts = np.asarray(counts, dtype=np.int64)
    validated_sums = np.asarray(reward_sums, dtype=float)
    if validated_counts.shape != (num_arms,) or validated_sums.shape != (num_arms,):
        raise AgentError("counts and reward_sums must match num_arms")
    if np.any(validated_counts < 0):
        raise AgentError("counts must be non-negative")
    if np.any(~np.isfinite(validated_sums)) or np.any(validated_sums < 0):
        raise AgentError("reward_sums must be finite and non-negative")
    if np.any(validated_sums > validated_counts):
        raise AgentError("reward_sums cannot exceed counts for Bernoulli rewards")
    return validated_counts, validated_sums
