
import os
import time
import logging
import requests

from prometheus_client import start_http_server, Counter, Gauge, Histogram
from incident_store import record_incident, count_incidents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

ROUTER = os.getenv("ROUTER_URL", "http://shopsphere-router:8080")

BACKENDS = {
    "v1": "http://shopsphere-v1:5000",
    "v2": "http://shopsphere-v2:5000"
}

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "5"))
SAMPLE_SIZE = int(os.getenv("SAMPLE_SIZE", "10"))
FAILURE_THRESHOLD = float(os.getenv("FAILURE_THRESHOLD", "0.10"))
CONSECUTIVE_FAILURES = int(os.getenv("CONSECUTIVE_FAILURES", "2"))
BASELINE_MAX_FAILURE = float(os.getenv("BASELINE_MAX_FAILURE", "0.10"))

PRODUCT_PRICES = {
    "headphones": 1500,
    "keyboard": 2000,
    "mouse": 800
}

SCENARIOS = [
    {"product": "headphones", "discount": 10, "valid": True},
    {"product": "keyboard", "discount": 20, "valid": True},
    {"product": "mouse", "discount": 25, "valid": True},
    {"product": "headphones", "discount": 0, "valid": True},
    {"product": "keyboard", "discount": 100, "valid": True},
    {"product": "unknown", "discount": 10, "valid": False},
    {"product": "mouse", "discount": -5, "valid": False},
    {"product": "headphones", "discount": 110, "valid": False},
    {"product": "keyboard", "discount": "ten", "valid": False},
    {"product": "mouse", "discount": True, "valid": False}
]

rollback_total = Counter(
    "shopsphere_automatic_rollbacks_total",
    "Successful automatic release rollbacks"
)

regression_detected = Gauge(
    "shopsphere_regression_detected",
    "Whether a release regression is detected"
)

active_release = Gauge(
    "shopsphere_active_release",
    "Active production release",
    ["version"]
)

checkout_failure_rate = Gauge(
    "shopsphere_probe_failure_rate",
    "Semantic checkout failure rate",
    ["version"]
)

recovery_duration = Histogram(
    "shopsphere_recovery_duration_seconds",
    "Rollback and recovery verification duration"
)

scenario_failure = Gauge(
    "shopsphere_scenario_failure",
    "Latest failure rate per business scenario",
    ["version", "scenario"]
)

rollback_blocked = Counter(
    "shopsphere_rollback_blocked_total",
    "Rollbacks blocked for safety",
    ["reason"]
)

release_decision = Gauge(
    "shopsphere_release_decision",
    "Decision state: 0 healthy, 1 monitoring, 2 rollback, 3 blocked"
)

incident_events = Counter(
    "shopsphere_incident_events_total",
    "Recorded incident events",
    ["event_type"]
)

incident_history_count = Gauge(
    "shopsphere_incident_history_count",
    "Total persisted incident events"
)

for version in BACKENDS:
    active_release.labels(version=version).set(0)
    checkout_failure_rate.labels(version=version).set(0)


def save_event(event_type, **details):
    try:
        event = record_incident(event_type, **details)
        incident_events.labels(event_type=event_type).inc()
        incident_history_count.set(count_incidents())
        return event
    except Exception:
        logging.exception(
            "Incident persistence failed | event=%s",
            event_type
        )
        return None


def get_release_status():
    response = requests.get(
        f"{ROUTER}/router/status",
        timeout=3
    )
    response.raise_for_status()
    return response.json()


def expected_price(product, discount):
    return round(
        PRODUCT_PRICES[product] * (1 - discount / 100),
        2
    )


def validate_response(response, version, scenario):
    if scenario["valid"]:
        if response.status_code != 200:
            return False

        result = response.json()

        if not isinstance(result, dict):
            return False

        actual = result.get("final_price")

        return (
            result.get("status") == "success"
            and result.get("version") == version
            and result.get("product") == scenario["product"]
            and result.get("original_price") == PRODUCT_PRICES[scenario["product"]]
            and result.get("discount") == scenario["discount"]
            and type(actual) in (int, float)
            and abs(
                actual - expected_price(
                    scenario["product"],
                    scenario["discount"]
                )
            ) <= 0.001
        )

    if response.status_code != 400:
        return False

    result = response.json()

    return (
        isinstance(result, dict)
        and result.get("status") == "failed"
        and result.get("version") == version
    )


