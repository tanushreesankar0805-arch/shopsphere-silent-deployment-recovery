
import json
import urllib.error
import urllib.request

V1_URL = "http://shopsphere-v1:5000"
V2_URL = "http://shopsphere-v2:5000"
ROUTER_URL = "http://shopsphere-router:8080"

TEST_REQUESTS = 20
FAILURE_THRESHOLD = 10.0


def check_health(base_url):
    try:
        with urllib.request.urlopen(
            f"{base_url}/health", timeout=3
        ) as response:
            data = json.load(response)
            return data.get("status") == "healthy"
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def test_checkout(base_url):
    payload = json.dumps({
        "product": "headphones",
        "discount": 10
    }).encode("utf-8")

    request = urllib.request.Request(
        f"{base_url}/checkout",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request, timeout=3
        ) as response:
            data = json.load(response)
            return (
                response.status == 200
                and data.get("status") == "success"
                and data.get("final_price") == 1350
            )
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def measure(base_url):
    failures = 0

    for _ in range(TEST_REQUESTS):
        if not test_checkout(base_url):
            failures += 1

    return round(failures / TEST_REQUESTS * 100, 2)


def rollback():
    print("\nExecuting automatic rollback...")

    request = urllib.request.Request(
        f"{ROUTER_URL}/router/switch/v1",
        data=b"",
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request, timeout=5
        ) as response:
            result = json.load(response)

        if result.get("active_version") == "v1":
            print("SUCCESS: Traffic restored to V1!")
        else:
            print("ERROR: Rollback not confirmed.")

    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        print(f"ERROR: Rollback failed: {error}")


def main():
    print("\nSHOPSPHERE AUTOMATED RELEASE RECOVERY")
    print("=" * 45)

    v1_healthy = check_health(V1_URL)
    v2_healthy = check_health(V2_URL)

    print(f"V1 health check: {v1_healthy}")
    print(f"V2 health check: {v2_healthy}")

    print("\nRunning checkout tests...")

    v1_failures = measure(V1_URL)
    v2_failures = measure(V2_URL)

    print(f"V1 failure rate: {v1_failures}%")
    print(f"V2 failure rate: {v2_failures}%")

    print("\nRELEASE DECISION")
    print("-" * 45)

    if not v1_healthy:
        print("PAUSE: Stable baseline is unhealthy.")

    elif not v2_healthy:
        print("ROLLBACK: New release is unhealthy!")
        rollback()

    elif v1_failures > FAILURE_THRESHOLD:
        print("PAUSE: Baseline failure rate is too high.")

    elif v2_failures - v1_failures > FAILURE_THRESHOLD:
        print("ROLLBACK: Silent regression detected!")
        rollback()

    else:
        print("PROMOTE: No significant regression detected.")


if __name__ == "__main__":
    main()
