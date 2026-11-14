# GitHub status reporting & required status checks

How Jenkins proves what a build actually did, and how to turn that proof into
branch-protection gates. Short version: **the GitHub Branch Source plugin
already posts one coarse status; the pipeline now also posts named per-stage
contexts**, so required checks are possible without guessing names.

Parent overview: `README.md` → **CI/CD & Jenkins**. Operator guide:
`deploy/jenkins/README.md`.

---

## 1. What Jenkins reports today (verified)

Two independent channels reach a commit:

| Channel | Context / check name | Produced by | Granularity |
|---|---|---|---|
| Plugin (always on) | `continuous-integration/jenkins/branch` | GitHub Branch Source plugin `GitHubBuildStatusNotification` | Whole run only |
| Pipeline (new, opt-in) | `dana/validate`, `dana/build`, `dana/stage-deploy`, `dana/stage-e2e`, `dana/prod-deploy` | `scripts/ci_github_status.sh` via Jenkinsfile `ghStatus()` | Per stage that genuinely ran |

Evidence for the plugin channel (this is not a webhook — Jenkins **polls**
GitHub hourly, then posts back over the REST API):

```bash
gh api repos/AliNikkhah2001/Work_Credit-RAG_Phase1/hooks          # → [] (no webhooks)
gh api repos/AliNikkhah2001/Work_Credit-RAG_Phase1/commits/<sha>/statuses \
  --jq '.[]|{context,state,description,target_url}'
# context: continuous-integration/jenkins/branch
# target_url: http://127.0.0.1:8085/job/dana-rag/job/main/21/display/redirect
```

The plugin maps results to GitHub states like this (decompiled from the
installed `github-branch-source` plugin, `GitHubNotificationContext`):

| Jenkins result | GitHub state |
|---|---|
| `SUCCESS` | `success` |
| `UNSTABLE` | `failure` |
| `FAILURE` | `error` |
| `ABORTED` / anything else | `error` |
| building | `pending` |

**Consequence:** marking a build `UNSTABLE` is enough to make GitHub stop showing
green. That is why the false-green fix is a Jenkins result change, not only a
new status context.

---

## 2. The false green, and the fix

`dana-rag/main` #20 and #21 finished `SUCCESS` while every build/deploy stage was
dropped by its `when` guard (`CI_MAY_DEPLOY_PROD=0` on the laptop stage
controller). Verified from the build record:

```bash
docker exec dana-jenkins sh -c \
  'cat /var/jenkins_home/jobs/dana-rag/branches/main/builds/21/pipeline-graph-view-tree.v3.json'
# Checkout success | Skip skipped | Lint success | Rollback skipped
# Build images skipped | Deploy stage skipped | E2E stage skipped
# Prod approval skipped | Deploy prod skipped          → result: SUCCESS
```

Compare `develop` #57, where `Build images` / `Deploy stage` / `E2E stage` all
ran — that green was real.

The fix has three parts, all in the parent repo:

1. **Stage evidence** — `scripts/ci_stage_evidence.sh` writes a marker per stage
   that really executed. The `Checkout` stage calls `reset` first, because the
   agent reuses one workspace (`.ci-workspace`) across branches and builds; a
   leftover marker would vouch for a later build that never ran the stage.
2. **Verdict** — `scripts/ci_verify_coverage.py` compares what ran against what
   this branch/trigger owed, and emits `COVERAGE_VERDICT`, `COVERAGE_STATE`,
   `COVERAGE_GUARD`.
3. **Enforcement** — the Jenkinsfile `post { always }` block publishes
   `dana/validate` from the verdict and downgrades the run when proof is missing.