def probe(version):
    failures = 0
    total = 0

    for scenario in SCENARIOS:
        scenario_failures = 0
        evidence = None

        scenario_name = (
            f"{scenario['product']}_{scenario['discount']}"
        )

        for _ in range(SAMPLE_SIZE):
            total += 1

            try:
                response = requests.post(
                    f"{BACKENDS[version]}/checkout",
                    json={
                        "product": scenario["product"],
                        "discount": scenario["discount"]
                    },
                    timeout=3
                )

                passed = validate_response(
                    response,
                    version,
                    scenario
                )

                if not passed and evidence is None:
                    try:
                        actual_response = response.json()
                    except ValueError:
                        actual_response = {
                            "error": "Non-JSON response"
                        }

                    evidence = {
                        "http_status": response.status_code,
                        "actual_response": actual_response
                    }

            except (
                requests.RequestException,
                ValueError,
                TypeError
            ) as error:
                passed = False

                if evidence is None:
                    evidence = {
                        "error": str(error)
                    }

            if not passed:
                failures += 1
                scenario_failures += 1

                logging.warning(
                    "SEMANTIC FAILURE | version=%s | scenario=%s",
                    version,
                    scenario_name
                )

        failure_fraction = scenario_failures / SAMPLE_SIZE

        scenario_failure.labels(
            version=version,
            scenario=scenario_name
        ).set(failure_fraction)

        if scenario_failures > 0:
            expected = None

            if scenario["valid"]:
                expected = expected_price(
                    scenario["product"],
                    scenario["discount"]
                )

            save_event(
                "SCENARIO_FAILURE",
                version=version,
                scenario=scenario_name,
                product=scenario["product"],
                discount=scenario["discount"],
                expected_http_status=200 if scenario["valid"] else 400,
                expected_price=expected,
                failures=scenario_failures,
                samples=SAMPLE_SIZE,
                evidence=evidence
            )

    failure_rate = failures / total

    checkout_failure_rate.labels(
        version=version
    ).set(failure_rate)

    return failure_rate


def verify_recovery():
    for scenario in SCENARIOS:
        try:
            response = requests.post(
                f"{ROUTER}/checkout",
                json={
                    "product": scenario["product"],
                    "discount": scenario["discount"]
                },
                timeout=3
            )

            if not validate_response(
                response,
                "v1",
                scenario
            ):
                return False

        except (
            requests.RequestException,
            ValueError,
            TypeError
        ):
            return False

    return True


def evaluate_release(v1_rate, v2_rate, consecutive):
    if v1_rate >= BASELINE_MAX_FAILURE:
        return "BLOCKED", 0

    difference = v2_rate - v1_rate

    if difference <= FAILURE_THRESHOLD:
        return "HEALTHY", 0

    consecutive += 1

    if consecutive >= CONSECUTIVE_FAILURES:
        return "ROLLBACK", consecutive

    return "MONITORING", consecutive


def perform_rollback(expected_generation):
    logging.warning(
        "ROLLBACK REQUESTED | generation=%s",
        expected_generation
    )

    status = get_release_status()

    if (
        status["active_version"] != "v2"
        or status["release_generation"] != expected_generation
    ):
        rollback_blocked.labels(reason="stale_release").inc()

        save_event(
            "ROLLBACK_BLOCKED",
            reason="stale_release",
            expected_generation=expected_generation,
            observed_generation=status["release_generation"],
            active_version=status["active_version"]
        )

        logging.warning("ROLLBACK BLOCKED | release changed")
        return False

    save_event(
        "ROLLBACK_STARTED",
        failed_version="v2",
        target_version="v1",
        release_generation=expected_generation
    )

    start = time.monotonic()

    try:
        response = requests.post(
            f"{ROUTER}/router/switch/v1",
            json={
                "expected_generation": expected_generation
            },
            timeout=3
        )

        if response.status_code == 409:
            rollback_blocked.labels(
                reason="generation_conflict"
            ).inc()

            save_event(
                "ROLLBACK_BLOCKED",
                reason="generation_conflict",
                release_generation=expected_generation
            )

            logging.warning(
                "ROLLBACK CANCELLED | generation conflict"
            )
            return False

        response.raise_for_status()

        if not verify_recovery():
            raise RuntimeError(
                "Rollback verification failed"
            )

    except Exception as error:
        save_event(
            "ROLLBACK_FAILED",
            failed_version="v2",
            target_version="v1",
            release_generation=expected_generation,
            error=str(error)
        )
        raise

    duration = time.monotonic() - start

    rollback_total.inc()
    recovery_duration.observe(duration)
    regression_detected.set(0)
    release_decision.set(0)

    save_event(
        "ROLLBACK_SUCCESS",
        failed_version="v2",
        restored_version="v1",
        release_generation=expected_generation,
        recovery_seconds=round(duration, 4),
        verification="passed"
    )

    logging.info(
        "AUTOMATIC ROLLBACK SUCCESS | V1 restored in %.3f seconds",
        duration
    )

    return True


