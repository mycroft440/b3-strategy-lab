import unittest


class HistoricalIssuerRefreshPolicyTests(unittest.TestCase):
    def test_historical_issuer_policy_is_present(self):
        from pathlib import Path
        text = Path('scripts/sync_point_in_time_universe.py').read_text(encoding='utf-8')
        self.assertIn('last_quote_by_ticker', text)
        self.assertIn('historical_issuers', text)
        self.assertIn('historical_primary_registry', text)
        self.assertIn('if last_quote_by_ticker[ticker] == replay_end', text)


if __name__ == '__main__':
    unittest.main()
