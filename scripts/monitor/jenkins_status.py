#!/usr/bin/env python3
"""Probe Jenkins API + local image freshness for the health dashboard.

Healthy means:
  * Jenkins is reachable and authenticated
  * Multibranch job exists / last build not failed red forever
  * Production image aliases exist and are not older than the latest snapshot tag
    by more than ``--stale-hours`` (default 168h = 7d) relative to each other
"""

from __future__ import annotations

import argparse
import base64
import json
import os
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


def jenkins_get(url: str, user: str, password: str) -> tuple[int, Any]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return int(resp.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return int(e.code), json.loads(body)
        except Exception:
            return int(e.code), {"error": body[:300]}
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
        # 2026-11-15T12:43:50.123456789Z
        ts = created.replace("Z", "+00:00")
        if "." in ts:
            head, rest = ts.split(".", 1)
            frac = rest.split("+", 1)[0].split("-", 1)[0][:6]
            tz = ""
            if "+" in rest:
                tz = "+" + rest.split("+", 1)[1]
            elif rest.count("-") and not rest.startswith("-"):
                # rare
                tz = ""
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
    args = ap.parse_args(argv)

    password = ""
    if args.pass_file.is_file():
        password = args.pass_file.read_text(encoding="utf-8", errors="ignore").strip()

    base = args.url.rstrip("/")
    who_code, who = jenkins_get(f"{base}/whoAmI/api/json", args.user, password)
    # Multibranch: prefer .../job/<name>/job/main ; fall back to folder API.
    job_code, job = jenkins_get(
        f"{base}/job/{args.job}/job/main/api/json?tree=name,url,lastBuild[number,result,timestamp,url],lastCompletedBuild[number,result,timestamp]",
        args.user,
        password,
    )
    if job_code != 200:
        job_code, job = jenkins_get(
            f"{base}/job/{args.job}/api/json?tree=name,url,lastBuild[number,result,timestamp,url],lastCompletedBuild[number,result,timestamp],jobs[name,lastBuild[number,result,timestamp]]",
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
        # Multibranch: look at jobs[].lastBuild
        if not last and isinstance(job.get("jobs"), list):
            for sub in job["jobs"]:
                lb = sub.get("lastBuild") if isinstance(sub, dict) else None
                if isinstance(lb, dict):
                    if last is None or (lb.get("timestamp") or 0) > (last.get("timestamp") or 0):
                        last = {**lb, "branch": sub.get("name")}

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

    payload = {
        "schema_version": "jenkins-status/v1",
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
    print(f"[jenkins] status={payload['status']} healthy={healthy} reasons={reasons or ['ok']}")
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
