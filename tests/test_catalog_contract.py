from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from b3_strategy_lab.catalog_contract import (
    DEFAULT_CATALOG_CONTRACT,
    runtime_catalog_contract,
    validate_catalog_contract,
)


class CatalogContractTests(unittest.TestCase):
    def test_checked_in_contract_exactly_matches_runtime_catalog(self) -> None:
        payload = validate_catalog_contract(DEFAULT_CATALOG_CONTRACT)
        self.assertEqual(payload["strategy_count"], 234)
        self.assertEqual(payload["management_count"], 478)
        self.assertEqual(payload["candidate_count"], 111_852)

    def test_tampered_contract_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            payload = runtime_catalog_contract()
            payload["strategy_count"] = 190
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "differs from its checked-in contract"):
                validate_catalog_contract(path)


if __name__ == "__main__":
    unittest.main()

