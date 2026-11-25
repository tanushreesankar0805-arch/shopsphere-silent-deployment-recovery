# ShopSphere — Silent Deployment Failure Detection & Automated Release Recovery

**Pre-PEM DevOps Project | AWS EC2 Hosting Implemented**

**Live storefront (HTTP):** http://13.201.18.82/  
**GitHub:** https://github.com/tanushreesankar0805-arch/shopsphere-silent-deployment-recovery

> AWS EC2 hosting is implemented and the public ShopSphere storefront was opened successfully in a browser. The public IP may change when the EC2 instance is stopped and restarted. HTTPS and an EC2-based rollback exercise have not yet been verified.

## Problem statement

Traditional health checks can report `HTTP 200 OK` even when an application is producing incorrect business results. ShopSphere demonstrates this using a deliberately faulty candidate checkout release (V2) and a stable baseline (V1). A recovery controller compares their business outcomes, confirms persistent regression, and safely restores traffic to V1.

## System architecture

```text
GitHub --> Jenkins CI --> Checkout source --> Install dependencies --> 24 tests
                |
                +--> Activate already-running candidate V2 on local release router
                +--> Verify controller automatically returns traffic to V1

AWS EC2 (Mumbai, ap-south-1)
   |
   +--> Ubuntu VM --> Docker Compose
   |                   |--> Flask ShopSphere V1 (stable)
   |                   |--> Flask ShopSphere V2 (faulty candidate)
   |                   |--> Release Router (localhost:8080)
   |                   |--> Recovery Controller
   |                   |--> Prometheus
   |                   +--> Grafana
   |
   +--> Nginx :80 --> localhost:8080 --> Public ShopSphere storefront

Recovery Controller --> 10 semantic checkout scenarios
                    --> Compare baseline vs candidate
                    --> Confirm consecutive regressions
                    --> Block unsafe rollback
                    --> Generation-guarded V2 to V1 rollback
                    --> Persistent incident records (JSONL)

Prometheus --> Metrics --> Grafana
```

## Technology stack

| Technology | Purpose | Status |
| --- | --- | --- |
| **AWS EC2 (ap-south-1)** | Host the containerized ShopSphere environment | **Implemented** |
| **Ubuntu Linux** | EC2 operating system | **Implemented** |
| **Nginx** | Public HTTP reverse proxy for the storefront | **Implemented** |
| Python and Flask | Checkout service, router and recovery controller | Implemented |
| Docker and Docker Compose | Container deployment of six services | Implemented |
| Git and GitHub | Source control and cloud source checkout | Implemented |
| Jenkins | Automated tests and local release/recovery verification | Implemented |
| Prometheus | Metrics collection | Implemented |
| Grafana | Monitoring dashboards | Implemented |
| Python `unittest` | Automated testing | Implemented |

## Implemented functionality

- Two ShopSphere application versions: stable V1 and deliberately faulty V2.
- Release router to switch traffic between V1 and V2.
- Ten business-level checkout scenarios, testing both expected prices and invalid inputs.
- Detection of silent failures even if the API returns HTTP 200.
- Baseline-aware, consecutive-failure decision engine to reduce false rollback.
- Generation-guarded release changes to avoid acting on stale release state.
- Safety block when the stable baseline is unhealthy.
- Automatic V2-to-V1 traffic rollback with recovery verification.
- JSONL incident history and Prometheus/Grafana observability.
- Jenkins pipeline with GitHub checkout, isolated dependency installation, 24 automated tests, candidate activation and observed automatic recovery in the **local** Docker environment.
- **AWS EC2 deployment:** repository cloned onto the instance, Docker and Docker Compose installed, six services started, Nginx configured and the HTTP storefront accessible through the instance public IP.

## Verified results

