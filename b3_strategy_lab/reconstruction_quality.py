from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


CERTIFIED_BROKER_QUALITIES = {"broker_statement", "broker_certified"}
CERTIFIED_EXECUTION_POLICY = "official_open_market_order"
FIXED_FEE_APPLICATION_PER_MARKET_ORDER_LEG = "per_market_order_leg"
# Backward-compatible alias. Public COTAHIST data can support a deterministic,
# certified counterfactual replay but cannot prove the exact fill of a hypothetical
# order. Exact personal-account labels are reserved for broker-source fills.
EXACT_EXECUTION_POLICY = CERTIFIED_EXECUTION_POLICY


@dataclass(frozen=True)
class BrokerFeeRule:
    start: str
    end: str
    brokerage_bps: float
    brokerage_fixed_per_order: float
    fixed_fee_application: str
    quality: str
    evidence: tuple[str, ...]

    def contains(self, value: str) -> bool:
        return self.start <= value <= self.end


@dataclass(frozen=True)
class BrokerProfile:
    broker_name: str
    account_label: str
    settlement_currency: str
    tax_scope: str
    other_equity_trades: bool
    initial_loss_carry: float
    monthly_custody_fee: float
    other_recurring_monthly_fee: float
    reviewed_by: str
    reviewed_at_utc: str
    recurring_fee_evidence: tuple[str, ...]
    rules: tuple[BrokerFeeRule, ...]

    @classmethod
    def from_json(cls, path: Path | str) -> "BrokerProfile":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schema_version") not in {1, 2}:
            raise ValueError("Broker profile requires schema_version 1 or 2.")
        tax = payload.get("tax_scope") or {}
        raw_rules = payload.get("rules")
        if not isinstance(raw_rules, list) or not raw_rules:
            raise ValueError("Broker profile requires at least one fee rule.")
        rules = tuple(
            BrokerFeeRule(
                start=str(item["start"]),
                end=str(item["end"]),
                brokerage_bps=float(item.get("brokerage_bps", 0.0)),
                brokerage_fixed_per_order=float(item.get("brokerage_fixed_per_order", 0.0)),
                fixed_fee_application=str(item.get("fixed_fee_application", "unspecified")).strip(),
                quality=str(item.get("quality", "unverified")),
                evidence=tuple(str(value) for value in item.get("evidence", []) if str(value).strip()),
            )
            for item in raw_rules
        )
        return cls(
            broker_name=str(payload.get("broker_name", "")).strip(),
            account_label=str(payload.get("account_label", "")).strip(),
            settlement_currency=str(payload.get("settlement_currency", "BRL")).upper(),
            tax_scope=str(tax.get("mode", "")).strip(),
            other_equity_trades=bool(tax.get("other_equity_trades", True)),
            initial_loss_carry=float(tax.get("initial_loss_carry", 0.0)),
            monthly_custody_fee=float(payload.get("monthly_custody_fee", 0.0)),
            other_recurring_monthly_fee=float(payload.get("other_recurring_monthly_fee", 0.0)),
            reviewed_by=str(payload.get("reviewed_by", "")).strip(),
            reviewed_at_utc=str(payload.get("reviewed_at_utc", "")).strip(),
            recurring_fee_evidence=tuple(
                str(value) for value in payload.get("recurring_fee_evidence", []) if str(value).strip()
            ),
            rules=rules,
        )


def _parse_iso(value: str) -> date:
    return date.fromisoformat(value)


def _continuous_coverage(rules: tuple[BrokerFeeRule, ...], start: str, end: str) -> bool:
    ordered = sorted(rules, key=lambda item: item.start)
    if not ordered or ordered[0].start > start or ordered[-1].end < end:
        return False
    cursor = _parse_iso(start)
    target = _parse_iso(end)
    for rule in ordered:
        rule_start = _parse_iso(rule.start)
        rule_end = _parse_iso(rule.end)
        if rule_end < cursor:
            continue
        if rule_start > cursor:
            return False
        cursor = max(cursor, rule_end + timedelta(days=1))
        if cursor > target:
            return True
    return cursor > target


