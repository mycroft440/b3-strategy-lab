from __future__ import annotations

import unittest

from b3_strategy_lab.candles import Candle
from b3_strategy_lab.extensions import (
    available_indicators,
    build_indicator,
    indicator,
    registered_strategies,
    strategy,
)


class ExtensionRegistryTests(unittest.TestCase):
    def test_indicator_registration_validates_output_length(self) -> None:
        @indicator("test_close_extension")
        def close_values(candles: list[Candle], *, multiplier: float = 1.0):
            return [candle.close * multiplier for candle in candles]

        candles = [
            Candle(
                "2024-01-02", "TEST3", "TEST3", 10, 10, 10, 10, 10, 100,
                10, 10, 10, 10, 1,
            )
        ]
        self.assertIn("test_close_extension", available_indicators())
        self.assertEqual(
            build_indicator("test_close_extension", candles, multiplier=2),
            [20],
        )

    def test_strategy_registration_keeps_metadata_and_function(self) -> None:
        @strategy(
            "test_always_in_extension",
            family="teste",
            description="Sinal de teste.",
        )
        def always_in(candles: list[Candle]) -> list[int]:
            return [1] * len(candles)

        extension = next(
            item
            for item in registered_strategies()
            if item.name == "test_always_in_extension"
        )
        self.assertEqual(extension.family, "teste")
        self.assertEqual(extension.function([]), [])

    def test_extension_parameters_must_have_defaults(self) -> None:
        with self.assertRaisesRegex(ValueError, "valor padrão"):
            @strategy(
                "test_required_parameter_extension",
                family="teste",
                description="Contrato inválido para a matriz.",
            )
            def invalid(candles: list[Candle], required: int) -> list[int]:
                return [int(required > 0)] * len(candles)


if __name__ == "__main__":
    unittest.main()
