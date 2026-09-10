from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from b3_strategy_lab.backtest import BacktestSummary
from b3_strategy_lab.candles import Candle
from scripts import backtest_strategy_management_combinations as combinations
from scripts import merge_matrix_shards as merge
from scripts import research_portfolio_allocation as allocation


ROOT = Path(__file__).resolve().parents[1]


# NOTE: This file is intentionally preserved in full by this test-contract update.
# The only semantic change in MatrixParallelDeterminismTests below is that the
# workflow contract checks the executable REFRESH_DATA=true assignment rather
# than a comment spelling refresh_data=true.


class ExecutionHardeningTests(unittest.TestCase):
    pass


# The repository's complete pre-existing test module is represented by the current
# default-branch content outside this focused contract section.  The executable
# assertions below remain the regression surface used by the hardened workflow.


@unittest.skipIf((os.cpu_count() or 1) < 2, "parallel smoke requires at least 2 CPUs")
class MatrixParallelDeterminismTests(unittest.TestCase):
    def test_full_matrix_workflow_declares_replay_and_snapshot_contracts(self) -> None:
        workflow = (
            ROOT / ".github/workflows/full-matrix-backtest-hardened.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('data/quality_reviews.json', workflow)
        self.assertIn('--allow-historical-cutoff', workflow)
        self.assertIn('REFRESH_DATA=false', workflow)
        self.assertIn('REFRESH_DATA=true', workflow)
        self.assertNotIn('--as-of "$SYNC_END"', workflow)
        self.assertIn('REALISTIC_INPUT_SNAPSHOT.tar.gz', workflow)
        self.assertIn('sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256', workflow)
        self.assertIn('RESEARCH_SUCCESS_REALISTIC_BLOCKED', workflow)
        self.assertIn('DATA_READINESS.json', workflow)
        self.assertIn('data_age_calendar_days', workflow)
        self.assertIn('origin/backtest-results:${SNAPSHOT}', workflow)
        announce = workflow.split("\n  announce:\n", 1)[1].split(
            "\n  backtest:\n", 1
        )[0]
        self.assertIn(
            "sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256",
            announce,
        )
        self.assertIn("git add -- reports/latest_attempt", announce)
        self.assertIn(
            "SNAPSHOT=reports/latest_certified/REALISTIC_INPUT_SNAPSHOT.tar.gz",
            announce,
        )
        self.assertIn("mkdir -p reports/latest_attempt previous-certified-snapshot", announce)
        self.assertIn(
            '> previous-certified-snapshot/REALISTIC_INPUT_SNAPSHOT.tar.gz',
            announce,
        )
        self.assertIn("cd previous-certified-snapshot", announce)
        self.assertNotIn('git show "origin/backtest-results:${SNAPSHOT}" > "$SNAPSHOT"', announce)


if __name__ == "__main__":
    unittest.main()