def broker_profile_issues(profile: BrokerProfile, *, start: str, end: str) -> list[str]:
    issues: list[str] = []
    if not profile.broker_name:
        issues.append("broker_name_missing")
    if profile.settlement_currency != "BRL":
        issues.append("settlement_currency_must_be_brl")
    if profile.tax_scope != "isolated_strategy_account":
        issues.append("tax_scope_must_be_isolated_strategy_account")
    if profile.other_equity_trades:
        issues.append("other_equity_trades_make_tax_reconstruction_non_isolated")
    if profile.initial_loss_carry != 0.0:
        issues.append("nonzero_initial_loss_carry_is_not_supported_by_certified_replay")
    if profile.monthly_custody_fee != 0.0 or profile.other_recurring_monthly_fee != 0.0:
        issues.append("recurring_broker_fees_are_not_yet_debited_by_account_engine")
    if not profile.recurring_fee_evidence:
        issues.append("recurring_fee_zero_or_amount_requires_documentary_evidence")
    try:
        reviewed_at = datetime.fromisoformat(profile.reviewed_at_utc.replace("Z", "+00:00"))
        if reviewed_at.tzinfo is None:
            raise ValueError
    except ValueError:
        issues.append("broker_profile_review_timestamp_invalid")
    if not profile.reviewed_by:
        issues.append("broker_profile_reviewer_missing")
    if not _continuous_coverage(profile.rules, start, end):
        issues.append("broker_fee_rules_do_not_cover_backtest_period")
    for rule in profile.rules:
        if rule.brokerage_bps < 0 or rule.brokerage_fixed_per_order < 0:
            issues.append("broker_fee_rule_has_negative_fee")
        if (
            rule.brokerage_fixed_per_order > 0
            and rule.fixed_fee_application != FIXED_FEE_APPLICATION_PER_MARKET_ORDER_LEG
        ):
            issues.append(
                f"fixed_brokerage_application_must_be_per_market_order_leg:{rule.start}:{rule.end}"
            )
        if rule.quality not in CERTIFIED_BROKER_QUALITIES:
            issues.append(f"broker_fee_rule_not_certified:{rule.start}:{rule.end}")
        if not rule.evidence:
            issues.append(f"broker_fee_rule_missing_evidence:{rule.start}:{rule.end}")
    return sorted(set(issues))


def certified_replay_blockers(
    audit: dict[str, object],
    profile: BrokerProfile,
    *,
    start: str,
    end: str,
    execution_policy: str,
    base_slippage_bps: float,
    participation_bps_at_1pct: float,
    max_slippage_bps: float,
) -> list[str]:
    """Gate a deterministic official-open counterfactual replay.

    Passing this gate certifies input provenance and declared assumptions. It does
    not prove that a hypothetical order would have received the public daily open;
    exact execution requires actual broker fills and is handled separately.
    """

    blockers: list[str] = []
    if audit.get("ready_for_certified_market_inputs") is not True:
        blockers.extend(str(item) for item in audit.get("certified_market_input_blockers", []))
    if audit.get("ex_ante_selection_claim_allowed") is not True:
        blockers.append("survivorship_safe_point_in_time_universe_required")
    if execution_policy != CERTIFIED_EXECUTION_POLICY:
        blockers.append("execution_policy_must_use_official_open_market_order")
    if any(value != 0.0 for value in (base_slippage_bps, participation_bps_at_1pct, max_slippage_bps)):
        blockers.append("modeled_slippage_must_be_disabled_for_certified_official_open_replay")
    blockers.extend(broker_profile_issues(profile, start=start, end=end))
    return sorted(set(blockers))


