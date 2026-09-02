from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one replacement target, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1) Realistic finalist gate: recompute curve-derived risk statistics and reconcile tax ledger.
path = "scripts/validate_matrix_top_realistic.py"
replace_once(path, "import math\nimport subprocess\n", "import math\nimport statistics\nimport subprocess\n")

old = '''def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _artifact_binding_issues(
'''
new = '''def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _curve_recalculated_metrics(
    curve: list[dict[str, str]],
    *,
    initial_cash: float,
) -> dict[str, float]:
    if not math.isfinite(initial_cash) or initial_cash <= 0:
        raise ValueError("initial cash must be finite and positive")
    if len(curve) < 2:
        raise ValueError("curve must contain at least two sessions")

    dates: list[datetime] = []
    equities: list[float] = []
    for row in curve:
        current = datetime.fromisoformat(str(row["date"]))
        equity = float(row["equity"])
        if not math.isfinite(equity) or equity <= 0:
            raise ValueError("curve equity must be finite and positive")
        if dates and current <= dates[-1]:
            raise ValueError("curve dates must be strictly increasing")
        dates.append(current)
        equities.append(equity)

    returns = [
        equities[index] / equities[index - 1] - 1.0
        for index in range(1, len(equities))
    ]
    years = max(
        (dates[-1] - dates[0]).total_seconds() / 31_557_600.0,
        1 / 365.25,
    )
    periods_per_year = (len(equities) - 1) / years
    if len(returns) >= 2:
        return_std = statistics.stdev(returns)
        annual_volatility = return_std * math.sqrt(periods_per_year)
        sharpe = (
            statistics.mean(returns) / return_std * math.sqrt(periods_per_year)
            if return_std > 0
            else 0.0
        )
    else:
        annual_volatility = 0.0
        sharpe = 0.0

    year_ends: dict[int, float] = {}
    for current, equity in zip(dates, equities):
        year_ends[current.year] = equity
    prior_equity = initial_cash
    yearly_returns: list[float] = []
    for end_equity in year_ends.values():
        yearly_returns.append(end_equity / prior_equity - 1.0)
        prior_equity = end_equity

    return {
        "annual_volatility": annual_volatility,
        "sharpe": sharpe,
        "average_annual_return": (
            statistics.mean(yearly_returns) if yearly_returns else 0.0
        ),
    }


def _artifact_binding_issues(
'''
replace_once(path, old, new)

replace_once(
    path,
    '''    cash_path: Path,\n) -> list[str]:\n''',
    '''    cash_path: Path,\n    tax_path: Path,\n) -> list[str]:\n''',
)
replace_once(
    path,
    '''        cash = _csv_rows(cash_path)\n    except (OSError, csv.Error, UnicodeError, ValueError):\n''',
    '''        cash = _csv_rows(cash_path)\n        tax = _csv_rows(tax_path)\n    except (OSError, csv.Error, UnicodeError, ValueError):\n''',
)

old = '''    except (KeyError, TypeError, ValueError):
        issues.append("invalid_cash_ledger")
    return sorted(set(issues))
'''
new = '''    except (KeyError, TypeError, ValueError):
        issues.append("invalid_cash_ledger")

    try:
        recomputed = _curve_recalculated_metrics(
            curve,
            initial_cash=float(payload["initial_cash"]),
        )
        metric_issue_names = {
            "annual_volatility": "curve_annual_volatility_mismatch",
            "sharpe": "curve_sharpe_mismatch",
            "average_annual_return": "curve_average_annual_return_mismatch",
        }
        for field, issue_name in metric_issue_names.items():
            actual = float(payload[field])
            expected = float(recomputed[field])
            if not (
                math.isfinite(actual)
                and math.isfinite(expected)
                and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-10)
            ):
                issues.append(issue_name)
    except (KeyError, TypeError, ValueError, OverflowError, statistics.StatisticsError):
        issues.append("invalid_curve_metrics")

    try:
        ledger_irrf = sum(float(row.get("irrf_withheld_month", 0.0) or 0.0) for row in tax)
        ledger_tax_due = sum(float(row["tax_due"]) for row in tax)
        outstanding = float(payload["outstanding_accrued_tax_liability"])
        ordinary_paid = float(payload["ordinary_income_tax_paid"])
        if not all(math.isfinite(value) for value in (ledger_irrf, ledger_tax_due, outstanding, ordinary_paid)):
            raise ValueError("non-finite tax reconciliation value")
        expected_darf_paid = ledger_tax_due - outstanding
        if expected_darf_paid < -1e-8:
            issues.append("tax_ledger_outstanding_liability_exceeds_accrual")
        else:
            expected_darf_paid = max(0.0, expected_darf_paid)
            expected_ordinary_paid = ledger_irrf + expected_darf_paid
            if not math.isclose(
                ordinary_paid,
                expected_ordinary_paid,
                rel_tol=1e-9,
                abs_tol=1e-8,
            ):
                issues.append("tax_ledger_ordinary_income_tax_paid_mismatch")
            if "ordinary_irrf_withheld" in payload and not math.isclose(
                float(payload["ordinary_irrf_withheld"]),
                ledger_irrf,
                rel_tol=1e-9,
                abs_tol=1e-8,
            ):
                issues.append("tax_ledger_irrf_withheld_mismatch")
            if "darf_paid" in payload and not math.isclose(
                float(payload["darf_paid"]),
                expected_darf_paid,
                rel_tol=1e-9,
                abs_tol=1e-8,
            ):
                issues.append("tax_ledger_darf_paid_mismatch")
    except (KeyError, TypeError, ValueError):
        issues.append("invalid_tax_ledger")

    return sorted(set(issues))
'''
replace_once(path, old, new)

