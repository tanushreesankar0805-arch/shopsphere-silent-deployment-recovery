
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

# Allow tests to import controller.py
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1])
)

import controller


class RecoveryTests(unittest.TestCase):

    def test_healthy_v1_checkout(self):
        """Healthy V1 checkout should have 0% failures."""

        response = Mock(status_code=200)

        with patch.object(
            controller.requests,
            "post",
            return_value=response
        ) as post:

            failure_rate = controller.probe("v1")

        self.assertEqual(failure_rate, 0.0)
        self.assertEqual(
            post.call_count,
            controller.SAMPLE_SIZE
        )

    def test_faulty_v2_checkout(self):
        """Faulty V2 checkout should have 100% failures."""

        response = Mock(status_code=500)

        with patch.object(
            controller.requests,
            "post",
            return_value=response
        ):

            failure_rate = controller.probe("v2")

        self.assertEqual(failure_rate, 1.0)

    def test_successful_recovery_verification(self):
        """V1 checkout success confirms recovery."""

        response = Mock(status_code=200)
        response.json.return_value = {
            "version": "v1"
        }

        with patch.object(
            controller.requests,
            "post",
            return_value=response
        ):

            result = controller.verify_recovery()

        self.assertTrue(result)

    def test_failed_recovery_verification(self):
        """Failed checkout must not count as recovery."""

        response = Mock(status_code=500)

        with patch.object(
            controller.requests,
            "post",
            return_value=response
        ):

            result = controller.verify_recovery()

        self.assertFalse(result)

    def test_stale_rollback_is_rejected(self):
        """Generation conflict must cancel rollback."""

        response = Mock(status_code=409)

        with patch.object(
            controller.requests,
            "post",
            return_value=response
        ):

            result = controller.perform_rollback(
                expected_generation=1
            )

        self.assertFalse(result)

    def test_successful_automatic_rollback(self):
        """Rollback should succeed after verification."""

        response = Mock(status_code=200)

        with patch.object(
            controller.requests,
            "post",
            return_value=response
        ), patch.object(
            controller,
            "verify_recovery",
            return_value=True
        ) as verify:

            result = controller.perform_rollback(
                expected_generation=1
            )

        self.assertTrue(result)
        verify.assert_called_once()

    def test_rollback_verification_failure(self):
        """Failed recovery verification must raise an error."""

        response = Mock(status_code=200)

        with patch.object(
            controller.requests,
            "post",
            return_value=response
        ), patch.object(
            controller,
            "verify_recovery",
            return_value=False
        ):

            with self.assertRaises(RuntimeError):
                controller.perform_rollback(
                    expected_generation=1
                )


if __name__ == "__main__":
    unittest.main()
