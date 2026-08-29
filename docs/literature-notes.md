# SwarmGov-R Literature Notes

Status: initial inspected-source notes for Milestone 0.
Created: 2026-08-25.

These notes are not yet the complete literature review. Entries below were
seeded from primary publisher, proceedings, arXiv, or author pages inspected on
2026-08-25. Do not cite a paper in the report until the corresponding PDF has
been inspected directly and the entry has been promoted from `triage` to
`reviewed`.

## Milestone 9 Citation Inspection

Status: selected entries below are approved for the Milestone 9 draft report
only, based on direct inspection of accessible publisher, proceedings, DOI, or
arXiv sources on 2026-08-25 and 2026-08-29. This is sufficient for the current
6-8 page draft, but it is not a systematic related-work survey.

The Milestone 9 report cites:

- Lai and Robbins (1985), classical stochastic bandit lower-bound foundation;
- Auer, Cesa-Bianchi, and Fischer (2002), UCB1 finite-time analysis;
- Bubeck and Cesa-Bianchi (2012), bandit regret survey;
- Szorenyi et al. (2013), gossip-based distributed stochastic bandits;
- Kolla, Jagannathan, and Gopalan (2016), social-network collaborative
  stochastic bandits;
- Landgren, Srivastava, and Leonard (2021), cooperative UCB with running
  consensus and graph-dependent performance;
- Martinez-Rubio, Kanade, and Rebeschini (2019), decentralized cooperative
  stochastic bandits with spectral-gap dependence;
- Dubey and Pentland (2020), cooperative bandits with robust estimation under
  heavy-tailed rewards;
- Zhu, Koppel, Velasquez, and Liu (2024), Byzantine-resilient decentralized
  multi-armed bandits;
- Hu, Wang, and Chen (2026), robust decentralized MABs under corruption and
  Byzantine models;
- Yin, Chen, Ramchandran, and Bartlett (2018), coordinate-wise median and
  trimmed-mean Byzantine-robust distributed learning;
- Blanchard et al. (2017), Byzantine-tolerant gradient aggregation;
- El-Mhamdi, Guerraoui, and Rouault (2018), limitations of convergence-only
  Byzantine robustness and Bulyan;
- Watts and Strogatz (1998), small-world graph model;
- Barabasi and Albert (1999), preferential-attachment scale-free graph model;
- Xu and Klabjan (2023), dynamic/random graph decentralized bandits.

The report must still avoid detailed theorem-by-theorem claims beyond what is
recorded here and in `report/references.bib`.

## Review Fields

For each paper, record:

- bibliographic status: peer-reviewed, journal, conference, preprint, or
  unclear;
- setting and assumptions;
- algorithm or estimator;
- theorem or empirical result;
- experimental design;
- code availability;
- relevance and gap for SwarmGov-R;
- review status: triage, reading, or reviewed.

## Initial Paper Queue

### Lai and Robbins (1985), "Asymptotically Efficient Adaptive Allocation Rules"

- Source inspected: ScienceDirect/open archive page,
  https://www.sciencedirect.com/science/article/pii/0196885885900028.
- Bibliographic status: peer-reviewed journal article, Advances in Applied
  Mathematics.
- Setting: classical stochastic bandit allocation under parametric reward
  families.
- Core result: asymptotic efficiency and lower-bound foundations for adaptive
  allocation.
- Relevance: establishes baseline regret language used by later UCB work.
- Gap for project: single-agent, non-networked, no adversarial communication.
- Review status: triage.

### Auer, Cesa-Bianchi, and Fischer (2002), "Finite-time Analysis of the Multiarmed Bandit Problem"

- Source inspected: Springer DOI page,
  https://doi.org/10.1023/A:1013689704352.
- Bibliographic status: peer-reviewed journal article, Machine Learning.
- Setting: finite-time stochastic multi-armed bandits with bounded rewards.
- Algorithm or estimator: UCB-style policies, including UCB1.
- Core result: logarithmic finite-time regret with simple index policies.
- Relevance: primary source for the independent UCB1 baseline.
- Gap for project: no communication graph or Byzantine information.
- Review status: triage.

### Bubeck and Cesa-Bianchi (2012), "Regret Analysis of Stochastic and Nonstochastic Multi-armed Bandit Problems"

- Source inspected: Microsoft Research publication page,
  https://www.microsoft.com/en-us/research/publication/regret-analysis-stochastic-nonstochastic-multi-armed-bandit-problems/.
- Bibliographic status: Foundations and Trends in Machine Learning monograph.
- Setting: survey of stochastic and adversarial bandit regret analysis.
- Relevance: background reference for notation, regret definitions, and
  stochastic/adversarial distinctions.
- Gap for project: survey rather than decentralized Byzantine benchmark.
- Review status: triage.

### Szorenyi et al. (2013), "Gossip-based Distributed Stochastic Bandit Algorithms"

- Source inspected: PMLR page,
  https://proceedings.mlr.press/v28/szorenyi13.html.
- Bibliographic status: peer-reviewed conference paper, ICML 2013.
- Setting: identical arms at peers in a peer-to-peer network with limited
  random communication.
- Algorithm or estimator: gossip-based distributed stochastic bandit method.
- Core result: reported linear speedup in number of peers under the stated
  setting.
- Relevance: early decentralized stochastic bandit baseline and communication
  model.
- Gap for project: no Byzantine agents; graph process differs from fixed
  topology benchmark.
- Review status: triage.

### Kolla, Jagannathan, and Gopalan (2016), "Collaborative Learning of Stochastic Bandits over a Social Network"

- Source inspected: arXiv page, https://arxiv.org/abs/1602.08886.
- Bibliographic status: preprint with related Allerton version to verify.
- Setting: agents on a social network observing local actions and rewards.
- Algorithm or estimator: network-aware policy using graph structure,
  including dominating-set ideas.
- Core result: natural independent extensions can have poor network regret;
  graph structure can improve learning when exploited.
- Relevance: motivates topology and attacker-placement analysis.
- Gap for project: no Byzantine communication; reward-sharing model differs
  from falsified-statistics messages.
- Review status: triage.

### Landgren, Srivastava, and Leonard (2021), "Distributed Cooperative Decision Making in Multi-agent Multi-armed Bandits"

- Sources inspected: ScienceDirect article page and Leonard Lab publication
  page, https://www.sciencedirect.com/science/article/pii/S0005109820306439 and
  https://naomi.princeton.edu/publications/.
- Bibliographic status: peer-reviewed journal article, Automatica.
- Setting: multiple agents face the same MAB and cooperate over a fixed
  undirected graph.
- Algorithm or estimator: dynamic consensus estimation and coop-UCB2 variants.
- Core result: group performance close to centralized fusion under stated
  assumptions; graph indices predict performance.
- Relevance: leading candidate for decentralized mean-consensus reproduction.
- Gap for project: fixed graph and no Byzantine agents in the core model.
- Review status: triage.

### Martinez-Rubio, Kanade, and Rebeschini (2019), "Decentralized Cooperative Stochastic Bandits"

- Source inspected: NeurIPS proceedings page,
  https://papers.nips.cc/paper/8702-decentralized-cooperative-stochastic-bandits.
- Bibliographic status: peer-reviewed conference paper, NeurIPS 2019.
- Setting: K arms, N networked agents, shared reward distributions, neighbor
  communication each round.
- Algorithm or estimator: accelerated consensus with UCB adjusted for delayed
  approximate averages.
- Core result: regret bounded by centralized optimal regret plus a spectral-gap
  communication term, under the paper's assumptions.
- Relevance: modern decentralized cooperative UCB reference.
- Gap for project: no Byzantine message corruption; dynamic topology not the
  central empirical stress test.
- Review status: triage.

### Dubey and Pentland (2020), "Cooperative Multi-Agent Bandits with Heavy Tails"

- Source inspected: PMLR page,
  https://proceedings.mlr.press/v119/dubey20a.html.
- Bibliographic status: peer-reviewed conference paper, ICML 2020.
- Setting: cooperative multi-agent stochastic bandits with heavy-tailed rewards
  and network delays.
- Algorithm or estimator: MP-UCB with robust estimation through message
  passing.
- Core result: optimal regret bounds for several heavy-tailed cooperative
  settings and empirical comparisons.
- Relevance: robust estimation inside cooperative bandits; helps separate
  robustness to heavy tails from Byzantine robustness.
- Gap for project: heavy-tailed noise, not adversarial falsified messages.
- Review status: triage.

### Zhu, Koppel, Velasquez, and Liu (2024), "Byzantine-Resilient Decentralized Multi-Armed Bandits"

- Sources inspected: arXiv page and SUNY/TMLR metadata page,
  https://arxiv.org/abs/2310.07320 and
  https://researchconnect.suny.edu/en/publications/byzantine-resilient-decentralized-multi-armed-bandits/.
- Bibliographic status: listed as Transactions on Machine Learning Research,
  2024; publication venue should be verified from OpenReview/PDF before final
  citation.
- Setting: decentralized cooperative MAB with Byzantine agents sending wrong
  reward mean estimates or confidence sets.
- Algorithm or estimator: resilient UCB combining information mixing with
  truncation of inconsistent/extreme values.
- Core result: normal-agent regret no worse than classic UCB1 and better than
  non-cooperative learning when each agent has at least `3f + 1` neighbors,
  with extensions to time-varying neighbor graphs.
- Relevance: closest robust decentralized-bandit reference; likely comparison
  target.
- Gap for project: need inspect full experiments and time-varying model before
  claiming SwarmGov-R's controlled topology-change study is new.
- Review status: triage.

### Hu, Wang, and Chen (2026), "Robust Decentralized Multi-armed Bandits: From Corruption-Resilience to Byzantine-Resilience"

- Source inspected: AAAI proceedings page,
  https://ojs.aaai.org/index.php/AAAI/article/view/39344.
- Bibliographic status: peer-reviewed conference paper, AAAI 2026.
- Setting: decentralized cooperative MAB with adversarial reward corruption and
  Byzantine agents.
