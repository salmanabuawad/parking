# Israel Traffic and Parking Violation Reference

This package is a machine-readable **engineering draft** for software that checks whether a vehicle is likely committing a traffic or parking violation in Israel.

## Included files
- `israel_violation_reference.json`
- `israel_violation_reference.yaml`
- `README.md`

## Important limitation
This session could not perform live verification against official Israeli legal sources.
Therefore this package is **not a legal certification pack** and must be validated before operational enforcement.

## What this pack is good for
- Designing the rule engine
- Defining evidence requirements
- Separating sign-based, marking-based, and permit-based rules
- Structuring municipal overrides
- Building review workflows and audit trails

## What still must be validated before production
1. Exact regulation sections and legal wording
2. Current Israeli sign catalog semantics
3. Distance thresholds near junctions / crosswalks / other protected areas
4. Municipal by-laws, resident permits, paid parking hours, local exemptions
5. Penalty mappings and enforcement authority rules
6. Temporary and city-specific traffic orders

## Recommended architecture
1. Scene understanding: vehicle detection, tracking, plate OCR, sign and marking detection
2. Legal reference layer: rules, signs, markings, municipal overlays, exceptions
3. Decision layer: predicates + external permit/payment checks + human review policy
4. Audit layer: evidence package, reasoning trace, immutable logs

## Minimum evidence policy
Never output `confirmed_violation` unless:
- the restriction basis is visible or otherwise provable,
- vehicle position/state is reliable,
- time and location are known,
- all required external checks are resolved,
- no material exception remains open.

## Suggested next work
- Validate all rules against current official Israeli sources
- Add exact sign codes and legal citations
- Add municipality-by-municipality parking zone overlays
- Add evidence templates per rule
