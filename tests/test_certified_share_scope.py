from __future__ import annotations

import unittest
from types import SimpleNamespace

from b3_strategy_lab.point_in_time import is_company_equity


class CertifiedShareScopeTests(unittest.TestCase):
    def _quote(self, ticker: str, specification: str):
        return SimpleNamespace(ticker=ticker, specification=specification)

    def test_on_and_pn_share_classes_are_eligible(self) -> None:
        self.assertTrue(is_company_equity(self._quote("ABCD3", "ON")))
        self.assertTrue(is_company_equity(self._quote("ABCD4", "PN")))
        self.assertTrue(is_company_equity(self._quote("ABCD5", "PNA")))

    def test_units_are_excluded_from_certified_small_account_tax_scope(self) -> None:
        self.assertFalse(is_company_equity(self._quote("ABCD11", "UNT")))

    def test_non_share_security_is_excluded(self) -> None:
        self.assertFalse(is_company_equity(self._quote("ABCD11", "BDR")))


if __name__ == "__main__":
    unittest.main()
