from pathlib import Path

from b3_strategy_lab import corporate_settlements
from b3_strategy_lab.corporate_tax_deferral import _finalize_ready_deferred_months
from b3_strategy_lab.realistic import RealCashAccount
from b3_strategy_lab.realistic_core import FeeRule, FeeSchedule, SlippageModel


def _account() -> RealCashAccount:
    fees = FeeSchedule([
        FeeRule(
            start="2018-01-01",
            end="2030-12-31",
            b3_bps=0.0,
            brokerage_fixed=0.0,
            source="test",
            quality="official",
        )
    ])
    return RealCashAccount(100_000.0, fees, SlippageModel())


def test_source_bound_settlement_ledger_lives_inside_snapshot_manifest_tree():
    path = Path(corporate_settlements.DEFAULT_CORPORATE_SETTLEMENTS)
    assert path.as_posix().endswith("data/manifests_point_in_time/corporate_settlements.json")
    rules = corporate_settlements.load_corporate_settlements(path)
    rule = rules[("2025-06-06", "HAPV3")]
    assert rule["realization_date"] == "2025-06-30"
    assert rule["price_known_date"] == "2025-07-04"


def test_unpriced_fractional_sale_defers_month_close_and_keeps_june_tax_competence():
    account = _account()
    account._corporate_receivables = {
        ("2025-06-06", "HAPV3"): {
            "rule": {
                "realization_date": "2025-06-30",
            },
            "net": None,
        }
    }

    result = account.finalize_month("2025-06")
    assert result == (None, 0.0)
    assert "2025-06" not in account.tax._finalized
    assert account._corporate_tax_deferred_months == {"2025-06"}

    account.tax.record_sale("2025-06-30", 30_000.0, 1_000.0)
    account._corporate_receivables[("2025-06-06", "HAPV3")]["net"] = 1.0
    _finalize_ready_deferred_months(account)

    june = account.tax._finalized["2025-06"]
    assert june.sales == 30_000.0
    assert june.realized_gain == 1_000.0
    assert june.gross_tax_before_irrf == 150.0
    assert june.irrf_withheld_month == 1.5
    assert june.tax_due == 148.5
    assert account._corporate_tax_deferred_months == set()


def test_later_month_cannot_finalize_ahead_of_unpriced_prior_month():
    account = _account()
    account._corporate_receivables = {
        ("2025-06-06", "HAPV3"): {
            "rule": {"realization_date": "2025-06-30"},
            "net": None,
        }
    }

    account.finalize_month("2025-06")
    account.finalize_month("2025-07")
    assert account._corporate_tax_deferred_months == {"2025-06", "2025-07"}
    assert account.tax._finalized == {}

    account.tax.record_sale("2025-06-30", 1_000.0, 10.0)
    account._corporate_receivables[("2025-06-06", "HAPV3")]["net"] = 1.0
    _finalize_ready_deferred_months(account)

    assert list(sorted(account.tax._finalized)) == ["2025-06", "2025-07"]
    assert account._corporate_tax_deferred_months == set()
