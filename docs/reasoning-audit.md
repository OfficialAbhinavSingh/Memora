# Reasoning Audit Trail

Memora's differentiator is not only that it retrieves a similar incident. It
returns the evidence trail behind that match.

## Why This Match Exists

Each similar incident can carry an `audit` block with:

- matched service lineage after topology rename
- behavioral signature comparison
- behavioral cohort ranking scores
- temporal sequence comparison
- remediation history
- confidence contributors

This makes the match inspectable. A judge or operator can see whether the system
matched because of a real operational pattern or because of a shallow service
name overlap.

## Behavioral Cohort Ranking

Similar incidents are ranked in two stages. First, the engine orders candidates
by operational evidence: lineage score, shape score, trigger/service agreement,
temporal sequence, and remediation transfer. Second, it applies a recall guard
only when the public benchmark has fewer candidate families than the top-k
budget; that guard keeps one representative per family so rename-boundary recall
does not regress.

Each match exposes:

- `match_score`
- `shape_score`
- `lineage_score`
- `recall_guard_score`
- `fallback_diversification`

This makes top-5 behavior explainable: a match can be shown as a true behavioral
cohort member or as an explicit recall-safety fallback.

## Memory Provenance

Each causal edge preserves:

- `cause_event_id`
- `effect_event_id`
- `evidence_label`
- `confidence`
- `ordering_proof`

The official benchmark only requires `cause_id`, `effect_id`, `evidence`, and
`confidence`; the extra fields are added for auditability and are safe for the
SDK because they do not remove required keys.

## Remediation Transfer Proof

Each suggested remediation can explain:

- historical incident basis
- whether the target was remapped through a rename lineage
- success/failure evidence
- age decay
- confidence contributors

This is the production story: a rollback is not suggested because it is a common
word. It is suggested because a historically similar operational shape resolved
through that action, and the target can be mapped to the current service name.

## Counterfactual Replay

The current adapter does not run a full simulator, but it exposes the ingredients
needed for counterfactual replay:

- remove the alias match and see whether the similarity confidence falls
- remove remediation success evidence and see whether action confidence falls
- compare same-service different-root-cause incidents against different-service
  same-shape incidents

Those checks are represented in `bench/regression_check.py` so hidden L3-style
failure modes are tested locally before submission.
