from __future__ import annotations

import unittest

from b3_strategy_lab.strategies import portfolio_strategies, strategy_info, strategy_parameters
from scripts.audit_volume_indicators import (
    EXPECTED_SOURCE_CONSUMERS,
    source_raw_volume_consumers,
    source_volume_consumers,
    volume_strategy_names,
)


class VolumeAuditTests(unittest.TestCase):
    def test_static_inventory_covers_every_source_function_that_reads_volume(self) -> None:
        self.assertEqual(source_volume_consumers(), EXPECTED_SOURCE_CONSUMERS)
        self.assertEqual(source_raw_volume_consumers(), set())

    def test_inventory_covers_volume_families_and_parameterized_filters(self) -> None:
        registered = set(portfolio_strategies())
        audited = set(volume_strategy_names())
        family_volume = {
            name for name in registered if "volume" in strategy_info(name).family
        }
        parameter_volume = {
            name
            for name in registered
            if {"volume_window", "volume_mult"} & set(strategy_parameters(name))
        }

        self.assertLessEqual(family_volume, audited)
        self.assertLessEqual({"cmf_ema_trend", "nvi_dual_ema_trend"}, audited)
        self.assertEqual(
            parameter_volume,
            {"chandelier_breakout", "range_expansion_breakout"},
        )
        self.assertLessEqual(audited, registered)


if __name__ == "__main__":
    unittest.main()

# Touchpoint: trigger the hardened expanded full-matrix run.