| Situation | Verdict | Jenkins result | `dana/validate` |
|---|---|---|---|
| `main` fully verified by a prod controller | `covered` | `SUCCESS` | `success` |
| `main` on a stage-only controller (the #21 case) | `structurally-skipped` | `UNSTABLE` | `failure` |
| `main` on a controller that *should* own prod but skipped the deploy | `unexpected-missing` | `FAILURE` | `failure` |
| `develop` `[ci stage]` without the stage/E2E stages | `unexpected-missing` | `FAILURE` | `failure` |
| `[ci skip]` / `[skip ci]` | `opted-out` | `SUCCESS` | `success` |

### Knobs

| Env | Default | Meaning |
|---|---|---|
| `CI_MAIN_PROOF_POLICY` | `unstable` | `unstable` → never green; `fail` → hard failure (prod host); `allow` → keep Jenkins `SUCCESS` but `dana/validate` still reports `failure` |
| `CI_REQUIRE_PROD_CONTROLLER` | `0` | `1` on the host that owns prod verification (set in `docker-compose.gpu.yml`) |
| `GITHUB_STATUS_ENABLED` | `1` in compose | `0` disables the named statuses; the plugin's coarse status still posts |

The laptop gets `unstable`, not `fail`: a stage container cannot verify prod by
design, and failing every `main` build on the laptop would train people to
ignore red. `unstable` is still not green, and `dana/validate` says exactly
what was missing.

---

## 3. Credential setup (no secrets in the repo)

The named statuses reuse the credential the Multibranch scan already needs.

1. Jenkins → **Manage Credentials** → global → **Add Credentials**
2. Kind: **Username with password**
3. ID: **`github-pat`** (must match; it is the default)
4. Username: your GitHub account
5. Password: a PAT with **`repo:status`** (classic) — it needs `repo` for a
   private repo. Fine-grained tokens need *Commit statuses: read and write*.

Override the id with `GITHUB_STATUS_CREDENTIALS_ID` if you rename it.

Verify from the container without printing the secret:

```bash
docker exec dana-jenkins sh -c 'grep -o "<id>[^<]*</id>" /var/jenkins_home/credentials.xml'
# expect <id>github-pat</id>
```

The Jenkinsfile wraps every publish in `try/catch` and runs the script with
`|| true`, so a missing/expired credential logs a warning instead of turning a
good build red. Set `--strict` inside `ci_github_status.sh` only if you *want*
status publication to be a gate.

---

## 4. Required status checks — apply only after the first successful post

> **Do not enable these before Jenkins has posted at least once.** A required
> check that never appears leaves a PR permanently "Expected — waiting".

### Recommended: parent repo `main` + `develop`

`PATCH /branches/{branch}/protection` **replaces the whole protection object**, so
every field you want to keep must be in the body. Use `--input` with explicit JSON
rather than `-f` flags: it is reviewable, and it avoids `gh`'s typed-coercion
surprises on empty values (`restrictions` must be `null`, not `""`).

```bash
# --- main: prod-relevant proof -------------------------------------------
cat > /tmp/protect-main.json <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["dana/validate"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON

gh api -X PATCH repos/AliNikkhah2001/Work_Credit-RAG_Phase1/branches/main/protection \
  -H 'Accept: application/vnd.github+json' \
  --input /tmp/protect-main.json

# --- develop: stage-relevant proof only (no prod-deploy) ------------------
cat > /tmp/protect-develop.json <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["dana/validate"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON

gh api -X PATCH repos/AliNikkhah2001/Work_Credit-RAG_Phase1/branches/develop/protection \
  -H 'Accept: application/vnd.github+json' \
  --input /tmp/protect-develop.json
```

### Adding more contexts later (once each has posted at least once)

Widen `required_status_checks.contexts` in the same JSON body. Only add a context
after you have seen it on a real commit — a required context that never appears
blocks the branch forever.

| Branch | Safe to require now | Add after the stage reliably posts |
|---|---|---|
| `main` | `dana/validate` | `dana/prod-deploy` (prod controller only) |
| `develop` | `dana/validate` | `dana/stage-deploy`, `dana/stage-e2e` |

`dana/build` is intentionally **not** in the safe set — see the caveat below.

### Check applicability

| Context | `main` | `develop` | When it posts |
|---|---|---|---|
| `dana/validate` | ✅ require | ✅ require | always (`post { always }`), including skipped builds |
| `dana/build` | after caveat | after caveat | Build stage `post` — **skipped when `CI_SERVICES=none`** |
| `dana/stage-deploy` | — | after 1st post | `develop` only |
| `dana/stage-e2e` | — | after 1st post | `develop` only |
| `dana/prod-deploy` | after 1st post | — | `main`, prod controller only |

**`dana/build` is conditional today.** The Build stage is dropped when
`CI_SERVICES=none` (Jenkinsfile/docs-only changes) and by the `when` guards, so
requiring it would block docs-only PRs forever. Before adding it to
`required_status_checks`, either accept that every PR must touch a build-relevant
path, or make the pipeline always publish `dana/build` (`skipped`) — the latter
is a deliberate follow-up, not part of this change.

**Safe minimum for the first rollout: `dana/validate` only,** plus the review
rule. It is posted on every build, skipped ones included, and it is exactly the
check that encodes "we proved what we claim".

### Verify what is live

```bash
gh api repos/AliNikkhah2001/Work_Credit-RAG_Phase1/branches/main/protection \
  --jq '{checks:.required_status_checks.contexts, strict:.required_status_checks.strict,
         reviews:.required_pull_request_reviews.required_approving_review_count,
         admins:.enforce_admins.enabled}'

# Does a specific commit carry the contexts?
gh api repos/AliNikkhah2001/Work_Credit-RAG_Phase1/commits/<sha>/statuses \
  --jq '[.[]|select(.context|startswith("dana/"))|{context,state}]'
```

Component repos (`Work_RAG-KB`, `Work_RAG-Orchestrator`, `Work_RAG-Guardrails`,
`Work_RAG-Server-Setup`) are **not** covered by this pipeline: no Jenkins job
builds them and they have no `dana/*` contexts. Leave their
`required_status_checks` null until a job exists that reports there.

---

## 5. Prod controller: do not stand it up tonight

`docker-compose.gpu.yml` (`DANA_ROLE=prod`) has never run. Standing it up to
"solve" the false green would swap a visibility bug for a deployment risk:

- The prod path (`Deploy prod` → `ci_deploy_gate.sh` → `ci_record_last_good.sh`)
  has never executed end-to-end on that host. A first-ever unattended run
  against `main` is the worst possible way to discover its failure modes.
- `[ci auto]` / `[ci prod]` deploy **without approval**. An untested controller
  with those keys armed can push an unverified image set to production.
- The GPU host is unreachable tonight, so nothing can be validated either way.
  Writing config that cannot be exercised is unverifiable code, not progress.

**Minimum viable safe step (recommended):**

1. Keep prod deploys manual (`bash deploy/gpu/deploy.sh`) until the prod
   controller has passed a supervised dry run.
2. Make `deploy/gpu/health.sh` the source of truth for prod health — it already
   reports endpoint status per service. Anything claiming "prod is fine" that is
   not backed by that script's output is not evidence.
3. When the host is reachable, bring the controller up in a supervised window
   with `CI_MAIN_PROOF_POLICY=fail`, verify one deliberate no-op `main` build
   reports `dana/prod-deploy`, and only then consider `[ci auto]`.

Until then the laptop's `main` builds report `UNSTABLE` + `dana/validate:
failure`. That is the honest state: *we did not verify prod*.

---

## 6. Self-tests

```bash
python3 scripts/ci_verify_coverage.py --self-test     # decision table
bash scripts/ci_stage_evidence.sh self-test           # evidence + contexts
bash -n scripts/ci_stage_evidence.sh scripts/ci_github_status.sh
shellcheck scripts/ci_stage_evidence.sh scripts/ci_github_status.sh
```

These run inside the `Lint` stage, so a broken gate fails the build instead of
silently allowing a false green.
