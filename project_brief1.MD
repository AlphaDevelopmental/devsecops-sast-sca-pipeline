# Project Topic: DevSecOps SAST/SCA/Secrets/Container Security Gate Pipeline (Project 1)

## Overview

Build a CI/CD pipeline on GitHub Actions that enforces four automated, blocking security controls on every push to a small, deliberately vulnerable application. The goal is to demonstrate that a "DevSecOps pipeline" is not a marketing term — each gate must catch a genuine, real vulnerability, fail the build, and only pass once that vulnerability is actually fixed. No synthetic or staged findings.

## Prerequisites

- Python 3.10+
- Git and a GitHub account
- Docker installed
- A GitHub repository with Actions enabled

## What to Build

### 1. Target Application (deliberately vulnerable, seeded on purpose)

A small Flask app (`app.py`) with one intentional flaw seeded per security control you plan to test. Minimum recommended:
- A route that builds a raw SQL query via string concatenation from user input (SQL injection, CWE-89)
- A hardcoded credential/API key/token as a literal string in the source code

A `requirements.txt` pinned to old versions of real packages that carry known CVEs (e.g. an old Flask release with a documented CVE).

### 2. Secrets Detection — Gitleaks

Add a job to `.github/workflows/security.yml` that runs Gitleaks against the full git history on every push. It should fail the build the moment a hardcoded secret is detected.

**Known pitfall to be aware of:** Gitleaks (and most secret scanners) allowlist well-known documentation placeholder values (e.g. AWS's official example access key). If you seed a "fake" secret using a placeholder value copied from documentation, it may not be detected — use a realistic-looking but non-placeholder value to get a genuine positive.

### 3. Static Application Security Testing (SAST) — Semgrep

Add a job running Semgrep against the codebase. Start with a lightweight ruleset and observe what it catches — then deliberately test whether it catches your seeded SQL injection. If not, switch to a stronger ruleset (e.g. `p/security-audit` + `p/owasp-top-ten`) and re-test. Document which ruleset actually catches the seeded flaw and which doesn't — this comparison is itself a useful finding.

### 4. Software Composition Analysis (SCA) — Trivy

Add a job running Trivy in filesystem mode against `requirements.txt`, gating on HIGH/CRITICAL severity findings. Confirm it detects the CVE(s) in your intentionally outdated dependency, then upgrade to a patched version and confirm the scan goes clean.

### 5. Container Image Scanning — Trivy

Write a `Dockerfile` for the application (minimal base image, e.g. `python:3.10-slim`; non-root user; OS package upgrade at build time). Add a job that builds the image and runs Trivy in image-scan mode against it. Expect to encounter:
- OS-level CVEs in the base image, many of which have no available patch (`ignore-unfixed: true` is the correct way to exclude these from the gate without hiding them from the report)
- CVEs in Python tooling bundled with the base image (`setuptools`, `wheel`, `pip`) that need explicit pinning in `requirements.txt`
- A known, hard limitation: `setuptools` vendors its own internal copies of some libraries in a `_vendor/` folder, which cannot be independently patched via `pip`. When this happens, the correct professional response is **documented risk acceptance** via a `.trivyignore` file — one CVE ID per line, each with a dated justification comment — not chasing an unfixable finding indefinitely.

### 6. Supply Chain Hardening

Pin every third-party GitHub Action used in the workflow to a full 40-character commit SHA (not a mutable version tag like `@v4`), to prevent a compromised or repointed tag from silently injecting malicious code into your pipeline.

### 7. Documentation (README.md)

- **Architecture** — pipeline flow diagram, job dependency table, explanation of fail-fast staging (why secrets scan runs first, why SAST/SCA run in parallel)
- **Findings & Remediation** — one entry per vulnerability, including the CWE/CVE identifier, the tool and rule that caught it, the exact fix applied, and links to the failing and passing CI runs
- **Threat Model** — explicitly state what this pipeline protects against, and equally explicitly state its limitations (no DAST, ruleset coverage is not exhaustive, unfixed CVEs are excluded from the gate but still visible, etc.)
- **Evidence** — a table of red→green CI run pairs for each gate

## Explicitly Out of Scope

- Kubernetes deployment (separate project)
- Authentication/authorization hardening, structured logging, production WSGI server — legitimate hardening ideas, but out of scope unless you deliberately decide to extend the project and document it as a separate phase

## Suggested Order of Work

1. Write the vulnerable app and push it
2. Add secrets scanning, confirm red, fix, confirm green
3. Add SAST, confirm red, fix, confirm green
4. Add SCA, confirm red, fix, confirm green
5. Add Dockerfile + container scanning, work through OS/tooling/vendored-dependency findings iteratively
6. Pin all GitHub Actions to SHAs
7. Write the README with full evidence trail
8. (Polish) Enable branch protection requiring all four checks to pass before merge; add a `.dockerignore`; tag a `v1.0` release
