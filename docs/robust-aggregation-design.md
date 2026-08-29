# Robust Aggregation Design

Status: Milestone 5 design, implemented as heuristic one-hop UCB baselines.
Created: 2026-08-25.

## Scope

Milestone 5 adds robust one-hop aggregation baselines for the existing
decentralized communication model:

- count-weighted mean, preserving the Milestone 3 behaviour;
- unweighted per-source median;
- unweighted per-source symmetric trimmed mean.

These methods are empirical robust-aggregation baselines. They are not claimed
to be theoretically Byzantine-safe, and the robust UCB confidence rule below is
not claimed to satisfy standard UCB regret guarantees.

## Input Construction

For each receiver and each arm, the aggregator constructs source-level
empirical estimates from authoritative `counts` and `reward_sums`:

```text
estimate = reward_sum / count
```

The receiver's own local estimate is included exactly once when its local count
is positive. Each direct neighbour contributes at most one latest message
estimate for that arm when the message count is positive. Arms with count zero
are unavailable and are excluded; they are not treated as mean zero.

Aggregators never trust a separately transmitted empirical mean field. The
typed `Message` object may expose derived empirical means for records, but
aggregation derives estimates from counts and reward sums.

The aggregator is stateless across rounds. It never adds a cumulative neighbour
snapshot permanently to local observations.

## Mean Baseline

The `mean` aggregator preserves the previous one-hop weighted pooling
semantics:

```text
effective_count[a] = local_count[a] + sum_neighbour count_j[a]
aggregate_sum[a] = local_reward_sum[a] + sum_neighbour reward_sum_j[a]
aggregate_mean[a] = aggregate_sum[a] / effective_count[a]
```

This is not robust to extreme Byzantine reward-sum corruption. It remains as
the non-robust regression baseline.

## Median Aggregator

The `median` aggregator collects one empirical mean per valid source and
computes the NumPy-style median. With an even number of valid estimates, the
median is the average of the two middle sorted values.

Fallback behaviour:

- zero valid estimates: the arm remains unobserved with count `0` and sum `0`;
- one valid estimate: that estimate is returned unchanged.

A source with a larger truthful count still contributes only one median value.
This prevents count size from becoming extra median voting weight under the
current controlled threat model.

## Trimmed-Mean Aggregator

The `trimmed_mean` aggregator collects one empirical mean per valid source,
sorts values, removes a symmetric number from each tail, and averages the
remaining values.

Exactly one trimming configuration is allowed:

- `trim_count`: fixed number removed from each tail; or
- `trim_fraction`: converted per arm as
  `floor(trim_fraction * valid_source_count)`.

The small-neighbourhood policy is `median_fallback`. If requested trimming
would remove every value, the aggregator computes the median instead and emits
diagnostic metadata marking the fallback. It does not silently fall back to the
ordinary mean.

## UCB Effective-Support Rule

For `median` and `trimmed_mean`, the robust aggregate mean is converted back to
decision statistics for the existing UCB scorer using source-level effective
support:

```text
effective_count[a] = number of source estimates used for the robust aggregate
effective_reward_sum[a] = aggregate_mean[a] * effective_count[a]
```

For median, the source estimates used are all valid source estimates. For
trimmed mean, the source estimates used are the retained estimates after
trimming; if median fallback occurs, all valid source estimates are counted as
the fallback support.

This rule deliberately ignores per-source sample-count magnitude in the robust
confidence term. It is conservative when neighbours have very different sample
counts: a neighbour with many truthful samples improves its source estimate,
but it does not make the receiver as confident as if every sample were directly
pooled. This avoids giving Byzantine senders extra robust-aggregation influence
through large declared support, and it keeps the median/trimmed methods aligned
with the per-source robust estimators.

Because this is a heuristic robust one-hop UCB baseline, not a paper-faithful
algorithm with inspected proof assumptions, no standard UCB regret guarantee is
claimed.

## Diagnostics

When aggregation diagnostics are enabled, each receiver-round aggregation
records:

- number of valid sources per arm;
- aggregate mean per arm;
- effective support/count per arm;
- number of values trimmed from each tail;
- whether median fallback occurred per arm;
- number of invalid messages rejected.

The current validation policy raises on malformed or round-incompatible
messages, so `invalid_messages_rejected` is expected to remain zero for normal
runs.
