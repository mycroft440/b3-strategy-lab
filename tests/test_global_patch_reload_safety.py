from __future__ import annotations

import csv
import importlib
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from b3_strategy_lab import audit_hardening, causal_liquidity
from b3_strategy_lab import realistic_core


class GlobalPatchReloadSafetyTests(unittest.TestCase):
    def test_causal_liquidity_reload_keeps_canonical_legs_non_recursive(self) -> None:
        canonical = getattr(
            realistic_core.ExecutionPriceBook,
            "_causal_liquidity_original_legs",
        )
        for _ in range(3):
            importlib.reload(causal_liquidity)
            self.assertIs(
                getattr(
                    realistic_core.ExecutionPriceBook,
                    "_causal_liquidity_original_legs",
                ),
                canonical,
            )

        book = realistic_core.ExecutionPriceBook(
            [
                realistic_core.ExecutionQuote(
                    date="2020-01-02",
                    ticker="TEST3",
                    market_type=realistic_core.STANDARD_MARKET,
                    open=10.0,
                    close=10.0,
                    financial_volume=100_000.0,
                )
            ]
        )
        legs = book.legs("2020-01-02", "TEST3", 100)
        self.assertEqual(len(legs), 1)
        self.assertEqual(legs[0][0], 100)

    def test_causal_from_csv_reload_preserves_classmethod_and_causal_reference(self) -> None:
        for _ in range(3):
            importlib.reload(causal_liquidity)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "execution.csv"
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=[
                        "date",
                        "ticker",
                        "market_type",
                        "open",
                        "close",
                        "financial_volume",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "date": "2020-01-02",
                        "ticker": "TEST3",
                        "market_type": realistic_core.STANDARD_MARKET,
                        "open": "10",
                        "close": "10",
                        "financial_volume": "1000",
                    }
                )
                writer.writerow(
                    {
                        "date": "2020-01-03",
                        "ticker": "TEST3",
                        "market_type": realistic_core.STANDARD_MARKET,
                        "open": "11",
                        "close": "11",
                        "financial_volume": "999999",
                    }
                )
            book = realistic_core.ExecutionPriceBook.from_csv(path)
            legs = book.legs("2020-01-03", "TEST3", 100)
            self.assertEqual(len(legs), 1)
            self.assertEqual(legs[0][1].financial_volume, 1000.0)

    def test_accounting_hardening_reload_keeps_buy_and_sell_non_recursive(self) -> None:
        canonical_buy = getattr(
            realistic_core.RealCashAccount,
            "_audit_hardening_original_buy_leg",
        )
        canonical_sell = getattr(
            realistic_core.RealCashAccount,
            "_audit_hardening_original_sell_leg",
        )
        for _ in range(3):
            importlib.reload(audit_hardening)
            self.assertIs(
                getattr(
                    realistic_core.RealCashAccount,
                    "_audit_hardening_original_buy_leg",
                ),
                canonical_buy,
            )
            self.assertIs(
                getattr(
                    realistic_core.RealCashAccount,
                    "_audit_hardening_original_sell_leg",
                ),
                canonical_sell,
            )

        schedule = realistic_core.FeeSchedule(
            [
                realistic_core.FeeRule(
                    start="2020-01-01",
                    end="2020-12-31",
                    b3_bps=0.0,
                )
            ]
        )
        account = realistic_core.RealCashAccount(
            10_000.0,
            schedule,
            realistic_core.SlippageModel(
                base_bps=0.0,
                participation_bps_at_1pct=0.0,
                max_bps=0.0,
            ),
        )
        quote = realistic_core.ExecutionQuote(
            date="2020-01-02",
            ticker="TEST3",
            market_type=realistic_core.STANDARD_MARKET,
            open=10.0,
            close=10.0,
            financial_volume=1_000_000.0,
        )
        account.buy_leg("2020-01-02", "TEST3", 10, quote)
        account.sell_leg("2020-01-02", "TEST3", 5, quote)
        self.assertEqual(account.shares("TEST3"), 5)

    def test_target_core_reload_can_be_rehardened_in_fresh_process(self) -> None:
        code = textwrap.dedent(
            """
            import importlib
            from b3_strategy_lab import audit_hardening, causal_liquidity
            from b3_strategy_lab import realistic_core, realistic_portfolio_core

            old_book = realistic_core.ExecutionPriceBook
            old_account = realistic_core.RealCashAccount
            importlib.reload(realistic_core)
            importlib.reload(realistic_portfolio_core)
            assert realistic_core.ExecutionPriceBook is not old_book
            assert realistic_core.RealCashAccount is not old_account

            importlib.reload(causal_liquidity)
            importlib.reload(audit_hardening)

            assert realistic_core.ExecutionPriceBook.legs.__module__ == 'b3_strategy_lab.causal_liquidity'
            assert realistic_core.RealCashAccount.buy_leg.__module__ == 'b3_strategy_lab.audit_hardening'
            assert realistic_core.RealCashAccount.sell_leg.__module__ == 'b3_strategy_lab.audit_hardening'
            assert realistic_portfolio_core._provisional_ordinary_tax.__module__ == 'b3_strategy_lab.audit_hardening'
            """
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