def strict_exact_blockers(
    audit: dict[str, object],
    profile: BrokerProfile,
    *,
    start: str,
    end: str,
    execution_policy: str,
    base_slippage_bps: float,
    participation_bps_at_1pct: float,
    max_slippage_bps: float,
) -> list[str]:
    """Deprecated compatibility wrapper for certified_replay_blockers."""

    return certified_replay_blockers(
        audit,
        profile,
        start=start,
        end=end,
        execution_policy=execution_policy,
        base_slippage_bps=base_slippage_bps,
        participation_bps_at_1pct=participation_bps_at_1pct,
        max_slippage_bps=max_slippage_bps,
    )


def _load_b3_rules(path: Path | str) -> list[dict[str, object]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("B3 fee schedule requires rules.")
    return [dict(item) for item in rules]


def write_composite_fee_schedule(
    *,
    b3_fee_schedule: Path | str,
    broker_profile: BrokerProfile,
    start: str,
    end: str,
    output: Path | str,
) -> Path:
    """Combine official B3 percentage fees with certified broker order fees.

    ``brokerage_fixed`` is consumed by the execution engine once for every
    executable market leg. An integer position can therefore generate one standard
    order (010), one fractional order (020), or both. Nonzero certified fixed fees
    are accepted only when the broker evidence explicitly uses that same charging
    unit via ``fixed_fee_application=per_market_order_leg``.
    """

    b3_rules = _load_b3_rules(b3_fee_schedule)
    combined: list[dict[str, object]] = []
    requested_start = _parse_iso(start)
    requested_end = _parse_iso(end)
    for b3 in b3_rules:
        b3_start = _parse_iso(str(b3["start"]))
        b3_end = _parse_iso(str(b3["end"]))
        for broker in broker_profile.rules:
            broker_start = _parse_iso(broker.start)
            broker_end = _parse_iso(broker.end)
            overlap_start = max(requested_start, b3_start, broker_start)
            overlap_end = min(requested_end, b3_end, broker_end)
            if overlap_start > overlap_end:
                continue
            if str(b3.get("quality", "")) != "official":
                raise ValueError("Cannot build certified composite schedule from non-official B3 fees.")
            if broker.quality not in CERTIFIED_BROKER_QUALITIES:
                raise ValueError("Cannot build certified composite schedule from unverified broker fees.")
            if (
                broker.brokerage_fixed_per_order > 0
                and broker.fixed_fee_application != FIXED_FEE_APPLICATION_PER_MARKET_ORDER_LEG
            ):
                raise ValueError(
                    "Nonzero fixed brokerage requires fixed_fee_application="
                    f"{FIXED_FEE_APPLICATION_PER_MARKET_ORDER_LEG}."
                )
            combined.append(
                {
                    "start": overlap_start.isoformat(),
                    "end": overlap_end.isoformat(),
                    "b3_bps": float(b3["b3_bps"]) + broker.brokerage_bps,
                    "brokerage_fixed": broker.brokerage_fixed_per_order,
                    "fixed_fee_application": broker.fixed_fee_application,
                    "quality": "certified",
                    "source": (
                        f"B3={b3.get('source', '')}; broker={broker_profile.broker_name}; "
                        f"broker_evidence={' | '.join(broker.evidence)}"
                    ),
                }
            )
    combined.sort(key=lambda item: str(item["start"]))
    if not combined:
        raise ValueError("No overlapping B3/broker fee rules cover the requested period.")

    synthetic = tuple(
        BrokerFeeRule(
            start=str(item["start"]),
            end=str(item["end"]),
            brokerage_bps=0.0,
            brokerage_fixed_per_order=0.0,
            fixed_fee_application=FIXED_FEE_APPLICATION_PER_MARKET_ORDER_LEG,
            quality="broker_certified",
            evidence=("composite",),
        )
        for item in combined
    )
    if not _continuous_coverage(synthetic, start, end):
        raise ValueError("Composite fee schedule has a date gap.")

    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "purpose": "Certified B3 plus broker fee schedule for deterministic official-open replay.",
                "broker_name": broker_profile.broker_name,
                "rules": combined,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination
