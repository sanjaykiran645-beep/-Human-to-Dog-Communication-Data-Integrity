# Annotation policy

Automatically generated labels are never ground truth.

## Required metadata

- `path` — original recording
- `dog_id` — stable animal identifier
- `session_id` — recording session
- `label` — one of bark, growl, whine, howl, yip, grunt, other
- `annotator_id`
- `annotated_at`
- `synthetic` / `augmented` flags (must be false on the test set)

## Review

Critical training labels require independent human review. Disagreements are recorded and adjudicated. A third annotator breaks ties.

## Splits

Group by `dog_id`. Never put the same dog or session in both train and test. Augment only after splitting. Keep a frozen held-out test set.