| Verification | Observed result |
| --- | --- |
| Baseline V1 failure rate | 0% in local semantic tests |
| Faulty V2 failure rate | 40% in local semantic tests |
| Jenkins automated tests | **24/24 PASSED** (final observed build: 0.278 s) |
| Jenkins local release activation | V2, release generation 7 |
| Jenkins local recovery validation | V1 restored, release generation 8 |
| Jenkins build result | **SUCCESS** |
| Unsafe baseline | Rollback blocked in chaos validation |
| Stale generation | HTTP 409; release unchanged |
| Incident persistence | Survived controller restart/recreation |
| EC2 Docker Compose | **All six services running** |
| Public EC2 storefront | **Accessible at http://13.201.18.82/** after allowing inbound HTTP TCP/80 |
| EC2 live V2-to-V1 rollback | **Not separately validated yet** |

**Timing note:** Earlier local live tests measured approximately 0.12–0.23 seconds for the rollback action and verification, not end-to-end failure detection. Jenkins's recovery observation occurred on a subsequent polling iteration. Unit tests include mocked scenarios.

**Release semantics:** Jenkins activates an already-running V2 container; it does not yet build a fresh container image and deploy it to EC2. The AWS deployment was carried out through SSH and Docker Compose.

## Reproduce locally

Prerequisites: Docker / Docker Compose, Git, and Python 3.12+ for local tests.

```bash
git clone https://github.com/tanushreesankar0805-arch/shopsphere-silent-deployment-recovery.git
cd shopsphere-silent-deployment-recovery
docker compose up -d --build
docker compose ps
python -m pip install -r requirements.txt
python -m unittest discover -s tests -q
```

Local-only services are bound to `127.0.0.1` in the Compose file:

- ShopSphere router: http://localhost:8080
- Router status: http://localhost:8080/router/status
- Prometheus: http://localhost:9091
- Grafana: http://localhost:3001
- Controller metrics: http://localhost:9100/metrics

## AWS EC2 deployment (implemented)

**Environment:** AWS EC2 in Mumbai (`ap-south-1`), Ubuntu Linux, Git, Docker 29.1.3, Docker Compose 2.40.3, Nginx, ShopSphere application stack.

```bash
# Commands used on the Ubuntu EC2 instance:
sudo apt update
sudo apt install -y docker.io git docker-compose-v2 nginx
sudo systemctl enable --now docker
git clone https://github.com/tanushreesankar0805-arch/shopsphere-silent-deployment-recovery.git
cd shopsphere-silent-deployment-recovery
sudo docker compose up -d --build
sudo docker compose ps
```

**EC2 runtime result:** All six containers started: `shopsphere-v1`, `shopsphere-v2`, `shopsphere-router`, `recovery-controller`, `prometheus`, and `grafana`.

**Public access:** Nginx listens on TCP/80 and proxies storefront traffic to the local-only router at `127.0.0.1:8080`. The EC2 security group's inbound HTTP rule was configured for TCP/80, and the website became accessible at **http://13.201.18.82/**.

**Security:** SSH TCP/22 should be restricted to the operator's IP. Keep Compose ports 8080, 5001, 5002, 9100, 9091 and 3001 closed to the internet. The public Nginx configuration should deny `/router` and `/router/` control routes and `/metrics`. Never commit `.pem` keys or AWS credentials. The shared Jenkins SSH credential should be rotated. This demo uses HTTP; add a domain and TLS/HTTPS before production use.

**Operational notes:** EC2 instance charges and public IPv4 charges can apply. The public IP may change after instance stop/start unless an Elastic IP is configured. `t3.small` or other small instances may be resource-constrained when hosting all six containers.

## Current project status

**Completed and verified:** core semantic failure detection, safety-aware rollback, incident evidence, monitoring, local Jenkins release/recovery validation, and **AWS EC2 hosting with public storefront access**.

**Further hardening / demo preparation:** verify a full V2-to-V1 rollback separately on EC2, rotate the exposed Jenkins SSH key, save the Jenkins pipeline in a `Jenkinsfile`, set up HTTPS, and capture final AWS cloud evidence.

## Repository

https://github.com/tanushreesankar0805-arch/shopsphere-silent-deployment-recovery
