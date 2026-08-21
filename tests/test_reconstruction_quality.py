from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.reconstruction_quality import (
    CERTIFIED_EXECUTION_POLICY,
    EXACT_EXECUTION_POLICY,
    BrokerProfile,
    broker_profile_issues,
    certified_replay_blockers,
    strict_exact_blockers,
    write_composite_fee_schedule,
)


class ReconstructionQualityTests(unittest.TestCase):
    def _profile(self, directory: Path, *, quality: str = "broker_certified") -> BrokerProfile:
        path = directory / "broker.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "broker_name": "Test Broker",
                    "account_label": "isolated",
                    "settlement_currency": "BRL",
                    "tax_scope": {
                        "mode": "isolated_strategy_account",
                        "other_equity_trades": False,
                        "initial_loss_carry": 0.0,
                    },
                    "monthly_custody_fee": 0.0,
                    "other_recurring_monthly_fee": 0.0,
                    "recurring_fee_evidence": ["broker statement"],
                    "reviewed_by": "statement review",
                    "reviewed_at_utc": "2026-08-21T12:00:00+00:00",
                    "rules": [
                        {
                            "start": "2018-01-01",
                            "end": "2099-12-31",
                            "brokerage_bps": 0.0,
                            "brokerage_fixed_per_order": 0.0,
                            "quality": quality,
                            "evidence": ["broker tariff table"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return BrokerProfile.from_json(path)

    def _audit(self) -> dict[str, object]:
        return {
            "ready_for_certified_market_inputs": True,
            "certified_market_input_blockers": [],
            "ex_ante_selection_claim_allowed": True,
        }

    def test_certified_profile_and_zero_slippage_can_pass_certified_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile = self._profile(Path(tmp))
            blockers = certified_replay_blockers(
                self._audit(),
                profile,
                start="2018-01-02",
                end="2026-08-20",
                execution_policy=CERTIFIED_EXECUTION_POLICY,
                base_slippage_bps=0.0,
                participation_bps_at_1pct=0.0,
                max_slippage_bps=0.0,
            )
            self.assertEqual(blockers, [])

    def test_modeled_slippage_is_a_certified_replay_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile = self._profile(Path(tmp))
            blockers = certified_replay_blockers(
                self._audit(),
                profile,
                start="2018-01-02",
                end="2026-08-20",
                execution_policy=CERTIFIED_EXECUTION_POLICY,
                base_slippage_bps=1.0,
                participation_bps_at_1pct=0.0,
                max_slippage_bps=0.0,
            )
            self.assertIn(
                "modeled_slippage_must_be_disabled_for_certified_official_open_replay",
                blockers,
            )

    def test_legacy_exact_names_are_compatibility_aliases_only(self) -> None:
        self.assertEqual(EXACT_EXECUTION_POLICY, CERTIFIED_EXECUTION_POLICY)
        with tempfile.TemporaryDirectory() as tmp:
            profile = self._profile(Path(tmp))
            self.assertEqual(
                strict_exact_blockers(
                    self._audit(),
                    profile,
                    start="2018-01-02",
                    end="2026-08-20",
                    execution_policy=EXACT_EXECUTION_POLICY,
                    base_slippage_bps=0.0,
                    participation_bps_at_1pct=0.0,
                    max_slippage_bps=0.0,
                ),
                [],
            )

    def test_unverified_broker_rule_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile = self._profile(Path(tmp), quality="unverified")
            issues = broker_profile_issues(profile, start="2018-01-02", end="2026-08-20")
            self.assertTrue(any(item.startswith("broker_fee_rule_not_certified") for item in issues))

    def test_survivorship_unsafe_audit_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile = self._profile(Path(tmp))
            audit = self._audit()
            audit["ex_ante_selection_claim_allowed"] = False
            blockers = certified_replay_blockers(
                audit,
                profile,
                start="2018-01-02",
                end="2026-08-20",
                execution_policy=CERTIFIED_EXECUTION_POLICY,
                base_slippage_bps=0.0,
                participation_bps_at_1pct=0.0,
                max_slippage_bps=0.0,
            )
            self.assertIn("survivorship_safe_point_in_time_universe_required", blockers)

    def test_composite_schedule_adds_b3_and_broker_percentage_costs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self._profile(directory)
            payload = json.loads((directory / "broker.json").read_text())
            payload["rules"][0]["brokerage_bps"] = 1.0
            (directory / "broker.json").write_text(json.dumps(payload), encoding="utf-8")
            profile = BrokerProfile.from_json(directory / "broker.json")
            b3 = directory / "b3.json"
            b3.write_text(
                json.dumps(
                    {
                        "rules": [
                            {
                                "start": "2018-01-01",
                                "end": "2099-12-31",
                                "b3_bps": 3.2,
                                "quality": "official",
                                "source": "B3",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            output = directory / "combined.json"
            write_composite_fee_schedule(
                b3_fee_schedule=b3,
                broker_profile=profile,
                start="2018-01-02",
                end="2026-08-20",
                output=output,
            )
            combined = json.loads(output.read_text())
            self.assertAlmostEqual(combined["rules"][0]["b3_bps"], 4.2)
            self.assertEqual(combined["rules"][0]["quality"], "certified")


if __name__ == "__main__":
    unittest.main()
