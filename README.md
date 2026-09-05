# DevSecOps Security Gate Pipeline
> See [PROJECT_BRIEF.md](./PROJECT_BRIEF.md) for the original goals and what I learned building this.
[![Pipeline Status](https://github.com/AlphaDevelopmental/devsecops-sast-sca-pipeline/actions/workflows/security.yml/badge.svg)](https://github.com/AlphaDevelopmental/devsecops-sast-sca-pipeline/actions)

A CI/CD security gate implementing Shift-Left Security on GitHub Actions. Enforces four automated, blocking security controls — Secrets Detection, Static Application Security Testing (SAST), Software Composition Analysis (SCA), and Container Image Scanning — on every push, with parallel job execution, least-privilege token permissions, and SHA-pinned Actions to mitigate supply-chain risk.

Each control is demonstrated as a functioning gate: a deliberately vulnerable Flask application is scanned, the pipeline fails on real findings (CVE-2023-30861, CWE-89 SQL Injection, exposed credential, container-level CVEs), the code is remediated, and the same pipeline passes clean — with the full run history preserved as evidence.

| | |
|---|---|
| **Target application** | Python 3.10 / Flask |
| **CI/CD** | GitHub Actions |
| **Secrets detection** | Gitleaks |
| **SAST** | Semgrep (`p/security-audit`, `p/owasp-top-ten`) |
| **SCA** | Trivy (filesystem scan, pip) |
| **Container scanning** | Trivy (image scan, `python:3.10-slim`) |
| **Author** | Taiwo Micheal Glass — AlphaDevelopmental Technologies |
| **Links** | [github.com/AlphaDevelopmental](https://github.com/AlphaDevelopmental) · [alphadevelopmental.github.io](https://alphadevelopmental.github.io) |

---

## Architecture

### Design principles

- **Fail-fast staging** — cheapest, most urgent check (secrets) runs first; both downstream jobs depend on it passing before consuming compute.
- **Parallel execution** — SAST and SCA run concurrently once secrets-scan passes, minimizing total pipeline duration.
- **Least privilege** — `permissions: contents: read` at workflow level; no job is granted write access it doesn't need.
- **Supply-chain integrity** — every third-party Action is pinned to a full 40-character commit SHA, not a mutable version tag, preventing silent upstream compromise.
- **Hard gates, not reports** — every scanner runs with a blocking exit code (`--error`, `exit-code: 1`). A finding above threshold fails the build; nothing merges silently.
- **Documented risk acceptance, not silent suppression** — findings with no available fix (e.g. vendored transitive dependencies) are explicitly listed in `.trivyignore` with a dated justification, not quietly ignored.

### Pipeline flow

```
                    ┌───────────────────┐
                    │   git push        │
                    │   (branch: master)│
                    └─────────┬─────────┘
                              │
                              ▼
                ┌─────────────────────────┐
                │  secrets-scan           │
                │  Gitleaks               │
                │  (full git history)     │
                └────────────┬────────────┘
                              │ needs: secrets-scan
                 ┌────────────┴────────────┐
                 ▼                         ▼
      ┌─────────────────────┐   ┌─────────────────────┐
      │  sast-scan          │   │  sca-scan           │
      │  Semgrep             │   │  Trivy (fs, pip)    │
      │  security-audit +    │   │  severity: HIGH,    │
      │  owasp-top-ten       │   │  CRITICAL           │
      └───────────┬─────────┘   └───────────┬─────────┘
                  │                          │
                  └───────────┬──────────────┘
                              ▼
                  ┌───────────────────────┐
                  │  container-scan        │
                  │  docker build           │
                  │  Trivy (image scan)     │
                  │  severity: HIGH,        │
                  │  CRITICAL                │
                  └────────────┬────────────┘
                              ▼
                  ┌───────────────────────┐
                  │  All gates pass?       │
                  ├── NO  ──► Build fails, │
                  │           merge blocked│
                  └── YES ──► Build passes │
                  └───────────────────────┘
```

### Job dependency table

| Job | Depends on | Runs in parallel with | Blocking? |
|---|---|---|---|
| `secrets-scan` | — | — | Yes |
| `sast-scan` | `secrets-scan` | `sca-scan` | Yes |
| `sca-scan` | `secrets-scan` | `sast-scan` | Yes |
| `container-scan` | `secrets-scan`, `sast-scan`, `sca-scan` | — | Yes |

---

## Findings & Remediation

Each control below was verified against a genuine, seeded vulnerability — not a synthetic test. The build failed on first detection and passed only after real code remediation.

### 1. Secrets Detection — Gitleaks

| | |
|---|---|
| **Rule** | `generic-api-key` |
| **Location** | `app.py`, line 5 |
| **Finding** | Hardcoded API token committed to source |
| **Risk** | Credential exposure — anyone with repo read access (or a repo leak) gains a live-looking secret; in a real deployment this could mean account or resource compromise |
| **Remediation** | Externalized via `os.getenv()`; secret now sourced from environment at runtime, never committed |
| **Evidence** | Run #2 (red) → Run #3 (green) |

### 2. SAST — Semgrep

| | |
|---|---|
| **Rules** | `python.django.security.injection.sql.sql-injection-using-db-cursor-execute`, `python.flask.security.injection.tainted-sql-string` |
| **CWE** | CWE-89 — SQL Injection |
| **Location** | `app.py`, line 15 |
| **Finding** | User-controlled `username` parameter concatenated directly into a raw SQL string |
| **Risk** | Unauthenticated SQL injection — an attacker could manipulate the query to read, modify, or exfiltrate arbitrary data from the `users` table |
| **Remediation** | Replaced with a parameterized query (`cursor.execute(query, (username,))`), letting the DB driver treat input strictly as data |
| **Evidence** | Run #7 (red) → Run #8 (green) |

### 3. SCA — Trivy

| | |
|---|---|
| **CVE** | CVE-2023-30861 |
| **Severity** | HIGH |
| **Package** | `flask==1.1.2` |
| **Finding** | Missing `Vary: Cookie` header can cause the permanent session cookie to be cached and served to a different user under certain caching configurations |
| **Risk** | Session disclosure — one user's authenticated session could leak to another |
| **Remediation** | Upgraded to `flask==2.3.2` (patched release) |
| **Evidence** | Run #10 (red) → Run #11 (green) |

### 4. Secrets Externalization Anti-Pattern — Manual Review

| | |
|---|---|
| **Finding** | `DB_PASSWORD` and `API_TOKEN` were "externalized" via `os.getenv("Pr0d_Db_P@ssw0rd_2024_Secure")` — but the literal secret value was used as the **environment variable name**, not a real variable name. The code looked externalized on casual inspection but was functionally broken (the lookup could never succeed) and still exposed the real secret value in source. |
| **Detected by** | Manual code review (not caught by Gitleaks, Semgrep, or Trivy — the value wasn't in a position any of these tools pattern-match against) |
| **Risk** | False sense of security — a superficial glance suggests secrets are externalized when they are not; the plaintext credential remains fully readable in source |
| **Remediation** | Corrected to `os.getenv("DB_PASSWORD")` and `os.getenv("API_TOKEN")` — proper variable names, with real values supplied via a gitignored `.env` locally and CI/production secrets elsewhere |
| **Incident during fix** | The `.env` file containing real values was briefly and accidentally committed alongside this fix. Caught before further exposure; remediated by `git rm --cached .env` and confirming `.gitignore` coverage |
| **Evidence** | Runs #30–#31 (fix applied) → Run #32 (`.env` untracked and leak prevented) |

### 5. Container Image Scanning — Trivy

| | |
|---|---|
| **Target** | Docker image built from `Dockerfile` (`python:3.10-slim` base) |
| **Findings** | OS-level Debian CVEs (mostly unfixed/`fix_deferred`, excluded via `ignore-unfixed`); Python tooling CVEs in `setuptools`, `wheel`, `msgpack`, `urllib3` |
| **Root cause** | Base image OS packages and bundled Python tooling age independently of `requirements.txt`, just like any other dependency |
| **Remediation** | `apt-get upgrade` at build time; explicit pinning of `setuptools`, `wheel`, `msgpack`, `urllib3`, `jaraco.context` in `requirements.txt`; removed unused `ensurepip` bundled wheels; container runs as a non-root user (`appuser`) |
| **Residual risk — documented, not silently ignored** | `setuptools` vendors its own internal copies of `wheel`, `jaraco.context`, and other packages inside `setuptools/_vendor/`. These are not independently upgradable via `pip` — only a new `setuptools` release changes them, and they are never executed directly by the application. Four such CVEs are explicitly accepted via `.trivyignore`, each with a dated justification comment, rather than left as a permanently failing, unactionable gate. |
| **Evidence** | Run #16 (red — Dockerfile added, base image + tooling CVEs) → iterative remediation (runs #17–#27) → Run #28 (green) |

### Ruleset iteration note

The initial Semgrep run used the lightweight `p/ci` ruleset, which did **not** catch the seeded SQL injection — it only flagged unrelated findings (mutable Action tags, Flask host binding). Switching to `p/security-audit` + `p/owasp-top-ten` (225 rules vs. 32) surfaced the actual SQLi. This is documented deliberately: no single ruleset is exhaustive, and ruleset selection is itself a security decision.

### Secrets anti-pattern note

Not every "secrets externalization" fix is a real fix — a scanner-evasion pattern where the secret's literal value is used as the environment variable *name* (`os.getenv("<the actual secret>")`) reads as externalized on casual review but is functionally broken and still leaks the value. No automated tool in this pipeline caught it; it surfaced only through manual review. This is documented because it's a real, easy-to-make mistake, not a hypothetical.

### Vendored-dependency note

Container scanning surfaced a subtler class of finding: CVEs in packages that `setuptools` bundles internally for its own use (`setuptools/_vendor/`), which are structurally impossible to patch via `pip install` or version pinning — only an upstream `setuptools` release changes them. Rather than leave the pipeline permanently red over an unactionable finding, these were reviewed individually, confirmed as dormant/non-executed code paths, and formally accepted via `.trivyignore` with dated justification comments. This mirrors real-world practice: not every finding has a fix, and a mature pipeline distinguishes between "unfixed" and "accepted-and-documented."

---

## Threat Model

### In scope — what this pipeline defends against

| Threat | Control | Stage |
|---|---|---|
| Hardcoded credentials committed to source or history | Gitleaks, full-history scan | `secrets-scan` |
| Insecure code patterns (SQL injection, unsafe host binding) | Semgrep, security-audit + OWASP Top 10 rulesets | `sast-scan` |
| Known-vulnerable third-party dependencies | Trivy, pip manifest scan against NVD-backed DB | `sca-scan` |
| Known-vulnerable OS packages and Python tooling in the deployed container | Trivy, image scan against `python:3.10-slim` build | `container-scan` |
| Containers running as root | Non-root `USER appuser` in `Dockerfile` | Build stage |
| CI/CD supply-chain compromise via mutable Action references | SHA-pinned Actions | All jobs |
| Broad/unnecessary workflow permissions | `permissions: contents: read` | Workflow level |

### Out of scope — explicit limitations

- **No DAST (Dynamic Application Security Testing)** — the application is never run and probed live; only static analysis and dependency scanning are performed. Runtime-only issues (auth bypass under load, business-logic flaws) are not covered.
- **No infrastructure-as-code scanning** — no Terraform/IaC exists in this project yet; tools like `tfsec`/`checkov` would be needed if that's added.
- **Ruleset coverage is not exhaustive** — Semgrep's community rulesets catch common, well-known patterns; a determined attacker using unusual code constructs could evade static pattern matching. SAST is a gate, not a guarantee.
- **Trivy's DB reflects known CVEs at scan time** — a zero-day or freshly disclosed vulnerability in a dependency won't be caught until the DB updates.
- **Unfixed OS-level CVEs are excluded from the gate, not resolved** — `ignore-unfixed: true` prevents the pipeline from blocking forever on Debian packages with no available patch. These findings are still visible in Trivy's output, just non-blocking.
- **Vendored transitive dependencies are a known blind spot for pip-based pinning** — packages like `setuptools` bundle internal copies of other libraries that `pip install` cannot independently upgrade. These are handled via documented risk acceptance (`.trivyignore`), not left unaddressed. Reviewed 2026-08-26.
- **No secrets rotation** — Gitleaks detects committed secrets; it does not rotate or revoke a credential once found. That remains a manual/operational step.
- **Single-branch pipeline** — currently triggers on `master` only; no branch protection rules or required-status-check enforcement configured yet at the repository settings level.

---

## How to Run / Reproduce

### Prerequisites
- Python 3.10+
- Git
- A GitHub account (to fork/push and trigger Actions)

### Local setup

```bash
git clone https://github.com/AlphaDevelopmental/devsecops-sast-sca-pipeline.git
cd devsecops-sast-sca-pipeline
pip install -r requirements.txt
python app.py
```

The app runs on `http://127.0.0.1:5000`. Example endpoint:
```
GET /search?username=admin
```

### Running the security gates locally (before pushing)

```bash
# Secrets scan
gitleaks detect --source . --verbose

# SAST
pip install semgrep
semgrep scan --config p/security-audit --config p/owasp-top-ten --error

# SCA
trivy fs . --severity HIGH,CRITICAL --exit-code 1

# Container image scan
docker build -t devsecops-project1:local .
trivy image devsecops-project1:local --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1
```

### Triggering the CI pipeline

The pipeline runs automatically on every `push` or `pull_request` to `master`. To see it in action:

```bash
git add .
git commit -m "your message"
git push origin master
```

Then check the **Actions** tab of the repository for job-by-job results.

---

## Evidence

Screenshots of each gate's red (failing) → green (passing) transition are stored in `/screenshot`.

| Stage | Red Build | Green Build |
|---|---|---|
| Secrets Detection | Run #2 — `generic-api-key` detected | Run #3 — No leaks detected |
| SAST | Run #7 — 2 blocking SQLi findings | Run #8 — Clean scan |
| SCA | Run #10 — CVE-2023-30861 (HIGH) | Run #11 — Clean scan |
| Container Image Scanning | Run #16 — base image + tooling CVEs | Run #28 — Clean scan (all 4 jobs green) |
| Secrets Externalization Anti-Pattern | Runs #30–#31 — literal secret used as env var name | Run #32 — proper `DB_PASSWORD`/`API_TOKEN` names; `.env` untracked |

Full run history: [Actions tab](https://github.com/AlphaDevelopmental/devsecops-sast-sca-pipeline/actions)

![Red build — SAST catching SQL injection](screenshot/preview.png)
![Green build — after remediation](screenshot/preview%20-after.png)

---

**AlphaDevelopmental Technologies** · Build · Break · Secure
[github.com/AlphaDevelopmental](https://github.com/AlphaDevelopmental) · [alphadevelopmental.github.io](https://alphadevelopmental.github.io)
