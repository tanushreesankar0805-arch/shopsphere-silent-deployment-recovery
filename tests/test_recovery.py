
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import controller


class RecoveryTests(unittest.TestCase):

    def response(self, status, data):
        result = Mock()
        result.status_code = status
        result.json.return_value = data
        return result

    def checkout_response(self, version, scenario):
        if not scenario["valid"]:
            return self.response(
                400,
                {"status": "failed", "version": version}
            )

        return self.response(200, {
            "status": "success",
            "version": version,
            "product": scenario["product"],
            "original_price": controller.PRODUCT_PRICES[
                scenario["product"]
            ],
            "discount": scenario["discount"],
            "final_price": controller.expected_price(
                scenario["product"],
                scenario["discount"]
            )
        })

    def fake_checkout(self, version, faulty=False):
        def send(url, json, timeout):
            scenario = next(
                s for s in controller.SCENARIOS
                if s["product"] == json["product"]
                and s["discount"] == json["discount"]
                and type(s["discount"]) is type(json["discount"])
            )

            response = self.checkout_response(version, scenario)

            if faulty and scenario["valid"] and scenario["discount"] > 0:
                response.json.return_value["final_price"] = (
                    controller.PRODUCT_PRICES[scenario["product"]]
                )

            return response

        return send

    def test_all_valid_scenarios(self):
        for scenario in controller.SCENARIOS:
            if scenario["valid"]:
                self.assertTrue(
                    controller.validate_response(
                        self.checkout_response("v1", scenario),
                        "v1",
                        scenario
                    )
                )

    def test_all_invalid_scenarios(self):
        for scenario in controller.SCENARIOS:
            if not scenario["valid"]:
                self.assertTrue(
                    controller.validate_response(
                        self.checkout_response("v1", scenario),
                        "v1",
                        scenario
                    )
                )

    def test_wrong_price_detected(self):
        scenario = controller.SCENARIOS[0]
        response = self.checkout_response("v2", scenario)
        response.json.return_value["final_price"] = 1500

        self.assertFalse(
            controller.validate_response(response, "v2", scenario)
        )

    def test_wrong_version_detected(self):
        scenario = controller.SCENARIOS[0]

        self.assertFalse(
            controller.validate_response(
                self.checkout_response("v1", scenario),
                "v2",
                scenario
            )
        )

    def test_http_error_detected(self):
        self.assertFalse(
            controller.validate_response(
                self.response(500, {}),
                "v2",
                controller.SCENARIOS[0]
            )
        )

    def test_wrong_business_status_detected(self):
        scenario = controller.SCENARIOS[0]
        response = self.checkout_response("v1", scenario)
        response.json.return_value["status"] = "failed"

        self.assertFalse(
            controller.validate_response(response, "v1", scenario)
        )

    def test_invalid_input_accepted_is_failure(self):
        scenario = next(
            s for s in controller.SCENARIOS if not s["valid"]
        )

        self.assertFalse(
            controller.validate_response(
                self.response(
                    200,
                    {"status": "success", "version": "v2"}
                ),
                "v2",
                scenario
            )
        )

    def test_healthy_v1_probe(self):
        with patch.object(
            controller.requests,
            "post",
            side_effect=self.fake_checkout("v1")
        ):
            self.assertEqual(controller.probe("v1"), 0.0)

    def test_faulty_v2_probe(self):
        with patch.object(
            controller.requests,
            "post",
            side_effect=self.fake_checkout("v2", faulty=True)
        ):
            self.assertAlmostEqual(controller.probe("v2"), 0.4)

    def test_successful_recovery(self):
        with patch.object(
            controller.requests,
            "post",
            side_effect=self.fake_checkout("v1")
        ):
            self.assertTrue(controller.verify_recovery())

    def test_failed_recovery(self):
        with patch.object(
            controller.requests,
            "post",
            return_value=self.response(500, {})
        ):
            self.assertFalse(controller.verify_recovery())

    def test_stale_generation_rejected(self):
        with patch.object(
            controller,
            "get_release_status",
            return_value={
                "active_version": "v1",
                "release_generation": 2
            }
        ):
            with patch.object(controller.requests, "post") as post:
                self.assertFalse(controller.perform_rollback(1))
                post.assert_not_called()

    def test_successful_rollback(self):
        with patch.object(
            controller,
            "get_release_status",
            return_value={
                "active_version": "v2",
                "release_generation": 1
            }
        ):
            with patch.object(
                controller.requests,
                "post",
                return_value=self.response(200, {})
            ):
                with patch.object(
                    controller,
                    "verify_recovery",
                    return_value=True
                ):
                    self.assertTrue(controller.perform_rollback(1))

    def test_rollback_verification_failure(self):
        with patch.object(
            controller,
            "get_release_status",
            return_value={
                "active_version": "v2",
                "release_generation": 1
            }
        ):
            with patch.object(
                controller.requests,
                "post",
                return_value=self.response(200, {})
            ):
                with patch.object(
                    controller,
                    "verify_recovery",
                    return_value=False
                ):
                    with self.assertRaises(RuntimeError):
                        controller.perform_rollback(1)

    def test_healthy_release_decision(self):
        decision, count = controller.evaluate_release(0.0, 0.0, 0)
        self.assertEqual(decision, "HEALTHY")
        self.assertEqual(count, 0)

    def test_transient_failure_does_not_rollback(self):
        decision, count = controller.evaluate_release(0.0, 0.4, 0)
        self.assertEqual(decision, "MONITORING")
        self.assertEqual(count, 1)

        decision, count = controller.evaluate_release(0.0, 0.0, count)
        self.assertEqual(decision, "HEALTHY")
        self.assertEqual(count, 0)

    def test_confirmed_regression_triggers_rollback(self):
        decision, count = controller.evaluate_release(0.0, 0.4, 0)
        self.assertEqual(decision, "MONITORING")

        decision, count = controller.evaluate_release(0.0, 0.4, count)
        self.assertEqual(decision, "ROLLBACK")
        self.assertEqual(count, 2)

    def test_unhealthy_baseline_blocks_rollback(self):
        decision, count = controller.evaluate_release(0.2, 0.6, 1)
        self.assertEqual(decision, "BLOCKED")
        self.assertEqual(count, 0)

    def test_equal_failure_rates_do_not_trigger_rollback(self):
        decision, count = controller.evaluate_release(0.05, 0.05, 0)
        self.assertEqual(decision, "HEALTHY")
        self.assertEqual(count, 0)

    def test_generation_conflict_rejected(self):
        with patch.object(
            controller,
            "get_release_status",
            return_value={
                "active_version": "v2",
                "release_generation": 1
            }
        ):
            with patch.object(
                controller.requests,
                "post",
                return_value=self.response(409, {})
            ):
                self.assertFalse(controller.perform_rollback(1))


if __name__ == "__main__":
    unittest.main()