replace_once(
    path,
    '''        cash_path=cash,\n    )\n''',
    '''        cash_path=cash,\n        tax_path=tax,\n    )\n''',
)

# 2) Recovery: bind the entire calculation filesystem to the shards' original commit.
path = ".github/workflows/recover-backtest-merge-hardened.yml"
old = '''          import json
          from pathlib import Path
'''
new = '''          import json, os
          from pathlib import Path
'''
replace_once(path, old, new)

old = '''          if len(source_commits) != 1 or None in source_commits:
              raise SystemExit(f"proveniência inconsistente entre shards: {source_commits}")
          print(f"shards={len(csvs)} calculation_sha={next(iter(source_commits))}")
          PY

      - name: Consolidar
        run: |
          python scripts/merge_matrix_shards.py \\
'''
new = '''          if len(source_commits) != 1 or None in source_commits:
              raise SystemExit(f"proveniência inconsistente entre shards: {source_commits}")
          calculation_sha = str(next(iter(source_commits)))
          with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as env:
              env.write(f"CALCULATION_SHA={calculation_sha}\\n")
          print(f"shards={len(csvs)} calculation_sha={calculation_sha}")
          PY

      - name: Fixar ambiente no commit original dos shards
        run: |
          set -euo pipefail
          SOURCE_DIR="$RUNNER_TEMP/recovery-source"
          rm -rf "$SOURCE_DIR"
          git cat-file -e "${CALCULATION_SHA}^{commit}"
          git worktree add --detach "$SOURCE_DIR" "$CALCULATION_SHA"
          mkdir -p "$SOURCE_DIR/reports/shards"
          cp -a reports/shards/. "$SOURCE_DIR/reports/shards/"
          (
            cd "$SOURCE_DIR"
            python -m py_compile \\
              scripts/merge_matrix_shards.py \\
              scripts/audit_matrix_results.py \\
              scripts/audit_backtest_readiness.py
          )
          echo "SOURCE_DIR=$SOURCE_DIR" >> "$GITHUB_ENV"

      - name: Consolidar
        run: |
          set -euo pipefail
          cd "$SOURCE_DIR"
          python scripts/merge_matrix_shards.py \\
'''
replace_once(path, old, new)

replace_once(
    path,
    '''      - name: Auditar\n        run: |\n          set -euo pipefail\n          python scripts/audit_matrix_results.py \\\n''',
    '''      - name: Auditar\n        run: |\n          set -euo pipefail\n          cd "$SOURCE_DIR"\n          python scripts/audit_matrix_results.py \\\n''',
)
replace_once(
    path,
    '''      - name: Preparar latest recuperado\n        run: |\n          set -euo pipefail\n          PUBLISH_DIR="$RUNNER_TEMP/backtest-results-publish"\n''',
    '''      - name: Preparar latest recuperado\n        run: |\n          set -euo pipefail\n          cd "$SOURCE_DIR"\n          PUBLISH_DIR="$RUNNER_TEMP/backtest-results-publish"\n''',
)

