from __future__ import annotations

import unittest
from unittest.mock import patch

from b3_strategy_lab.b3_official import B3CorporateActionError
from scripts import sync_point_in_time_universe_realistic as realistic


class RealisticSyncRetryPolicyTests(unittest.TestCase):
    def test_deterministic_b3_validation_error_is_not_retried(self) -> None:
        error = B3CorporateActionError("BRML3: evidencia local deterministica invalida")
        with (
            patch.object(realistic, "_load_evidence_addendum", return_value={}),
            patch.object(realistic, "_install_evidence_addendum"),
            patch.object(realistic.base, "main", side_effect=error) as main,
            patch.object(realistic.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(B3CorporateActionError, "deterministica"):
                realistic.main([])
        self.assertEqual(main.call_count, 1)
        sleep.assert_not_called()

    def test_exhausted_b3_transport_error_retries_with_bounded_delays(self) -> None:
        error = B3CorporateActionError(
            "Falha ao consultar eventos oficiais de TEST: timed out"
        )
        with (
            patch.object(realistic, "_load_evidence_addendum", return_value={}),
            patch.object(realistic, "_install_evidence_addendum"),
            patch.object(realistic.base, "main", side_effect=error) as main,
            patch.object(realistic.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(B3CorporateActionError, "TEST"):
                realistic.main([])
        self.assertEqual(main.call_count, realistic.SYNC_ATTEMPTS)
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            list(realistic.SYNC_RETRY_DELAYS_SECONDS),
        )

    def test_retry_classifier_is_fail_closed_for_unrecognized_errors(self) -> None:
        self.assertTrue(
            realistic._is_retryable_b3_transport_error(
                B3CorporateActionError(
                    "Falha ao consultar eventos oficiais de ABCD: timeout"
                )
            )
        )
        self.assertFalse(
            realistic._is_retryable_b3_transport_error(
                B3CorporateActionError(
                    "ABCD3: fonte suplementar precisa ser CVM ou issuer."
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
