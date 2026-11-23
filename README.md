
# Silent Deployment Failure Detection and Automated Release Recovery System

A Docker-based DevOps project that detects silent application failures and automatically restores traffic to a stable release.

## Problem
Traditional health checks may report a healthy application even when important business operations fail.

## Solution
ShopSphere simulates two application releases:
- V1: Stable checkout functionality
- V2: Healthy application with a broken discounted checkout

A Python detector compares checkout failure rates and automatically instructs a Flask traffic router to restore V1 when a regression is detected.

## Technologies
Python, Flask, Docker, Docker Compose, REST APIs, Git, GitHub

## Run
```bash
docker compose up -d --build
```

## Test Automatic Rollback

Switch traffic to V2:

```bash
curl -X POST http://localhost:8080/router/switch/v2
```

Run the detector:

```bash
docker compose exec shopsphere-v1 python /app/detector.py
```

Verify the active release:

```bash
curl http://localhost:8080/router/status
```

Expected active version: `v1`.

## Demonstrated Results
- Both releases pass health checks.
- V1 checkout failure rate: 0%.
- V2 checkout failure rate: 100%.
- Silent regression detected.
- Automatic traffic rollback to V1 confirmed.

## Current Scope
The detector runs on demand. Continuous monitoring and a live dashboard are future enhancements.