old = '''          if [ -f "$PRESERVED_DIR/REALISTIC_INPUT_SNAPSHOT.tar.gz" ]; then
            (
              cd "$PRESERVED_DIR"
              sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256
            )
          fi
'''
new = '''          snapshot_exists=false
          checksum_exists=false
          [ -f "$PRESERVED_DIR/REALISTIC_INPUT_SNAPSHOT.tar.gz" ] && snapshot_exists=true
          [ -f "$PRESERVED_DIR/REALISTIC_INPUT_SNAPSHOT.sha256" ] && checksum_exists=true
          if [ "$snapshot_exists" != "$checksum_exists" ]; then
            echo "::error::snapshot/checksum realista assimétricos em backtest-results"
            exit 1
          fi
          if [ "$snapshot_exists" = "true" ]; then
            (
              cd "$PRESERVED_DIR"
              sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256
            )
          fi
'''
replace_once(path, old, new)

# 3) Full matrix publication: never silently discard an asymmetric persisted pair.
path = ".github/workflows/full-matrix-backtest-hardened.yml"
old = '''          if git cat-file -e "origin/backtest-results:${SNAPSHOT}" 2>/dev/null \\
            && git cat-file -e "origin/backtest-results:${CHECKSUM}" 2>/dev/null; then
            git show "origin/backtest-results:${SNAPSHOT}" > "$SNAPSHOT"
            git show "origin/backtest-results:${CHECKSUM}" > "$CHECKSUM"
            (
              cd reports/latest_backtest
              sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256
            )
          fi
'''
new = '''          snapshot_exists=false
          checksum_exists=false
          git cat-file -e "origin/backtest-results:${SNAPSHOT}" 2>/dev/null && snapshot_exists=true
          git cat-file -e "origin/backtest-results:${CHECKSUM}" 2>/dev/null && checksum_exists=true
          if [ "$snapshot_exists" != "$checksum_exists" ]; then
            echo "::error::snapshot/checksum realista assimétricos em backtest-results"
            exit 1
          fi
          if [ "$snapshot_exists" = "true" ]; then
            git show "origin/backtest-results:${SNAPSHOT}" > "$SNAPSHOT"
            git show "origin/backtest-results:${CHECKSUM}" > "$CHECKSUM"
            (
              cd reports/latest_backtest
              sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256
            )
          fi
'''
replace_once(path, old, new)

old = '''          if git cat-file -e "origin/backtest-results:${PREVIOUS_SNAPSHOT}" 2>/dev/null \\
            && git cat-file -e "origin/backtest-results:${PREVIOUS_CHECKSUM}" 2>/dev/null; then
            git show "origin/backtest-results:${PREVIOUS_SNAPSHOT}" \\
              > previous-realistic-snapshot/REALISTIC_INPUT_SNAPSHOT.tar.gz
            git show "origin/backtest-results:${PREVIOUS_CHECKSUM}" \\
              > previous-realistic-snapshot/REALISTIC_INPUT_SNAPSHOT.sha256
            (
              cd previous-realistic-snapshot
              sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256
            )
          fi
'''
new = '''          previous_snapshot_exists=false
          previous_checksum_exists=false
          git cat-file -e "origin/backtest-results:${PREVIOUS_SNAPSHOT}" 2>/dev/null && previous_snapshot_exists=true
          git cat-file -e "origin/backtest-results:${PREVIOUS_CHECKSUM}" 2>/dev/null && previous_checksum_exists=true
          if [ "$previous_snapshot_exists" != "$previous_checksum_exists" ]; then
            echo "::error::snapshot/checksum realista assimétricos em backtest-results"
            exit 1
          fi
          if [ "$previous_snapshot_exists" = "true" ]; then
            git show "origin/backtest-results:${PREVIOUS_SNAPSHOT}" \\
              > previous-realistic-snapshot/REALISTIC_INPUT_SNAPSHOT.tar.gz
            git show "origin/backtest-results:${PREVIOUS_CHECKSUM}" \\
              > previous-realistic-snapshot/REALISTIC_INPUT_SNAPSHOT.sha256
            (
              cd previous-realistic-snapshot
              sha256sum -c REALISTIC_INPUT_SNAPSHOT.sha256
            )
          fi
'''
replace_once(path, old, new)

