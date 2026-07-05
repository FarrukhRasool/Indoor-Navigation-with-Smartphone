Implement only the currently approved milestone from the implementation plan.

Rules:
1. Read `CLAUDE.md` and follow its working style and coding philosophy.
2. Read `docs/implementation_plan.md` and identify the currently approved milestone.
3. Do not implement future milestones or unapproved tasks.
4. Do not modify the raw data (`data/raw/`) or the given assignment material (`assignment/`).
5. Keep the code modular: one responsibility per file in `src/`, following the module boundaries in `docs/architecture.md`. Do not mix concerns across modules.
6. Keep the code simple, readable, and student-level. Prefer clarity over cleverness.
7. If anything is uncertain, stop and ask instead of guessing.

Before editing, summarize:
- The approved milestone (and which part of it, if it has sub-steps).
- The files to create or modify.
- The expected behavior and the data structures involved.

Then implement one module (or one coherent piece) at a time, and review your own code afterwards for correctness and simplicity.

After implementation, explain exactly how to test it:
- The Python snippet or command to run (validate on Run 1 first, then generalize to all runs).
- What output confirms it works (expected counts, ranges, plots, or table shape).
- Any plot to inspect and where it is saved.
