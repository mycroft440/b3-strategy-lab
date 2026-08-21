from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import research_portfolio_allocation as research
from scripts import sync_point_in_time_universe_realistic as sync_realistic


class PointInTimeStorageIsolationTests(unittest.TestCase):
    def test_realistic_sync_injects_all_isolated_roots(self) -> None:
        with patch.object(sync_realistic.base, "main", return_value=0) as delegated:
            self.assertEqual(sync_realistic.main(["--years", "2017:2018"]), 0)
        arguments = delegated.call_args.args[0]
        pairs = dict(zip(arguments[::2], arguments[1::2]))
        self.assertEqual(pairs["--data-dir"], "data/candles_point_in_time")
        self.assertEqual(pairs["--actions-dir"], "data/actions_point_in_time")
        self.assertEqual(pairs["--manifests-dir"], "data/manifests_point_in_time")
        self.assertEqual(
            pairs["--split-evidence"],
            "data/corporate_actions/point_in_time_split_evidence.json",
        )
        self.assertEqual(pairs["--dataset-split-evidence"], pairs["--split-evidence"])

    def test_realistic_sync_preserves_explicit_overrides(self) -> None:
        arguments = [
            "--data-dir",
            "tmp/data",
            "--actions-dir",
            "tmp/actions",
            "--manifests-dir",
            "tmp/manifests",
            "--split-evidence",
            "tmp/splits.json",
        ]
        with patch.object(sync_realistic.base, "main", return_value=0) as delegated:
            self.assertEqual(sync_realistic.main(arguments), 0)
        forwarded = delegated.call_args.args[0]
        self.assertEqual(forwarded.count("--data-dir"), 1)
        self.assertEqual(forwarded.count("--actions-dir"), 1)
        self.assertEqual(forwarded.count("--manifests-dir"), 1)
        self.assertEqual(forwarded.count("--split-evidence"), 1)
        index = forwarded.index("--dataset-split-evidence")
        self.assertEqual(forwarded[index + 1], "tmp/splits.json")

    def test_market_data_passes_isolated_roots_to_verifier(self) -> None:
        candle = SimpleNamespace(date="2018-01-02", close=10.0, raw_close=10.0)
        manifest = SimpleNamespace(ticker="AAA3")
        with patch.object(
            research,
            "load_verified_candles",
            return_value=([candle], manifest),
        ) as loader:
            data = research.MarketData(
                ["AAA3"],
                "1d",
                "adjusted",
                require_verified_splits_from="2017-01-01",
                history_start="2017-01-01",
                data_dir="tmp/data",
                actions_dir="tmp/actions",
                manifests_dir="tmp/manifests",
                split_evidence_path="tmp/splits.json",
            )
        self.assertEqual(data.dates, ["2018-01-02"])
        loader.assert_called_once_with(
            "AAA3",
            "1d",
            start="2017-01-01",
            require_verified_splits_from="2017-01-01",
            data_dir="tmp/data",
            actions_dir="tmp/actions",
            manifests_dir="tmp/manifests",
            split_evidence_path="tmp/splits.json",
        )

    def test_default_market_data_still_delegates_to_research_core(self) -> None:
        with patch.object(research._core.MarketData, "__init__", return_value=None) as init:
            research.MarketData(["AAA3"], "1d", "adjusted")
        init.assert_called_once_with(
            ["AAA3"],
            "1d",
            "adjusted",
            allow_unverified_data=False,
            require_verified_splits_from=None,
            history_start=None,
        )


if __name__ == "__main__":
    unittest.main()
