from pathlib import Path


def test_temporary_bootstrap_dispatch_workflow_is_not_committed():
    """Temporary dispatch helpers must never remain on main.

    The hardened backtest publishes status by force-pushing the checked-out
    tree to ``backtest-results``. A temporary workflow file in that tree makes
    GitHub reject the push when the job token lacks ``workflows`` permission.
    """
    forbidden = Path(".github/workflows/dispatch-certified-bootstrap-once.yml")
    assert not forbidden.exists(), (
        "temporary bootstrap dispatch workflow must be removed before running "
        "the hardened backtest publication flow"
    )
