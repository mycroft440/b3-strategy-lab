from __future__ import annotations

import unittest
import csv
import json
import tempfile
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import walk_forward_certified as certified
from scripts import walk_forward_realistic as walk
from scripts.research_portfolio_allocation import PortfolioConfig
from scripts.walk_forward_certified import _force_certified_semantics
from scripts.walk_forward_realistic import _metric, _rank_candidates


class CertifiedWalkForwardSemanticsTests(unittest.TestCase):
    def test_argument_values_follow_argparse_equals_and_last_wins(self) -> None:
        self.assertEqual(certified._value_after(
            ["--end", "2020-01-01", "--end=2021-12-31"], "--end", "missing"
        ), "2021-12-31")

    def test_help_does_not_require_data_or_raise_percent_format_error(self) -> None:
        with redirect_stdout(StringIO()), self.assertRaises(SystemExit) as stopped:
            certified.main(["--help"])
        self.assertEqual(stopped.exception.code, 0)

    def test_main_bounds_actual_folds_to_implicit_certified_end(self) -> None:
        calls = []

        def replay(**kwargs):
            calls.append(kwargs)
            summary = SimpleNamespace(
                initial_cash=1000.0, final_equity=1000.0, total_return=0.0,
                cagr=0.0, sharpe=0.0, max_drawdown=0.0, trades=0, fees_paid=0.0,
                ordinary_income_tax_paid=0.0, distribution_tax_paid=0.0,
                selection_status=kwargs["selection_status"], validity="REALISTIC_POINT_IN_TIME",
            )
            curve = [SimpleNamespace(date=day, equity=1000.0, cash=1000.0, selected="",
                                     positions=0, tax_paid=0.0, fees_paid=0.0)
                     for day in dates if kwargs["start"] <= day <= kwargs["end"]]
            return summary, curve, object()

        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            universe = root / "universe.json"
            universe.write_text(json.dumps({
                "point_in_time": True, "survivorship_safe": True,
                "tickers": ["AAA3"], "warmup_start": "2019-01-01",
            }), encoding="utf-8")
            cash_manifest = root / "cash.json"
            cash_manifest.write_text(json.dumps({"complete": True, "end": "2021-12-30"}),
                                     encoding="utf-8")
            certificate = root / "certificate.json"
            certificate.write_text("{}", encoding="utf-8")
            output = root / "folds.csv"
            summary_path = root / "summary.json"
            dates = ["2020-12-29", "2020-12-30", "2021-01-04", "2021-12-30", "2022-01-03"]
            stack.enter_context(patch.object(walk, "MarketData", return_value=SimpleNamespace(dates=dates)))
            stack.enter_context(patch.object(walk.PointInTimeUniverse, "from_csv",
                                            return_value=SimpleNamespace(union={"AAA3"})))
            stack.enter_context(patch.object(walk.ExecutionPriceBook, "from_csv"))
            stack.enter_context(patch.object(walk.FeeSchedule, "from_json"))
            stack.enter_context(patch.object(walk, "load_cash_distributions", return_value=[]))
            stack.enter_context(patch.object(walk, "load_transitions", return_value=[]))
            stack.enter_context(patch.object(walk, "transition_binding_issues", return_value=[]))
            stack.enter_context(patch.object(walk, "portfolio_strategies", return_value=["gap_momentum"]))
            stack.enter_context(patch.object(walk, "_configs", return_value=[PortfolioConfig(name="test")]))
            stack.enter_context(patch.object(walk, "run_realistic", side_effect=replay))
            coverage = stack.enter_context(patch.object(certified, "cash_coverage_certification_issues", return_value=[]))
            arguments = [
                f"--universe-manifest={universe}", f"--cash-manifest={cash_manifest}",
                f"--cash-certification={certificate}", "--start=2020-01-01",
                "--first-test-year=2021",
                f"--output={output}", f"--summary-output={summary_path}",
                f"--continuous-curve-output={root / 'curve.csv'}",
            ]
            self.assertEqual(certified.main(arguments), 0)
            self.assertEqual(coverage.call_args.kwargs["end"], "2021-12-30")
            self.assertEqual(len(calls), 2)  # one training run and one OOS run
            self.assertTrue(all(call["end"] <= "2021-12-30" for call in calls))
            with output.open(newline="", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual([row["test_year"] for row in rows], ["2021"])
            self.assertEqual(json.loads(summary_path.read_text())["certified_coverage_end"], "2021-12-30")
            benchmark = root / "cdi.csv"
            benchmark.write_text("date,return\n" + "".join(f"{day},0.0001\n" for day in dates), encoding="utf-8")
            calls.clear()
            self.assertEqual(certified.main(arguments + [
                "--benchmark-csv", str(benchmark), "--objective", "excess_sharpe",
                "--holdout-start", "2021-01-01",
            ]), 0)
            result = json.loads(summary_path.read_text())
            self.assertEqual(result["oos_sign_test_reference"], "benchmark_excess")
            self.assertEqual(result["holdout_fold_count"], 1)
            self.assertLess(result["continuous_excess_total_return"], 0)
            self.assertLess(calls[0]["end"], "2021-01-01")

            def exceeds_coverage(_argv):
                return walk.run_realistic(start="2021-01-04", end="2022-01-03")

            with patch.object(walk, "main", side_effect=exceeds_coverage):
                with self.assertRaisesRegex(ValueError, "exceeds certified coverage"):
                    certified.main(arguments)

    def test_certified_semantics_force_gap_adjustment_and_continuous_account(self) -> None:
        argv = _force_certified_semantics(["--all-strategies", "--start", "2018-01-02"])
        self.assertIn("--economic-gap-adjustment", argv)
        self.assertIn("--continuous-oos-account", argv)

    def test_certified_flags_are_not_duplicated(self) -> None:
        argv = _force_certified_semantics(
            [
                "--all-strategies",
                "--economic-gap-adjustment",
                "--continuous-oos-account",
            ]
        )
        self.assertEqual(argv.count("--economic-gap-adjustment"), 1)
        self.assertEqual(argv.count("--continuous-oos-account"), 1)

    def test_exact_metric_ties_do_not_compare_portfolio_config_objects(self) -> None:
        config_z = PortfolioConfig(name="z_config")
        config_a = PortfolioConfig(name="a_config")
        summary = SimpleNamespace(cagr=0.0, total_return=0.0, sharpe=0.0)
        ranked = _rank_candidates(
            [
                (0.0, "same_strategy", config_z, summary),
                (0.0, "same_strategy", config_a, summary),
            ]
        )
        self.assertEqual(ranked[0][2].name, "a_config")
        self.assertEqual(ranked[1][2].name, "z_config")

    def test_training_objective_rejects_nonfinite_values(self) -> None:
        summary = SimpleNamespace(cagr=float("nan"), total_return=0.0, sharpe=0.0)
        with self.assertRaisesRegex(ValueError, "Non-finite training objective"):
            _metric(summary, "cagr")


if __name__ == "__main__":
    unittest.main()
