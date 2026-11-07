# Implementation plan

## P0 (done)

- Restore FFmpeg; robust decoder discovery; health diagnostics.
- Magic-based format sniff; WEBM/Opus via FFmpeg; WAV mic capture.
- Engine B: phrase mapping, always-return experimental audio unless truly ambiguous multi-intent, download, WAV response.

## P1 (partial)

- Dataset inspect/prepare/validate/train/evaluate/predict scripts exist.
- ZIP not accessible → training blocked on real dog data.
- Production classifier remains `acoustic-heuristic-v1.0.0` behind `inference.py`.

## P2 (done)

- Analyze retry, decoder hint, signal panel after success.
- Communicate playback + download.
- Isolation tests still pass.

## P3 (done in this environment)

- pytest 25 passed
- `npm run build` run as part of delivery
- Browser UI automation: not available as a dedicated suite