# 4) Regression tests for statistical/fiscal reconciliation and workflow provenance contracts.
Path("tests/test_realistic_artifact_reconciliation.py").write_text('''from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_matrix_top_realistic import _artifact_binding_issues


class RealisticArtifactReconciliationTests(unittest.TestCase):
    def _fixture(self, root: Path):
        curve = root / "curve.csv"
        trades = root / "trades.csv"
        cash = root / "cash.csv"
        tax = root / "tax.csv"
        curve.write_text(
            "date,equity,tax_paid\\n"
            "2023-12-29,1000,1\\n"
            "2024-01-02,1000,1\\n",
            encoding="utf-8",
        )
        trades.write_text("date,fee\\n", encoding="utf-8")
        cash.write_text("date,net,tax\\n", encoding="utf-8")
        tax.write_text(
            "month,tax_due,irrf_withheld_month\\n"
            "2023-12,10,1\\n"
            "2024-01,5,0\\n",
            encoding="utf-8",
        )
        payload = {
            "start": "2023-12-29",
            "end": "2024-01-02",
            "initial_cash": 1000.0,
            "final_equity": 1000.0,
            "annual_volatility": 0.0,
            "sharpe": 0.0,
            "average_annual_return": 0.0,
            "trades": 0,
            "fees_paid": 0.0,
            "distributions_net": 0.0,
            "distribution_tax_paid": 0.0,
            "ordinary_income_tax_paid": 1.0,
            "ordinary_irrf_withheld": 1.0,
            "darf_paid": 0.0,
            "outstanding_accrued_tax_liability": 15.0,
        }
        return payload, curve, trades, cash, tax

    def test_gate_recomputes_curve_metrics_and_reconciles_tax_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload, curve, trades, cash, tax = self._fixture(Path(temporary))
            self.assertEqual(
                _artifact_binding_issues(
                    payload,
                    curve_path=curve,
                    trades_path=trades,
                    cash_path=cash,
                    tax_path=tax,
                ),
                [],
            )

    def test_curve_metric_mismatches_are_blocking(self) -> None:
        cases = {
            "annual_volatility": "curve_annual_volatility_mismatch",
            "sharpe": "curve_sharpe_mismatch",
            "average_annual_return": "curve_average_annual_return_mismatch",
        }
        with tempfile.TemporaryDirectory() as temporary:
            payload, curve, trades, cash, tax = self._fixture(Path(temporary))
            for field, expected_issue in cases.items():
                with self.subTest(field=field):
                    mutated = dict(payload)
                    mutated[field] = 0.25
                    issues = _artifact_binding_issues(
                        mutated,
                        curve_path=curve,
                        trades_path=trades,
                        cash_path=cash,
                        tax_path=tax,
                    )
                    self.assertIn(expected_issue, issues)

    def test_ordinary_tax_must_match_fiscal_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload, curve, trades, cash, tax = self._fixture(Path(temporary))
            payload["ordinary_income_tax_paid"] = 2.0
            self.assertIn(
                "tax_ledger_ordinary_income_tax_paid_mismatch",
                _artifact_binding_issues(
                    payload,
                    curve_path=curve,
                    trades_path=trades,
                    cash_path=cash,
                    tax_path=tax,
                ),
            )


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

Path("tests/test_workflow_integrity_contracts.py").write_text('''from __future__ import annotations

import unittest
from pathlib import Path


class WorkflowIntegrityContractTests(unittest.TestCase):
    def test_recovery_uses_original_calculation_commit_as_filesystem(self) -> None:
        text = Path(".github/workflows/recover-backtest-merge-hardened.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("CALCULATION_SHA=", text)
        self.assertIn('git worktree add --detach "$SOURCE_DIR" "$CALCULATION_SHA"', text)
        self.assertGreaterEqual(text.count('cd "$SOURCE_DIR"'), 3)

    def test_snapshot_checksum_asymmetry_is_fail_closed_everywhere(self) -> None:
        recovery = Path(".github/workflows/recover-backtest-merge-hardened.yml").read_text(
            encoding="utf-8"
        )
        matrix = Path(".github/workflows/full-matrix-backtest-hardened.yml").read_text(
            encoding="utf-8"
        )
        marker = "snapshot/checksum realista assimétricos em backtest-results"
        self.assertIn(marker, recovery)
        self.assertGreaterEqual(matrix.count(marker), 2)


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")
