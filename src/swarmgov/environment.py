"""Bandit environments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

import numpy as np


class EnvironmentError(ValueError):
    """Raised when an environment is configured or used incorrectly."""


@dataclass(frozen=True)
class BernoulliBanditEnvironment:
    """Stationary Bernoulli multi-armed bandit environment.

    Configuration files for the core study require means strictly inside
    ``(0, 1)``. The class itself also accepts ``0`` and ``1`` so unit tests can
    use deterministic hand-checkable rewards.
    """

    arm_means: tuple[float, ...]

    @classmethod
    def from_means(cls, arm_means: list[float] | tuple[float, ...]) -> Self:
        means = tuple(float(mean) for mean in arm_means)
        if not means:
            raise EnvironmentError("at least one arm mean is required")
        for mean in means:
            if not 0.0 <= mean <= 1.0:
                raise EnvironmentError("Bernoulli arm means must be in [0, 1]")
        return cls(arm_means=means)

    @property
    def num_arms(self) -> int:
        return len(self.arm_means)

    @property
    def optimal_arm(self) -> int:
        return int(np.argmax(np.asarray(self.arm_means, dtype=float)))

    @property
    def optimal_mean(self) -> float:
        return self.arm_means[self.optimal_arm]

    def sample(self, arm: int, rng: np.random.Generator) -> float:
        self._validate_arm(arm)
        reward = rng.binomial(n=1, p=self.arm_means[arm])
        return float(reward)

    def _validate_arm(self, arm: int) -> None:
        if not isinstance(arm, int) or isinstance(arm, bool):
            raise EnvironmentError("arm must be an integer")
        if not 0 <= arm < self.num_arms:
            raise EnvironmentError(
                f"arm index {arm} is outside valid range [0, {self.num_arms})"
            )
