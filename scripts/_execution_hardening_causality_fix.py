from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        print(f"already fixed: {path}")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"fixed: {path}")


replace_once(
    "b3_strategy_lab/extended_strategies.py",
    "from datetime import date\n",
    "from datetime import date, timedelta\n",
)

replace_once(
    "b3_strategy_lab/extended_strategies.py",
    '''    sessions = [date.fromisoformat(candle.date.split(" ", 1)[0]) for candle in candles]\n\n    def is_invested(month: int) -> bool:\n        if entry_month > exit_month:\n            return month >= entry_month or month < exit_month\n        return entry_month <= month < exit_month\n\n    # The signal at a close is the desired position at the next known session's open.\n    return [int(is_invested(sessions[index + 1].month)) if index + 1 < len(sessions) else 0 for index in range(len(sessions))]\n''',
    '''    sessions = [date.fromisoformat(candle.date.split(" ", 1)[0]) for candle in candles]\n\n    def is_invested(month: int) -> bool:\n        if entry_month > exit_month:\n            return month >= entry_month or month < exit_month\n        return entry_month <= month < exit_month\n\n    def next_business_month(session: date) -> int:\n        # Calendar information is known ex ante.  We only need the month of the\n        # next potential trading day; weekends are skipped and an exchange holiday\n        # cannot change the month classification once the calendar crosses the\n        # boundary.  No future candle, price, volume, or observed session is read.\n        candidate = session + timedelta(days=1)\n        while candidate.weekday() >= 5:\n            candidate += timedelta(days=1)\n        return candidate.month\n\n    # A close signal is the desired position for the following open.  This remains\n    # prefix-causal even when the current candle is the final candle in the input.\n    return [int(is_invested(next_business_month(session))) for session in sessions]\n''',
)

replace_once(
    "tests/test_extended_strategies.py",
    '''    def test_price_engines_do_not_rewrite_past_signals(self) -> None:\n        candles = rich_market_candles()\n\n        for strategy in EXTENDED_STRATEGIES:\n            if strategy.name == "halloween_effect":\n                continue\n            with self.subTest(strategy=strategy.name):\n''',
    '''    def test_price_engines_do_not_rewrite_past_signals(self) -> None:\n        candles = rich_market_candles()\n\n        for strategy in EXTENDED_STRATEGIES:\n            with self.subTest(strategy=strategy.name):\n''',
)

replace_once(
    "tests/test_extended_strategies.py",
    '''        self.assertEqual(signals, [1, 1, 0, 0, 1, 0])\n''',
    '''        self.assertEqual(signals, [1, 1, 0, 0, 1, 1])\n\n        prefix = build_signals("halloween_effect", candles[:-1])\n        self.assertEqual(prefix, signals[:-1])\n''',
)

print("Halloween causality fix complete")
