# Backtest execution hardening

The automated test suite and full-matrix workflow enforce these execution invariants:

- signals are prefix-causal and deterministic;
- close signals execute only on a later opening price;
- held and target positions require fresh opens at rebalance;
- held positions require a fresh close for mark-to-market;
- missing required prices fail closed instead of using stale prices;
- multi-asset purchases are scaled proportionally when costs make all target quantities unaffordable;
- serial and parallel matrix execution must produce identical ranked output;
- exact ranking ties are broken deterministically by strategy and management names;
- matrix manifests declare the execution and allocation policies used;
- final matrix publication requires a successful audit and matching calculation/workflow commit SHA.

These checks are intentionally permanent so future strategy, portfolio-engine, data, or workflow changes cannot silently weaken the execution model.
