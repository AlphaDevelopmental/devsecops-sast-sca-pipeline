# Project Brief: DevSecOps Security Gate Pipeline (Project 1)

## What I Set Out to Build

A CI/CD pipeline on GitHub Actions that enforces automated, blocking security controls on every push — not reports that get read and ignored, but gates that physically stop insecure code from merging. My goal was to prove each control against a genuine, real vulnerability: seed it, catch it with a scanner, fix it, and re-verify — not stage a synthetic pass/fail.

## What I Built

A small Flask application with a deliberately seeded SQL injection and a hardcoded credential, wired into a pipeline enforcing four gates:

1. **Secrets Detection (Gitleaks)** — scans full git history for hardcoded credentials
2. **SAST (Semgrep)** — static analysis of the application code
3. **SCA (Trivy, filesystem scan)** — dependency CVE detection against `requirements.txt`
4. **Container Image Scanning (Trivy, image scan)** — CVE detection against the actual built Docker image, not just the dependency manifest

## What I Learned Along the Way (Not Just What I Planned)

- **Gitleaks allowlists well-known documentation placeholder secrets** — my first seeded AWS key used AWS's own official example value, which is deliberately excluded by default to avoid false positives. I had to switch to a realistic-but-non-placeholder value to get a genuine detection.
- **My initial Semgrep ruleset (`p/ci`) didn't catch the SQL injection at all** — it only flagged unrelated findings. Switching to `p/security-audit` + `p/owasp-top-ten` (225 rules vs. 32) surfaced it. I documented this deliberately: no ruleset is exhaustive, and the choice of ruleset is itself a security decision.
- **Container scanning surfaced a class of finding I hadn't anticipated**: CVEs in packages (`setuptools`, `wheel`, `msgpack`, `jaraco.context`) vendored *inside* `setuptools`'s own internal `_vendor/` folder. These can't be patched by pinning versions in `requirements.txt` — only an upstream `setuptools` release changes them. I handled this through documented risk acceptance in a `.trivyignore` file, with a dated justification per CVE, rather than leaving the pipeline permanently red over something unfixable.
- **I found a real bug in my own "fixed" code during manual review**: an earlier secrets-externalization attempt used `os.getenv("<the actual secret value>")` — the literal secret as the environment variable *name* instead of a real variable name. It looked externalized on a casual glance but was functionally broken and still leaked the value. No automated tool caught this; only manual review did.

## Hardening Applied

- Every third-party GitHub Action pinned to a full commit SHA, not a mutable version tag, to prevent supply-chain compromise via a repointed tag
- Container runs as a non-root user
- `permissions: contents: read` set at the workflow level (least privilege)
- Branch protection on `master` requiring all four status checks to pass before merge
- `.dockerignore` added to keep repo metadata out of the build context

## Explicit Limitations (Documented, Not Hidden)

- No DAST — the application is never run and probed live
- SAST ruleset coverage is not exhaustive, as demonstrated by the initial missed SQLi
- Unfixed OS-level CVEs are excluded from the blocking gate (`ignore-unfixed: true`) but remain visible in scan output
- No secrets rotation — Gitleaks detects committed secrets, it does not revoke them
- Single-branch pipeline with required status checks, but not required PR review (practiced instead in Project 2)

Full findings, remediation detail, and CI run evidence are in [README.md](./README.md).
