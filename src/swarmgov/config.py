"""Typed configuration loading for SwarmGov-R."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from math import isfinite
from pathlib import Path
from typing import Any

import yaml

from swarmgov.seeds import DEFAULT_STREAM_NAMES, derive_component_seeds


class ConfigError(ValueError):
    """Raised when a configuration file is malformed or inconsistent."""


@dataclass(frozen=True)
class SeedConfig:
    master: int
    streams: tuple[str, ...] = DEFAULT_STREAM_NAMES


@dataclass(frozen=True)
class PopulationConfig:
    agents: int
    byzantine_fraction: float
    byzantine_placement: str


@dataclass(frozen=True)
class BanditConfig:
    arms: int
    arm_means: tuple[float, ...]
    reward_family: str


@dataclass(frozen=True)
class AlgorithmConfig:
    name: str
    parameters: Mapping[str, Any]


@dataclass(frozen=True)
class GraphConfig:
    family: str
    parameters: Mapping[str, Any]


@dataclass(frozen=True)
class CommunicationConfig:
    interval: int
    enabled: bool


@dataclass(frozen=True)
class AggregationConfig:
    method: str
    trim_count: int | None
    trim_fraction: float | None
    small_neighborhood_policy: str
    diagnostics: bool


@dataclass(frozen=True)
class AttackConfig:
    strategy: str
    target_arm: int | None
    inflated_mean: float
    diagnostics: bool


@dataclass(frozen=True)
class TopologyChangeConfig:
    enabled: bool
    change_round: int | None
    rewire_fraction: float
    preserve_connectivity: bool


@dataclass(frozen=True)
class ExperimentConfig:
    horizon: int
    seeds: tuple[int, ...]
    output_dir: str
    overwrite: bool


@dataclass(frozen=True)
class StudyConfig:
    name: str
    stage: str
    description: str
    seeds: SeedConfig
    population: PopulationConfig
    bandit: BanditConfig
    algorithm: AlgorithmConfig
    graph: GraphConfig
    communication: CommunicationConfig
    aggregation: AggregationConfig
    attack: AttackConfig
    topology_change: TopologyChangeConfig
    experiment: ExperimentConfig

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> StudyConfig:
        mapping = _require_mapping(data, "configuration")
        seeds = _parse_seeds(_get_mapping(mapping, "seeds"))
        population = _parse_population(_get_mapping(mapping, "population"))
        bandit = _parse_bandit(_get_mapping(mapping, "bandit"))
        experiment = _parse_experiment(_get_mapping(mapping, "experiment"))
        topology_change = _parse_topology_change(
            _get_mapping(mapping, "topology_change"),
            horizon=experiment.horizon,
        )

        config = cls(
            name=_get_non_empty_string(mapping, "name"),
            stage=_get_non_empty_string(mapping, "stage"),
            description=str(mapping.get("description", "")).strip(),
            seeds=seeds,
            population=population,
            bandit=bandit,
            algorithm=_parse_algorithm(_get_mapping(mapping, "algorithm")),
            graph=_parse_graph(_get_mapping(mapping, "graph")),
            communication=_parse_communication(_get_mapping(mapping, "communication")),
            aggregation=_parse_aggregation(
                _get_optional_mapping(mapping, "aggregation")
            ),
            attack=_parse_attack(_get_optional_mapping(mapping, "attack")),
            topology_change=topology_change,
            experiment=experiment,
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.bandit.arms != len(self.bandit.arm_means):
            raise ConfigError(
                "bandit.arms must match the number of entries in bandit.arm_means"
            )
        if self.population.byzantine_fraction > 0 and self.population.agents < 2:
            raise ConfigError("Byzantine runs require at least two agents")
        if self.population.byzantine_fraction == 0.0:
            if self.population.byzantine_placement != "none":
                raise ConfigError(
                    "population.byzantine_placement must be 'none' when "
                    "byzantine_fraction is 0"
                )
            if self.attack.strategy != "no_attack":
                raise ConfigError(
                    "attack.strategy must be 'no_attack' when byzantine_fraction is 0"
                )
        else:
            allowed_placements = {"random", "degree_centrality"}
            if self.population.byzantine_placement not in allowed_placements:
                raise ConfigError(
                    "population.byzantine_placement must be one of "
                    f"{sorted(allowed_placements)} when Byzantine agents are used"
                )
        if self.attack.strategy != "no_attack":
            if self.attack.target_arm is None:
                raise ConfigError(
                    f"attack.target_arm is required for {self.attack.strategy}"
                )
            if self.attack.target_arm >= self.bandit.arms:
                raise ConfigError("attack.target_arm is outside configured arms")
            optimal_arm = max(
                range(len(self.bandit.arm_means)),
                key=lambda arm: self.bandit.arm_means[arm],
            )
            if self.attack.target_arm == optimal_arm:
                raise ConfigError(
                    "attack.target_arm must be suboptimal in the core threat model"
                )
        if self.algorithm.name != "one_hop_weighted_pooling_ucb1":
            if self.aggregation.method != "mean":
                raise ConfigError(
                    "non-communication baselines must use aggregation.method='mean'"
                )
            if self.aggregation.diagnostics:
                raise ConfigError(
                    "aggregation.diagnostics requires one_hop_weighted_pooling_ucb1"
                )
            if self.topology_change.enabled:
                raise ConfigError(
                    "topology_change.enabled requires one_hop_weighted_pooling_ucb1"
                )
        if self.topology_change.enabled and self.graph.family == "complete":
            raise ConfigError(
                "dynamic topology rewiring is unsupported for complete graphs "
                "under the fixed-edge-count process"
            )
        if not self.description:
            raise ConfigError("description must not be empty")

    def resolved_dict(self) -> dict[str, Any]:
        resolved = asdict(self)
        component_seeds = derive_component_seeds(
            self.seeds.master,
            self.seeds.streams,
        )
        resolved["derived_component_seeds"] = {
            name: component_seed.to_record()
            for name, component_seed in component_seeds.items()
        }
        return resolved


def load_config(path: str | Path) -> StudyConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"configuration file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if loaded is None:
        raise ConfigError(f"configuration file is empty: {config_path}")
    return StudyConfig.from_mapping(loaded)


def _parse_seeds(data: Mapping[str, Any]) -> SeedConfig:
    master = _get_non_negative_int(data, "master")
    streams_value = data.get("streams", DEFAULT_STREAM_NAMES)
    streams = _as_non_empty_string_tuple(streams_value, "seeds.streams")
    return SeedConfig(master=master, streams=streams)


def _parse_population(data: Mapping[str, Any]) -> PopulationConfig:
    return PopulationConfig(
        agents=_get_positive_int(data, "agents"),
        byzantine_fraction=_get_fraction(data, "byzantine_fraction"),
        byzantine_placement=_get_non_empty_string(data, "byzantine_placement"),
    )


def _parse_bandit(data: Mapping[str, Any]) -> BanditConfig:
    reward_family = _get_non_empty_string(data, "reward_family")
    if reward_family != "bernoulli":
        raise ConfigError("bandit.reward_family must be 'bernoulli' for the core study")
    return BanditConfig(
        arms=_get_positive_int(data, "arms"),
        arm_means=_as_probability_tuple(data.get("arm_means"), "bandit.arm_means"),
        reward_family=reward_family,
    )


def _parse_algorithm(data: Mapping[str, Any]) -> AlgorithmConfig:
    parameters = data.get("parameters", {})
    if not isinstance(parameters, Mapping):
        raise ConfigError("algorithm.parameters must be a mapping")
    return AlgorithmConfig(
        name=_get_non_empty_string(data, "name"),
        parameters=dict(parameters),
    )


def _parse_graph(data: Mapping[str, Any]) -> GraphConfig:
    parameters = data.get("parameters", {})
    if not isinstance(parameters, Mapping):
        raise ConfigError("graph.parameters must be a mapping")
    family = _get_non_empty_string(data, "family")
    allowed_families = {"complete", "ring", "small_world", "scale_free"}
    if family not in allowed_families:
        raise ConfigError(
            f"graph.family must be one of {sorted(allowed_families)}, got {family!r}"
        )
    return GraphConfig(family=family, parameters=dict(parameters))


def _parse_communication(data: Mapping[str, Any]) -> CommunicationConfig:
    return CommunicationConfig(
        interval=_get_positive_int(data, "interval"),
        enabled=_get_bool(data, "enabled"),
    )


def _parse_aggregation(data: Mapping[str, Any]) -> AggregationConfig:
    method = str(data.get("method", "mean")).strip()
    allowed_methods = {"mean", "median", "trimmed_mean"}
    if method not in allowed_methods:
        raise ConfigError(
            f"aggregation.method must be one of {sorted(allowed_methods)}"
        )

    trim_count = _optional_non_negative_int(
        data.get("trim_count"),
        "aggregation.trim_count",
    )
    trim_fraction = _optional_fraction(
        data.get("trim_fraction"),
        "aggregation.trim_fraction",
    )
    policy = str(data.get("small_neighborhood_policy", "median_fallback")).strip()
    if policy != "median_fallback":
        raise ConfigError(
            "aggregation.small_neighborhood_policy must be 'median_fallback'"
        )
    diagnostics = data.get("diagnostics", False)
    if not isinstance(diagnostics, bool):
        raise ConfigError("aggregation.diagnostics must be a boolean")

    if method == "trimmed_mean":
        if (trim_count is None) == (trim_fraction is None):
            raise ConfigError(
                "trimmed_mean requires exactly one of aggregation.trim_count "
                "or aggregation.trim_fraction"
            )
    elif trim_count is not None or trim_fraction is not None:
        raise ConfigError("aggregation trim parameters are valid only for trimmed_mean")

    return AggregationConfig(
        method=method,
        trim_count=trim_count,
        trim_fraction=trim_fraction,
        small_neighborhood_policy=policy,
        diagnostics=diagnostics,
    )


def _parse_attack(data: Mapping[str, Any]) -> AttackConfig:
    strategy = str(data.get("strategy", "no_attack")).strip()
    allowed_strategies = {
        "no_attack",
        "constant_inflation",
        "coordinated_target",
    }
    if strategy not in allowed_strategies:
        raise ConfigError(
            f"attack.strategy must be one of {sorted(allowed_strategies)}"
        )
    target_arm = _optional_non_negative_int(data.get("target_arm"), "attack.target_arm")
    inflated_mean = _bounded_float(
        data.get("inflated_mean", 1.0),
        "attack.inflated_mean",
    )
    diagnostics_value = data.get("diagnostics", False)
    if not isinstance(diagnostics_value, bool):
        raise ConfigError("attack.diagnostics must be a boolean")
    return AttackConfig(
        strategy=strategy,
        target_arm=target_arm,
        inflated_mean=inflated_mean,
        diagnostics=diagnostics_value,
    )


def _parse_topology_change(
    data: Mapping[str, Any],
    *,
    horizon: int,
) -> TopologyChangeConfig:
    enabled = _get_bool(data, "enabled")
    change_round = data.get("change_round")
    if change_round is not None:
        if not isinstance(change_round, int) or isinstance(change_round, bool):
            raise ConfigError("topology_change.change_round must be an integer or null")
        if not 0 < change_round < horizon:
            raise ConfigError("topology_change.change_round must be inside the horizon")
    if enabled and change_round is None:
        raise ConfigError("enabled topology changes require a change_round")
    rewire_fraction = _get_fraction(data, "rewire_fraction")
    if enabled and rewire_fraction == 0.0:
        raise ConfigError("enabled topology changes require a positive rewire_fraction")
    if not enabled and (change_round is not None or rewire_fraction != 0.0):
        raise ConfigError(
            "disabled topology changes must use change_round=null and "
            "rewire_fraction=0.0"
        )
    return TopologyChangeConfig(
        enabled=enabled,
        change_round=change_round,
        rewire_fraction=rewire_fraction,
        preserve_connectivity=_get_bool(data, "preserve_connectivity"),
    )


def _parse_experiment(data: Mapping[str, Any]) -> ExperimentConfig:
    return ExperimentConfig(
        horizon=_get_positive_int(data, "horizon"),
        seeds=_as_non_negative_int_tuple(data.get("seeds"), "experiment.seeds"),
        output_dir=_get_non_empty_string(data, "output_dir"),
        overwrite=_get_bool(data, "overwrite"),
    )


def _require_mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{context} must be a mapping")
    return value


def _get_mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    if key not in data:
        raise ConfigError(f"missing required section: {key}")
    return _require_mapping(data[key], key)


def _get_optional_mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    if key not in data:
        return {}
    return _require_mapping(data[key], key)


def _get_non_empty_string(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{key} must be a non-empty string")
    return value.strip()


def _get_bool(data: Mapping[str, Any], key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ConfigError(f"{key} must be a boolean")
    return value


def _get_positive_int(data: Mapping[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ConfigError(f"{key} must be a positive integer")
    return value


def _get_non_negative_int(data: Mapping[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ConfigError(f"{key} must be a non-negative integer")
    return value


def _get_fraction(data: Mapping[str, Any], key: str) -> float:
    value = data.get(key)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ConfigError(f"{key} must be a number in [0, 1]")
    as_float = float(value)
    if not 0.0 <= as_float <= 1.0:
        raise ConfigError(f"{key} must be in [0, 1]")
    return as_float


def _optional_fraction(value: Any, context: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ConfigError(f"{context} must be a number in [0, 1] or null")
    as_float = float(value)
    if not isfinite(as_float) or not 0.0 <= as_float <= 1.0:
        raise ConfigError(f"{context} must be in [0, 1]")
    return as_float


def _optional_non_negative_int(value: Any, context: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ConfigError(f"{context} must be a non-negative integer or null")
    return value


def _bounded_float(value: Any, context: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ConfigError(f"{context} must be a finite number in [0, 1]")
    as_float = float(value)
    if not isfinite(as_float) or not 0.0 <= as_float <= 1.0:
        raise ConfigError(f"{context} must be in [0, 1]")
    return as_float


def _as_non_empty_string_tuple(value: Any, context: str) -> tuple[str, ...]:
    if not isinstance(value, list | tuple) or not value:
        raise ConfigError(f"{context} must be a non-empty sequence")
    strings: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ConfigError(f"{context} must contain only non-empty strings")
        strings.append(item.strip())
    if len(set(strings)) != len(strings):
        raise ConfigError(f"{context} must not contain duplicate names")
    return tuple(strings)


def _as_non_negative_int_tuple(value: Any, context: str) -> tuple[int, ...]:
    if not isinstance(value, list | tuple) or not value:
        raise ConfigError(f"{context} must be a non-empty sequence")
    integers: list[int] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool) or item < 0:
            raise ConfigError(f"{context} must contain only non-negative integers")
        integers.append(item)
    return tuple(integers)


def _as_probability_tuple(value: Any, context: str) -> tuple[float, ...]:
    if not isinstance(value, list | tuple) or not value:
        raise ConfigError(f"{context} must be a non-empty sequence")
    probabilities: list[float] = []
    for item in value:
        if not isinstance(item, int | float) or isinstance(item, bool):
            raise ConfigError(f"{context} must contain only numeric probabilities")
        probability = float(item)
        if not 0.0 < probability < 1.0:
            raise ConfigError(f"{context} entries must be inside (0, 1)")
        probabilities.append(probability)
    return tuple(probabilities)
