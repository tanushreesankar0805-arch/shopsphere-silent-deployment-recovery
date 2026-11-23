# ShopSphere — Silent Deployment Failure Detection & Automated Release Recovery

A local-first DevOps reliability project that detects **silent business-logic regressions**: deployments that return HTTP 200 but produce incorrect checkout results. The system compares candidate release V2 with baseline V1 and automatically restores V1 when a confirmed regression makes V2 unsafe.

## Problem statement

Traditional availability checks can miss functional defects. A checkout service can be reachable and still calculate the wrong price. ShopSphere checks **business correctness**, not merely HTTP availability.

## Architecture

```text
GitHub --> Jenkins CI --> Python unit tests (24 passing)
                             |
                 ShopSphere V1 and V2 (Docker)
                             |
                       Release Router
                             |
                  Customer checkout requests

Recovery Controller --> Semantic checkout probes (10 scenarios)
                    --> Compare V2 with V1 baseline
                    --> Confirm persistent regression
                    --> Safety checks and generation guard
                    --> Switch traffic to V1 and verify
                    --> Persistent JSONL incident evidence

Prometheus --> Monitoring metrics --> Grafana
```

## Implemented features

- Docker Compose deployment of ShopSphere V1, V2, router, recovery controller, Prometheus, and Grafana.
- Ten checkout scenarios covering valid and invalid input, including expected final prices.
- Semantic validation of checkout payloads, HTTP status, version, discount, and price.
- Baseline-aware decision engine requiring consecutive failing evaluations.
- Automated rollback with release-generation concurrency protection and post-rollback verification.
- Persistent incident history with failure evidence and recovery events.
- Reliability tests for unhealthy baseline, transient failures, stale generation, and persistence.
- GitHub-backed Jenkins pipeline: **24 automated tests passed**.

## Verified demonstration results

| Check | Observed result |
| --- | --- |
| Baseline V1 semantic failure rate | 0% |
| Intentionally faulty V2 semantic failure rate | 40% |
| Automatic recovery | V2 → V1, verified |
| Unsafe baseline | Rollback blocked |
| Stale release generation | HTTP 409; production unchanged |
| Incident persistence | Survived controller recreation |
| Jenkins CI | 24/24 tests passed (0.223 s in observed build) |
| Rollback and verification | ~0.12–0.23 s in observed runs |

> Recovery timing above measures rollback and verification, **not** end-to-end detection time. Some automated tests use mocks; live Docker behavior was validated separately.

## Technology stack

Python, Flask, Docker Compose, Git, GitHub, Jenkins, Prometheus, Grafana, and Python `unittest`.

## Run locally

Requirements: Docker Desktop and Docker Compose.

```bash
docker compose up -d --build
docker compose ps
python -m pip install -r requirements.txt
python -m unittest discover -s tests -q
```

Local endpoints:

- ShopSphere router: http://localhost:8080
- Release status: http://localhost:8080/router/status
- Prometheus: http://localhost:9091
- Grafana: http://localhost:3001
- Controller metrics: http://localhost:9100/metrics

To inspect the current release:

```bash
curl http://localhost:8080/router/status
```

> V2 intentionally contains a checkout regression for demonstration. Deploying V2 to the active router can trigger automatic rollback. Use only in the local lab environment.

## Project status

**Completed:** business-aware failure detection, release safety decisions, automatic recovery, persistent evidence, chaos validation, GitHub integration, and Jenkins test pipeline.

**Remaining:** Jenkins-driven release deployment demonstration, rotation of an exposed development SSH credential, and final submission evidence.

## Repository

https://github.com/tanushreesankar0805-arch/shopsphere-silent-deployment-recovery