- Algorithm or estimator: DeMABAR with filtering/trimming style robustness.
- Core result: individual regret suffers only an additive corruption-budget
  term in the corruption model and is inherently robust in the Byzantine
  setting under stated assumptions.
- Relevance: recent robust decentralized MAB baseline to inspect before
  freezing attacks and robust aggregators.
- Gap for project: need compare assumptions, communication costs, attacker
  placement, topology families, and dynamic topology treatment.
- Review status: triage.

### Yin, Chen, Ramchandran, and Bartlett (2018), "Byzantine-Robust Distributed Learning: Towards Optimal Statistical Rates"

- Source inspected: arXiv page, https://arxiv.org/abs/1803.01498.
- Bibliographic status: ICML 2018 paper; final proceedings metadata still to
  add.
- Setting: distributed learning with Byzantine computing units.
- Algorithm or estimator: robust gradient aggregation using coordinate-wise
  median and trimmed mean.
- Core result: statistical error rates for robust distributed gradient methods.
- Relevance: methodological support for median and trimmed-mean aggregation.
- Gap for project: distributed gradient learning, not bandit communication over
  graph neighbors.
- Review status: triage.

### Blanchard et al. (2017), "Machine Learning with Adversaries: Byzantine Tolerant Gradient Descent"

- Source inspected: NeurIPS proceedings page,
  https://papers.nips.cc/paper_files/paper/2017/hash/f4b9ec30ad9f68f89b29639786cb62ef-Abstract.html.
- Bibliographic status: peer-reviewed conference paper, NeurIPS/NIPS 2017.
- Setting: distributed SGD with Byzantine workers.
- Algorithm or estimator: Krum gradient aggregation.
- Core result: linear aggregation rules cannot tolerate a single Byzantine
  worker under the paper's model; Krum satisfies a Byzantine resilience
  property.
- Relevance: motivates why ordinary averaging is fragile.
- Gap for project: gradient aggregation rather than decentralized bandit
  statistics.
- Review status: triage.

### El-Mhamdi, Guerraoui, and Rouault (2018), "The Hidden Vulnerability of Distributed Learning in Byzantium"

- Source inspected: PMLR page,
  https://proceedings.mlr.press/v80/mhamdi18a.html.
- Bibliographic status: peer-reviewed conference paper, ICML 2018.
- Setting: Byzantine distributed SGD in high-dimensional non-convex models.
- Algorithm or estimator: attack analysis and Bulyan defense.
- Core result: convergence alone may be insufficient for Byzantine resilience;
  aggregation rules can retain exploitable poisoning leeway.
- Relevance: informs attack design and caution around robustness claims.
- Gap for project: not a bandit paper and not graph-neighbor communication.
- Review status: triage.

### Watts and Strogatz (1998), "Collective Dynamics of Small-world Networks"

- Source inspected: Nature DOI page, https://doi.org/10.1038/30918.
- Bibliographic status: peer-reviewed journal article, Nature.
- Setting: graph models interpolating between regular and random networks.
- Algorithm or estimator: rewired ring-lattice small-world construction.
- Core result: high clustering with small characteristic path lengths.
- Relevance: source for small-world topology family.
- Gap for project: graph model only, no learning or adversarial agents.
- Review status: triage.

### Barabasi and Albert (1999), "Emergence of Scaling in Random Networks"

- Source inspected: Science DOI page,
  https://doi.org/10.1126/science.286.5439.509.
- Bibliographic status: peer-reviewed journal article, Science.
- Setting: growing networks with preferential attachment.
- Algorithm or estimator: scale-free network generation model.
- Core result: preferential attachment produces power-law degree patterns.
- Relevance: source for scale-free topology family and hub-sensitivity tests.
- Gap for project: graph model only, no learning or Byzantine behavior.
- Review status: triage.

### Xu and Klabjan (2023), "Decentralized Randomly Distributed Multi-agent Multi-armed Bandit with Heterogeneous Rewards"

- Source inspected: arXiv page, https://arxiv.org/abs/2306.05579.
- Bibliographic status: arXiv preprint, noted as NeurIPS 2023 spotlight on the
  source page; proceedings citation to verify.
- Setting: decentralized multi-agent MAB with heterogeneous rewards and
  time-dependent random graphs.
- Algorithm or estimator: averaging-based consensus and UCB-type method for
  random graph sequences.
- Core result: logarithmic instance-dependent regret and graph-randomness
  accounting under stated assumptions.
- Relevance: dynamic-graph MAB reference for checking novelty of the
  topology-change extension.
- Gap for project: random graph process and heterogeneous rewards differ from
  controlled Byzantine value-corruption benchmark.
- Review status: triage.

## Immediate Reading Priorities

1. Fully read Auer et al. (2002) before implementing UCB1.
2. Fully read Landgren et al. (2021) and Martinez-Rubio et al. (2019) before
   implementing mean-consensus UCB.
3. Fully read Zhu et al. (2024), Hu et al. (2026), and Yin et al. (2018)
   before implementing robust aggregation or attack comparisons.
4. Verify whether SwarmGov-R's one-time controlled topology rewiring is a true
   empirical extension relative to Zhu et al. (2024), Hu et al. (2026), and Xu
   and Klabjan (2023).
