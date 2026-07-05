Review the current implementation against:
- `CLAUDE.md` (working style and coding philosophy)
- `docs/implementation_plan.md` and `docs/architecture.md`
- the latest approved milestone and its acceptance criteria

Check for:
1. Module boundary violations — logic in the wrong file (e.g. BLE logic in `imu.py`, filtering in `preprocessing.py`, computation inside `visualization.py`). Each file in `src/` must keep its single responsibility per `docs/architecture.md`.
2. Hardcoded, run-specific values — magic numbers or per-run assumptions that should be data-driven or exposed as parameters (e.g. a fixed threshold instead of one derived from the data, or a value that only works for Run 1).
3. Data-handling correctness — timestamp alignment and shared `t0`, missing/NaN handling, correct `t_rel`, preserved raw values where required (e.g. raw RSSI, raw acceleration), and event-driven BLE not force-resampled.
4. Domain correctness — sensor fusion, building constraints, floor transitions, and coordinate conventions behave sensibly (valid positions, correct floors, no silently wrong units or headings).
5. Code complexity or poor modularity — unnecessary abstraction, deep nesting, unclear names, or code that a fellow student could not easily read and explain.
6. Whether the approved milestone's acceptance criteria (Definition of Done) are met.

Do not implement changes unless explicitly asked.

Return:
- An overall verdict: **Pass** or **Needs changes**.
- For each check above: Pass / Fail with a one-line reason.
- Specific findings with `file:line` references and a short suggested fix.
- Confirmation of whether the milestone's acceptance criteria are met.
