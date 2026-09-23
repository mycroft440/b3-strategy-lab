from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.rank_strategies_realistic import (
    classify_reading,
    excess_statistics,
    one_sided_pvalue,
    render_markdown,
    run_ranking,
)


def _row(strategy: str, train_rank: int, test_rank: int, train_cagr: float, test_cagr: float) -> dict[str, object]:
    return {
        "strategy": strategy,
        "management": "top1_test",
        "train_rank": train_rank,
        "test_rank": test_rank,
        "train_cagr": train_cagr,
        "test_cagr": test_cagr,
        "test_total_return": test_cagr * 3,
        "test_final_equity": 1000 * (1 + test_cagr * 3),
        "test_max_drawdown": -0.3,
        "test_sharpe": 0.5,
        "cdi_total_return": 0.5,
        "excess_total_return_vs_cdi": test_cagr * 3 - 0.5,
        "excess_t_stat": 1.0,
        "excess_pvalue_bonferroni": 1.0,
        "reading": classify_reading(test_cagr * 3, test_cagr * 3 - 0.5, 1.0),
    }


class RankStrategiesRealisticTests(unittest.TestCase):
    def test_reading_requires_benchmark_and_multiple_testing_evidence(self) -> None:
        self.assertEqual(classify_reading(-0.1, 0.2, 0.001), "PERDA NO TESTE")
        self.assertEqual(classify_reading(0.1, None, None), "SEM BENCHMARK")
        self.assertEqual(classify_reading(0.1, -0.05, 0.001), "ABAIXO DO CDI")
        self.assertEqual(classify_reading(2.0, 1.5, 0.5), "ACIMA DO CDI (NAO SIGNIFICATIVO)")
        self.assertEqual(
            classify_reading(2.0, 1.5, 0.01), "ACIMA DO CDI (SIGNIFICATIVO APOS BONFERRONI)"
        )

    def test_one_sided_pvalue_uses_normal_tail(self) -> None:
        self.assertAlmostEqual(one_sided_pvalue(0.0), 0.5)
        self.assertAlmostEqual(one_sided_pvalue(1.6448536269514722), 0.05, places=6)

    def test_excess_statistics_compare_against_dated_benchmark(self) -> None:
        curve = [("2024-01-02", 1010.0), ("2024-01-03", 1020.1), ("2024-01-04", 1030.301)]
        benchmark = {"2024-01-02": 0.001, "2024-01-03": 0.001, "2024-01-04": 0.001}

        stats = excess_statistics(curve, 1000.0, benchmark)

        self.assertAlmostEqual(stats["cdi_total_return"], 1.001**3 - 1)
        self.assertAlmostEqual(stats["excess_total_return_vs_cdi"], 0.030301 - (1.001**3 - 1))
        self.assertTrue(all(value is None for value in excess_statistics(curve, 1000.0, None).values()))

    def test_rejects_test_period_before_universe_is_knowable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            universe = Path(tmp) / "universe.json"
            universe.write_text(
                json.dumps(
                    {
                        "tickers": ["AAA3"],
                        "warmup_start": "2017-01-01",
                        "selection_rules": {"liquidity_year": 2018},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "2019-01-01"):
                run_ranking(
                    ["buy_and_hold"],
                    start="2018-01-02",
                    train_end="2018-06-29",
                    test_start="2018-07-02",
                    universe_path=universe,
                    benchmark_path=None,
                )

    def test_markdown_reports_train_selected_pair_and_flags_test_selection(self) -> None:
        train_best = _row("sma_cross", 1, 2, 0.70, 0.0025)
        test_best = _row("gap_momentum", 2, 1, 0.35, 0.37)
        result = {
            "rows": [train_best, test_best],
            "protocol_winner": train_best,
            "market_baseline": None,
            "cdi": {"total_return": 0.5, "cagr": 0.13, "final_equity": 1500.0},
            "metadata": {
                "start": "2018-01-02",
                "train_end": "2022-12-29",
                "test_start": "2023-01-02",
                "test_end": "2026-08-19",
                "initial_cash": 1000.0,
                "cost_bps": 3.2,
                "slippage_bps": 10.0,
                "lot_size": 1,
                "config_set": "base",
                "management_candidates_per_strategy": 160,
                "objective": "cagr",
                "universe": "data/universes/fixed_40_2018.json",
                "survivorship_safe": False,
                "validity": "OUT_OF_SAMPLE_SELECTION__BIASED_UNIVERSE",
                "economic_scope": "strict_level1_split_adjusted_no_dividends_no_income_tax",
            },
        }

        text = render_markdown(result)

        protocol = text.split("## Resultado do protocolo", 1)[1].split("##", 1)[0]
        self.assertIn("`sma_cross`", protocol)
        self.assertNotIn("gap_momentum", protocol)
        self.assertIn("selecao no holdout entre 2 candidatos", text)
        self.assertIn("survivorship_safe=false", text)
        self.assertNotIn("EXCELENTE", text)


if __name__ == "__main__":
    unittest.main()
