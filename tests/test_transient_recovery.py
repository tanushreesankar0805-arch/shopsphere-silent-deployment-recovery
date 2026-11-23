
import unittest

from controller import evaluate_release


class TestTransientRecovery(unittest.TestCase):

    def test_single_failure_does_not_rollback(self):
        decision, consecutive = evaluate_release(
            0.0, 0.4, 0
        )

        self.assertEqual(decision, "MONITORING")
        self.assertEqual(consecutive, 1)

    def test_recovery_resets_failure_counter(self):
        decision, consecutive = evaluate_release(
            0.0, 0.4, 0
        )

        self.assertEqual(decision, "MONITORING")

        decision, consecutive = evaluate_release(
            0.0, 0.0, consecutive
        )

        self.assertEqual(decision, "HEALTHY")
        self.assertEqual(consecutive, 0)

    def test_two_consecutive_failures_trigger_rollback(self):
        decision, consecutive = evaluate_release(
            0.0, 0.4, 0
        )

        self.assertEqual(decision, "MONITORING")

        decision, consecutive = evaluate_release(
            0.0, 0.4, consecutive
        )

        self.assertEqual(decision, "ROLLBACK")
        self.assertEqual(consecutive, 2)

    def test_unhealthy_baseline_blocks_rollback(self):
        decision, consecutive = evaluate_release(
            1.0, 0.4, 1
        )

        self.assertEqual(decision, "BLOCKED")
        self.assertEqual(consecutive, 0)


if __name__ == "__main__":
    unittest.main()
