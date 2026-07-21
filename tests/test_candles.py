from __future__ import annotations

import unittest

from b3_strategy_lab.candles import parse_yahoo_actions, parse_yahoo_chart, resample_to_4h, validate_candles


class CandleParsingTests(unittest.TestCase):
    def test_repairs_impossible_high_low_and_keeps_source_values(self) -> None:
        payload = {
            "chart": {
                "result": [
                    {
                        "meta": {"exchangeTimezoneName": "America/Sao_Paulo"},
                        "timestamp": [1704200400],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [10.0],
                                    "high": [9.0],
                                    "low": [11.0],
                                    "close": [12.0],
                                    "volume": [100],
                                }
                            ],
                            "adjclose": [{"adjclose": [6.0]}],
                        },
                    }
                ],
                "error": None,
            }
        }

        candles = parse_yahoo_chart(payload, "TEST3", "TEST3.SA")

        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].source_high, 9.0)
        self.assertEqual(candles[0].source_low, 11.0)
        self.assertEqual(candles[0].raw_high, 12.0)
        self.assertEqual(candles[0].raw_low, 10.0)
        self.assertEqual(candles[0].ohlc_repaired, 1)
        self.assertEqual(validate_candles(candles), [])

    def test_parses_dividends_and_splits_by_exchange_date(self) -> None:
        payload = {
            "chart": {
                "result": [
                    {
                        "meta": {"exchangeTimezoneName": "America/Sao_Paulo"},
                        "events": {
                            "dividends": {"1": {"amount": 1.5, "date": 1704200400}},
                            "splits": {
                                "2": {
                                    "date": 1704200400,
                                    "numerator": 2.0,
                                    "denominator": 1.0,
                                    "splitRatio": "2:1",
                                }
                            },
                        },
                    }
                ],
                "error": None,
            }
        }

        actions = parse_yahoo_actions(payload, "TEST3", "TEST3.SA")

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].date, "2024-01-02")
        self.assertEqual(actions[0].dividend, 1.5)
        self.assertEqual(actions[0].split_ratio, 2.0)

    def test_skips_nonpositive_source_ohlc(self) -> None:
        payload = {
            "chart": {
                "result": [
                    {
                        "meta": {"exchangeTimezoneName": "America/Sao_Paulo"},
                        "timestamp": [1704200400],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [0.0],
                                    "high": [12.0],
                                    "low": [10.0],
                                    "close": [11.0],
                                    "volume": [100],
                                }
                            ],
                            "adjclose": [{"adjclose": [11.0]}],
                        },
                    }
                ],
                "error": None,
            }
        }

        self.assertEqual(parse_yahoo_chart(payload, "TEST3", "TEST3.SA"), [])

    def test_resamples_intraday_candles_to_four_hour_buckets(self) -> None:
        payload = {
            "chart": {
                "result": [
                    {
                        "meta": {"exchangeTimezoneName": "America/Sao_Paulo"},
                        "timestamp": [
                            1704196800,
                            1704200400,
                            1704204000,
                            1704207600,
                            1704211200,
                            1704214800,
                            1704218400,
                            1704222000,
                        ],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0],
                                    "high": [11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0],
                                    "low": [9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0],
                                    "close": [10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5],
                                    "volume": [100, 200, 300, 400, 500, 600, 700, 800],
                                }
                            ],
                            "adjclose": [{"adjclose": [10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5]}],
                        },
                    }
                ],
                "error": None,
            }
        }

        candles = resample_to_4h(parse_yahoo_chart(payload, "TEST3", "TEST3.SA", include_time=True))

        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[0].raw_open, 10.0)
        self.assertEqual(candles[0].raw_high, 14.0)
        self.assertEqual(candles[0].raw_low, 9.0)
        self.assertEqual(candles[0].raw_close, 13.5)
        self.assertEqual(candles[0].volume, 1000)
        self.assertEqual(candles[1].raw_open, 14.0)
        self.assertEqual(candles[1].raw_high, 18.0)
        self.assertEqual(candles[1].raw_low, 13.0)
        self.assertEqual(candles[1].raw_close, 17.5)
        self.assertEqual(candles[1].volume, 2600)

    def test_resample_skips_incomplete_intraday_day(self) -> None:
        payload = {
            "chart": {
                "result": [
                    {
                        "meta": {"exchangeTimezoneName": "America/Sao_Paulo"},
                        "timestamp": [1704196800, 1704200400, 1704204000, 1704207600],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [10.0, 11.0, 12.0, 13.0],
                                    "high": [11.0, 12.0, 13.0, 14.0],
                                    "low": [9.0, 10.0, 11.0, 12.0],
                                    "close": [10.5, 11.5, 12.5, 13.5],
                                    "volume": [100, 200, 300, 400],
                                }
                            ],
                            "adjclose": [{"adjclose": [10.5, 11.5, 12.5, 13.5]}],
                        },
                    }
                ],
                "error": None,
            }
        }

        candles = resample_to_4h(parse_yahoo_chart(payload, "TEST3", "TEST3.SA", include_time=True))

        self.assertEqual(candles, [])


if __name__ == "__main__":
    unittest.main()
