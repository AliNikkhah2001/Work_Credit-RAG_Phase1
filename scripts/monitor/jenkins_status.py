#!/usr/bin/env python3
"""Probe Jenkins API + local image freshness for the health dashboard.

Healthy means:
  * Jenkins is reachable and authenticated
  * Multibranch job exists / last build not failed red forever
  * Production image aliases exist and are not older than the latest snapshot tag
    by more than ``--stale-hours`` (default 168h = 7d) relative to each other

Also captures forensic artifacts next to ``--out`` under ``jenkins/`` so the next
HealthCheck publish can show *why* a build failed:

  meta/jenkins/consoleText.txt       truncated console log
  meta/jenkins/console_excerpt.txt   docker/npm/Build images / ERROR lines
  meta/jenkins/wfapi.json            pipeline stage dump (when plugin present)
  meta/jenkins/build.json            last build API record
  meta/jenkins/diagnosis.json        heuristic classification of the failure
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROD_ALIASES = [
    "rag-kb:local",
    "rag-orchestrator:local",
    "rag-guardrails:local",
    "rag-webui:dana",
    "rag-tracing:local",
    "dana-jenkins:lts",
]

CONSOLE_MAX_BYTES = 750_000
EXCERPT_MAX_LINES = 400

# Lines worth keeping when operators dig into image / gate failures.
EXCERPT_RE = re.compile(
    r"(?i)("
    r"error|exception|failed|failure|fatal|"
    r"docker(?:\s+compose)?\s+build|building compose|npm\s+(?:ci|run\s+build)|"
    r"rag-webui|no prod controller|DANA_ROLE|CI_MAY_DEPLOY|"
    r"CSRF|crumb|Skipping rag-webui|externally-managed|"
    r"dana/validate|COVERAGE_|structurally-skipped|unexpected-missing|"
    r"Build images|Deploy prod|Stage\s+\(|Finished:\s+\w+"
    r")"
)

SECRET_RE = re.compile(
    r"(?i)(password|passwd|token|secret|api[_-]?key|authorization)\s*[:=]\s*\S+"
)


def jenkins_get(url: str, user: str, password: str, *, raw: bool = False) -> tuple[int, Any]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {token}",
            "Accept": "text/plain, application/json;q=0.9, */*;q=0.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read()
            code = int(resp.status)
            if raw:
                return code, body
            text = body.decode("utf-8", errors="replace")
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "json" in ctype or text.lstrip().startswith(("{", "[")):
                try:
                    return code, json.loads(text) if text else {}
                except json.JSONDecodeError:
                    return code, text
            return code, text
    except urllib.error.HTTPError as e:
        body = e.read()
        if raw:
            return int(e.code), body
        text = body.decode("utf-8", errors="replace")
        try:
            return int(e.code), json.loads(text)
        except Exception:
            return int(e.code), {"error": text[:300]}
    except Exception as e:
        return 0, {"error": f"{type(e).__name__}: {e}"}


def image_info(ref: str) -> dict[str, Any]:
    try:
        r = subprocess.run(
            [
                "docker",
                "image",
                "inspect",
                ref,
                "--format",
                "{{.Id}}|{{.Created}}|{{json .RepoTags}}",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ref": ref, "present": False, "error": str(e)}
    if r.returncode != 0:
        return {"ref": ref, "present": False, "error": (r.stderr or "")[:200]}
    parts = (r.stdout or "").strip().split("|", 2)
    created = parts[1] if len(parts) > 1 else ""
    age_h = None
    try:
        ts = created.replace("Z", "+00:00")
        if "." in ts:
            head, rest = ts.split(".", 1)
            frac = rest.split("+", 1)[0].split("-", 1)[0][:6]
            tz = ""
            if "+" in rest:
                tz = "+" + rest.split("+", 1)[1]
            else:
                for i, ch in enumerate(rest):
                    if ch in "+-":
                        tz = rest[i:]
                        break
            ts = f"{head}.{frac}{tz or '+00:00'}"
        from datetime import datetime

        dt = datetime.fromisoformat(ts)
        age_h = round((time.time() - dt.timestamp()) / 3600.0, 1)
    except Exception:
        age_h = None
    return {
        "ref": ref,
        "present": True,
        "id": (parts[0][:19] if parts else ""),
        "created": created,
        "age_hours": age_h,
        "tags": parts[2] if len(parts) > 2 else "[]",
    }


def snapshot_stamps(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def redact(text: str) -> str:
    return SECRET_RE.sub(r"\1=***", text)


def diagnose_console(console: str, last_result: str | None) -> dict[str, Any]:
    """Heuristic labels so Pages can show more than last_build_FAILURE."""
    labels: list[str] = []
    lower = console.lower()
    if "no prod controller" in lower or "dana_role=stage" in lower:
        labels.append("coverage_gate_stage_controller_on_main")
    if "csrf" in lower or "crumb" in lower:
        labels.append("jenkins_csrf_rejected")
    if "skipping rag-webui" in lower:
        labels.append("webui_image_skipped_no_npm_build")
    if re.search(r"npm (ci|run build).*(error|failed|err!)", console, re.I):
        labels.append("npm_frontend_build_failed")
    if "docker compose build" in lower and (
        "failed after retries" in lower or "exit code" in lower
    ):
        labels.append("docker_compose_build_failed")
    if "externally-managed-environment" in lower:
        labels.append("python_externally_managed_env")
    if "finished: failure" in lower or last_result == "FAILURE":
        labels.append("jenkins_result_failure")
    if not labels and last_result not in (None, "SUCCESS", "UNSTABLE"):
        labels.append("unknown_build_failure_see_console")
    tip = None
    if "coverage_gate_stage_controller_on_main" in labels:
        tip = (
            "Laptop/stage Jenkins ran `main` and correctly refused prod proof. "
            "Image rebuilds for prod require GPU job `dana-rag-prod` on `main` "
            "with `[ci prod]` / `[ci auto]` (or heavy paths). "
            "Do not treat this as a Dockerfile/npm failure."
        )
    elif "webui_image_skipped_no_npm_build" in labels:
        tip = (
            "Agent lacked npm and had no components/webui/build — WebUI image was skipped. "
            "Ensure the GPU agent has npm or a prebuilt webui/build."
        )
    elif "npm_frontend_build_failed" in labels or "docker_compose_build_failed" in labels:
        tip = "Real image build failure — inspect console_excerpt.txt / consoleText.txt."
    return {"labels": labels, "tip": tip}


def build_paths(job: str, branch: str | None, number: int) -> list[str]:
    """Candidate Jenkins URL prefixes for Multibranch vs flat jobs."""
    paths = []
    if branch:
        paths.append(f"job/{job}/job/{branch}/{number}")
    paths.append(f"job/{job}/{number}")
    return paths


def capture_build_forensics(
    *,
    base: str,
    user: str,
    password: str,
    job: str,
    last: dict[str, Any],
    dest: Path,
) -> dict[str, Any]:
    """Fetch console + stage dump for the last build into ``dest``."""
    dest.mkdir(parents=True, exist_ok=True)
    number = last.get("number")
    branch = last.get("branch") or "main"
    if not isinstance(number, int):
        return {"captured": False, "error": "no_build_number"}

    (dest / "build.json").write_text(
        json.dumps(last, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    console = ""
    console_url = None
    for prefix in build_paths(job, str(branch), int(number)):
        url = f"{base}/{prefix}/consoleText"
        code, body = jenkins_get(url, user, password, raw=True)
        if code == 200 and isinstance(body, (bytes, bytearray)) and body:
            console = body.decode("utf-8", errors="replace")
            console_url = url
            break
        # Some controllers need progressiveText
        url2 = f"{base}/{prefix}/logText/progressiveText?start=0"
        code2, body2 = jenkins_get(url2, user, password, raw=True)
        if code2 == 200 and isinstance(body2, (bytes, bytearray)) and body2:
            console = body2.decode("utf-8", errors="replace")
            console_url = url2
            break

    console = redact(console)
    if len(console.encode("utf-8", errors="ignore")) > CONSOLE_MAX_BYTES:
        # Keep the tail — failures usually print at the end.
        encoded = console.encode("utf-8", errors="ignore")
        console = (
            "[truncated head — keeping last "
            f"{CONSOLE_MAX_BYTES} bytes]\n\n"
            + encoded[-CONSOLE_MAX_BYTES:].decode("utf-8", errors="replace")
        )
    (dest / "consoleText.txt").write_text(console or "(empty console)\n", encoding="utf-8")

    excerpt_lines = [ln for ln in console.splitlines() if EXCERPT_RE.search(ln)]
    if len(excerpt_lines) > EXCERPT_MAX_LINES:
        excerpt_lines = excerpt_lines[-EXCERPT_MAX_LINES:]
    (dest / "console_excerpt.txt").write_text(
        ("\n".join(excerpt_lines) + "\n") if excerpt_lines else "(no matching build/error lines)\n",
        encoding="utf-8",
    )

    wfapi: Any = None
    wfapi_url = None
    for prefix in build_paths(job, str(branch), int(number)):
        for suffix in ("wfapi/describe", "pipeline-overview/tree", "api/json?tree=actions[*]"):
            url = f"{base}/{prefix}/{suffix}"
            code, data = jenkins_get(url, user, password)
            if code == 200 and data:
                wfapi = data
                wfapi_url = url
                break
        if wfapi is not None:
            break
    if wfapi is not None:
        (dest / "wfapi.json").write_text(
            json.dumps(wfapi, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    # Stage list (best-effort flatten)
    stages: list[dict[str, Any]] = []
    if isinstance(wfapi, dict):
        for key in ("stages", "nodes", "childNodes"):
            val = wfapi.get(key)
            if isinstance(val, list):
                for node in val:
                    if not isinstance(node, dict):
                        continue
                    stages.append(
                        {
                            "name": node.get("name") or node.get("displayName"),
                            "status": node.get("status") or node.get("result"),
                            "durationMillis": node.get("durationMillis") or node.get("durationInMillis"),
                            "id": node.get("id"),
                        }
                    )
                break
    if stages:
        (dest / "stages.json").write_text(
            json.dumps(stages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    diagnosis = diagnose_console(console, last.get("result") if isinstance(last, dict) else None)
    (dest / "diagnosis.json").write_text(
        json.dumps(diagnosis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    return {
        "captured": bool(console),
        "build_number": number,
        "branch": branch,
        "console_url": console_url,
        "wfapi_url": wfapi_url,
        "console_bytes": len(console.encode("utf-8", errors="ignore")),
        "excerpt_lines": len(excerpt_lines),
        "stages": len(stages),
        "diagnosis": diagnosis,
        "artifacts": [
            "consoleText.txt",
            "console_excerpt.txt",
            "build.json",
            "diagnosis.json",
            *(["wfapi.json"] if wfapi is not None else []),
            *(["stages.json"] if stages else []),
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--url", default=os.environ.get("JENKINS_URL", "http://127.0.0.1:8085"))
    ap.add_argument("--user", default=os.environ.get("JENKINS_USER", "admin"))
    ap.add_argument(
        "--pass-file",
        type=Path,
        default=Path(os.environ.get("JENKINS_PASS_FILE", "/splunk-data/production/.jenkins-admin-pass")),
    )
    ap.add_argument("--job", default="dana-rag-prod")
    ap.add_argument("--stale-hours", type=float, default=168.0)
    ap.add_argument(
        "--snapshots",
        type=Path,
        default=Path("/splunk-data/production/snapshots"),
    )
    ap.add_argument(
        "--capture-console",
        action="store_true",
        default=True,
        help="Always capture console/stage dump for the last completed build (default on).",
    )
    ap.add_argument(
        "--no-capture-console",
        action="store_false",
        dest="capture_console",
    )
    args = ap.parse_args(argv)

    password = ""
    if args.pass_file.is_file():
        password = args.pass_file.read_text(encoding="utf-8", errors="ignore").strip()

    base = args.url.rstrip("/")
    who_code, who = jenkins_get(f"{base}/whoAmI/api/json", args.user, password)
    # Multibranch: prefer .../job/<name>/job/main ; fall back to folder API.
    job_code, job = jenkins_get(
        f"{base}/job/{args.job}/job/main/api/json?tree=name,url,lastBuild[number,result,timestamp,url,duration],lastCompletedBuild[number,result,timestamp,url,duration],lastFailedBuild[number,result,timestamp,url]",
        args.user,
        password,
    )
    branch_hint = "main" if job_code == 200 else None
    if job_code != 200:
        job_code, job = jenkins_get(
            f"{base}/job/{args.job}/api/json?tree=name,url,lastBuild[number,result,timestamp,url,duration],lastCompletedBuild[number,result,timestamp,url,duration],jobs[name,lastBuild[number,result,timestamp,url,duration],lastCompletedBuild[number,result,timestamp,url]]",
            args.user,
            password,
        )

    images = [image_info(ref) for ref in PROD_ALIASES]
    missing = [i["ref"] for i in images if not i.get("present")]
    ages = [i["age_hours"] for i in images if isinstance(i.get("age_hours"), (int, float))]
    max_age = max(ages) if ages else None
    stale = [
        i["ref"]
        for i in images
        if isinstance(i.get("age_hours"), (int, float)) and i["age_hours"] > args.stale_hours
    ]

    last = None
    if isinstance(job, dict):
        last = job.get("lastCompletedBuild") or job.get("lastBuild")
        if isinstance(last, dict) and branch_hint and "branch" not in last:
            last = {**last, "branch": branch_hint}
        if not last and isinstance(job.get("jobs"), list):
            for sub in job["jobs"]:
                lb = None
                if isinstance(sub, dict):
                    lb = sub.get("lastCompletedBuild") or sub.get("lastBuild")
                if isinstance(lb, dict):
                    cand = {**lb, "branch": sub.get("name")}
                    if last is None or (cand.get("timestamp") or 0) > (last.get("timestamp") or 0):
                        last = cand

    last_result = (last or {}).get("result") if isinstance(last, dict) else None
    jenkins_up = who_code == 200 and bool((who or {}).get("authenticated"))
    images_ok = not missing and not stale
    build_ok = last_result in (None, "SUCCESS", "UNSTABLE")  # None = never built yet
    # "Healthy" for ops means Jenkins is up AND production image aliases are
    # present/fresh. A prior failed build is reported but does not fail the
    # image-health gate (operator can still force-heal / snapshot).
    healthy = jenkins_up and images_ok and job_code == 200

    reasons: list[str] = []
    if not jenkins_up:
        reasons.append("jenkins_auth_failed")
    if job_code != 200:
        reasons.append(f"job_http_{job_code}")
    if missing:
        reasons.append("missing_images:" + ",".join(missing))
    if stale:
        reasons.append("stale_images:" + ",".join(stale))
    if last_result not in (None, "SUCCESS", "UNSTABLE"):
        reasons.append(f"last_build_{last_result}")

    forensics: dict[str, Any] | None = None
    if args.capture_console and isinstance(last, dict) and jenkins_up:
        forensics_dir = args.out.parent / "jenkins"
        try:
            forensics = capture_build_forensics(
                base=base,
                user=args.user,
                password=password,
                job=args.job,
                last=last,
                dest=forensics_dir,
            )
            for label in (forensics.get("diagnosis") or {}).get("labels") or []:
                if label not in reasons:
                    reasons.append(label)
        except Exception as e:
            forensics = {"captured": False, "error": f"{type(e).__name__}: {e}"}

    payload = {
        "schema_version": "jenkins-status/v2",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "healthy": healthy,
        "images_ok": images_ok,
        "build_ok": build_ok,
        "status": "HEALTHY" if healthy else "DEGRADED",
        "reasons": reasons,
        "jenkins": {
            "url": base,
            "authenticated": jenkins_up,
            "who": who if isinstance(who, dict) else {"raw": who},
            "job": args.job,
            "job_http": job_code,
            "last_build": last,
        },
        "forensics": forensics,
        "images": images,
        "missing_images": missing,
        "stale_images": stale,
        "max_image_age_hours": max_age,
        "stale_hours_threshold": args.stale_hours,
        "snapshots": snapshot_stamps(args.snapshots),
        "latest_snapshot": (snapshot_stamps(args.snapshots) or [None])[-1],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # host mirror for ops
    try:
        Path("/var/lib/dana-health/jenkins-status.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except OSError:
        pass
    diag = ((forensics or {}).get("diagnosis") or {}).get("labels") or []
    print(
        f"[jenkins] status={payload['status']} healthy={healthy} "
        f"reasons={reasons or ['ok']} forensics={diag or ['none']}"
    )
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
