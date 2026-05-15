# Offline analysis

Use this area for Python-based evaluation that should not run in the production hot path.

Recommended uses:

- Compare incident-family scoring changes.
- Evaluate recall before and after topology drift.
- Analyze remediation acceptance and success rates.
- Produce benchmark summaries from exported context reports.

The production API should stay deterministic and fast. Offline analysis can be more experimental.
