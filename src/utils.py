"""Small shared helpers for the indoor navigation project."""

VALID_RUN_IDS = (1, 2, 3, 4)

# Simple global variable: change this value to select the run to use.
ACTIVE_RUN_ID = 1


def resolve_run_id(run_id=None):
    """Return the selected run id, defaulting to the global active choice."""
    if run_id is None:
        return ACTIVE_RUN_ID
    return int(run_id)