def main():
    start_http_server(9100)

    incident_history_count.set(count_incidents())

    logging.info(
        "ShopSphere Incident-Aware Recovery Controller started"
    )

    consecutive = 0
    observed_generation = None

    while True:
        try:
            status = get_release_status()

            active = status["active_version"]
            generation = status["release_generation"]

            if generation != observed_generation:
                consecutive = 0
                observed_generation = generation

                logging.info(
                    "Release generation=%s | active=%s",
                    generation,
                    active
                )

                save_event(
                    "RELEASE_OBSERVED",
                    active_version=active,
                    release_generation=generation
                )

            for version in BACKENDS:
                active_release.labels(version=version).set(
                    1 if version == active else 0
                )

            if active == "v2":
                v1_rate = probe("v1")
                v2_rate = probe("v2")

                decision, consecutive = evaluate_release(
                    v1_rate,
                    v2_rate,
                    consecutive
                )

                logging.info(
                    "V1=%.1f%% | V2=%.1f%% | decision=%s",
                    v1_rate * 100,
                    v2_rate * 100,
                    decision
                )

                if decision == "BLOCKED":
                    release_decision.set(3)
                    regression_detected.set(0)

                    rollback_blocked.labels(
                        reason="unhealthy_baseline"
                    ).inc()

                    save_event(
                        "ROLLBACK_BLOCKED",
                        reason="unhealthy_baseline",
                        release_generation=generation,
                        v1_failure_rate=v1_rate,
                        v2_failure_rate=v2_rate
                    )

                    logging.warning(
                        "ROLLBACK BLOCKED | V1 baseline unhealthy"
                    )

                elif decision == "HEALTHY":
                    release_decision.set(0)
                    regression_detected.set(0)

                elif decision == "MONITORING":
                    release_decision.set(1)
                    regression_detected.set(1)

                    save_event(
                        "REGRESSION_SUSPECTED",
                        release_generation=generation,
                        v1_failure_rate=v1_rate,
                        v2_failure_rate=v2_rate,
                        confirmation=consecutive
                    )

                    logging.warning(
                        "Regression confirmation (%d/%d)",
                        consecutive,
                        CONSECUTIVE_FAILURES
                    )

                elif decision == "ROLLBACK":
                    release_decision.set(2)
                    regression_detected.set(1)

                    save_event(
                        "REGRESSION_CONFIRMED",
                        release_generation=generation,
                        v1_failure_rate=v1_rate,
                        v2_failure_rate=v2_rate,
                        confirmation=consecutive
                    )

                    logging.warning(
                        "REGRESSION CONFIRMED | automatic recovery"
                    )

                    latest_v1_rate = probe("v1")

                    if latest_v1_rate >= BASELINE_MAX_FAILURE:
                        rollback_blocked.labels(
                            reason="baseline_recheck_failed"
                        ).inc()

                        save_event(
                            "ROLLBACK_BLOCKED",
                            reason="baseline_recheck_failed",
                            release_generation=generation,
                            v1_failure_rate=latest_v1_rate
                        )

                        release_decision.set(3)
                        regression_detected.set(0)
                        consecutive = 0

                        logging.warning(
                            "ROLLBACK BLOCKED | baseline recheck failed"
                        )

                    else:
                        perform_rollback(generation)
                        consecutive = 0

            else:
                consecutive = 0
                regression_detected.set(0)
                release_decision.set(0)

        except Exception as error:
            logging.exception(
                "Release evaluation failed"
            )

            save_event(
                "CONTROLLER_ERROR",
                error=str(error)
            )

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
