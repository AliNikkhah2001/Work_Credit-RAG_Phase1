#!/usr/bin/env python3
"""Last-known-good (LKG) state helper for the Dana GPU deploy path.

This module is the single writer of ``deploy/gpu/state/last_good.json``. The shell
scripts (deploy.sh / rollback.sh / health.sh / reconcile.sh) stay thin: they collect
nothing by hand and parse nothing by hand. Every structured fact goes through here.

Why Python: the previous rollback path stored only a bare git SHA in
``deploy/compose/.last_good_sha``. A SHA is not enough to restore a running stack
(the images can be rebuilt from a *different* working tree, env file, or compose
layering). We record the resolved compose config hash plus the exact image IDs so a
rollback restores what actually served traffic, not what git says should be there.

Subcommands
-----------
  config       Resolve the compose config and print it as JSON (single source of
               truth for "what would this deploy actually run?").
  check-ports  Assert every expected service publishes the expected host port.
               This is the guard that makes "container healthy, no published port"
               impossible to deploy silently.
  collect      Gather the full deploy fact set (compose hash, ports, image IDs,
               git SHAs, optional health verdicts) into a candidate JSON file.
  record       Atomically promote a candidate to last_good.json, rotating the
               previous good state to last_good.prev.json and appending history.
  get / set    Read or mutate a dotted field (used for the retry cadence).
  validate     Structural validation of a state file.
  show         Human summary.

All subcommands exit non-zero with a message on stderr when something is wrong so
callers can gate on exit status alone.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile

SCHEMA_VERSION = 1

# Services expected on the self-hosted GPU profile, in startup order.
# Format: service:published_host_port:container_port:health_path
# A path of "-" means "TCP reachable only, no HTTP probe".
GPU_SERVICES = (
    "postgres:15432:5432:- "
    "redis:16379:6379:- "
    "kb:8000:8000:/health "
    "guardrails:8200:8200:/health "
    "tracing:13002:3000:/api/public/health "
    "orchestrator:8100:8100:/health "
    "webui:13000:8080:/health"
).split()

# Laptop prod-sim (base + local + prod-sim) publishes the same loopback ports.
PROD_SIM_SERVICES = GPU_SERVICES

REQUIRED_STATE_KEYS = (
    "schema_version",
    "status",
    "promoted_at",
    "runtime",
    "project",
    "compose",
    "git",
    "images",
    "ports",
)


def die(msg: str, code: int = 2) -> None:
    print(f"state.py: {msg}", file=sys.stderr)
    sys.exit(code)


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value: str) -> datetime.datetime:
    return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc
    )


def run(cmd, cwd=None, check=True, stdin_text=None) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, input=stdin_text)
    if check and proc.returncode != 0:
        die(
            "command failed (%s): %s\n%s"
            % (proc.returncode, " ".join(cmd), (proc.stderr or proc.stdout).strip())
        )
    return proc


def compose_cmd(project: str, files, env_file, *args):
    cmd = ["docker", "compose", "-p", project]
    for f in files:
        cmd += ["-f", f]
    if env_file:
        cmd += ["--env-file", env_file]
    cmd += list(args)
    return cmd


def compose_config(project: str, files, env_file) -> dict:
    proc = run(compose_cmd(project, files, env_file, "config", "--format", "json"))
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        die(f"docker compose config is not valid JSON: {exc}")


def config_hash(config: dict) -> str:
    """Stable hash of the resolved config (sorted keys, no container state)."""
    import hashlib

    payload = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def parse_spec(spec: str):
    """Parse ``svc:published:target:path`` tokens into dicts."""
    out = []
    for token in spec.split():
        parts = token.split(":")
        if len(parts) < 3:
            die(f"bad service spec token {token!r} (want svc:published:target[:path])")
        svc, published, target = parts[0], int(parts[1]), int(parts[2])
        path = ":".join(parts[3:]) if len(parts) > 3 else "-"
        out.append(
            {"service": svc, "published": published, "target": target, "path": path or "-"}
        )
    return out


def normalise_ports(service_conf: dict):
    ports = []
    for entry in service_conf.get("ports") or []:
        published = entry.get("published")
        target = entry.get("target")
        try:
            published = int(published) if published not in (None, "") else None
        except (TypeError, ValueError):
            published = None
        try:
            target = int(target) if target not in (None, "") else None
        except (TypeError, ValueError):
            target = None
        ports.append(
            {
                "host_ip": entry.get("host_ip") or "0.0.0.0",
                "published": published,
                "target": target,
                "protocol": entry.get("protocol") or "tcp",
            }
        )
    return ports


def check_ports(config: dict, spec_tokens):
    """Return (rows, ok). Each row is one expected service/port verdict."""
    services = config.get("services") or {}
    expected = parse_spec(" ".join(spec_tokens) if isinstance(spec_tokens, (list, tuple)) else spec_tokens)
    rows = []
    seen_published = {}

    for exp in expected:
        svc = exp["service"]
        row = {
            "service": svc,
            "expected_published": exp["published"],
            "expected_target": exp["target"],
            "path": exp["path"],
            "image": None,
            "ports": [],
            "verdict": "OK",
            "detail": "",
        }
        conf = services.get(svc)
        if conf is None:
            row["verdict"] = "MISSING_SERVICE"
            row["detail"] = "service not defined in resolved compose config"
            rows.append(row)
            continue

        row["image"] = conf.get("image")
        row["ports"] = normalise_ports(conf)

        if not row["ports"]:
            # The exact production outage: base-only compose => zero published ports.
            row["verdict"] = "NO_PUBLISHED_PORT"
            row["detail"] = (
                "resolved config has no ports: mapping for this service "
                "(compose.base.yml alone publishes nothing)"
            )
            rows.append(row)
            continue

        match = [
            p
            for p in row["ports"]
            if p["published"] == exp["published"] and p["target"] == exp["target"]
        ]
        if not match:
            row["verdict"] = "WRONG_PORT"
            row["detail"] = "expected %d->%d, config has %s" % (
                exp["published"],
                exp["target"],
                ",".join(
                    "%s:%s->%s" % (p["host_ip"], p["published"], p["target"])
                    for p in row["ports"]
                )
                or "none",
            )
            rows.append(row)
            continue

        host_ip = match[0]["host_ip"]
        if host_ip not in ("127.0.0.1", "::1"):
            row["verdict"] = "PUBLIC_BIND"
            row["detail"] = "host_ip=%s (must stay loopback)" % host_ip
            rows.append(row)
            continue

        if exp["published"] in seen_published:
            row["verdict"] = "DUPLICATE_PORT"
            row["detail"] = "host port %d already published by %s" % (
                exp["published"],
                seen_published[exp["published"]],
            )
            rows.append(row)
            continue
        seen_published[exp["published"]] = svc
        rows.append(row)

    ok = all(r["verdict"] == "OK" for r in rows)
    return rows, ok


def fmt_port_check(rows) -> str:
    lines = []
    width = max(len(r["service"]) for r in rows) if rows else 8
    for r in rows:
        lines.append(
            "  %-*s %-7s %-10s %s"
            % (
                width,
                r["service"],
                str(r["expected_published"]),
                r["verdict"],
                r["detail"],
            )
        )
    return "\n".join(lines)


def ps_map(project: str, files, env_file):
    """Map service -> container facts. Handles both NDJSON and array output."""
    proc = run(
        compose_cmd(project, files, env_file, "ps", "--format", "json"), check=False
    )
    raw = (proc.stdout or "").strip()
    entries = []
    if raw:
        if raw.lstrip().startswith("["):
            try:
                entries = json.loads(raw)
            except json.JSONDecodeError:
                entries = []
        else:
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    out = {}
    for e in entries:
        svc = e.get("Service")
        if svc:
            out[svc] = {
                "container": e.get("Name"),
                "health": (e.get("Health") or "none") or "none",
                "state": e.get("State") or "unknown",
                "image": e.get("Image"),
                "container_id": e.get("ID"),
            }
    return out


def inspect_container(name: str):
    if not name:
        return {}
    proc = run(
        [
            "docker",
            "inspect",
            "--format",
            "{{json .}}",
            name,
        ],
        check=False,
    )
    if proc.returncode != 0 or not (proc.stdout or "").strip():
        return {}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}


def image_facts(image_ref: str, image_id: str):
    """Return RepoDigests / tags for an image reference or ID."""
    ref = image_id or image_ref
    out = {"image_id": image_id or None, "repo_digest": None}
    if not ref:
        return out
    proc = run(
        ["docker", "image", "inspect", "--format", "{{json .}}", ref], check=False
    )
    if proc.returncode != 0:
        return out
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return out
    out["image_id"] = data.get("Id") or out["image_id"]
    digests = data.get("RepoDigests") or []
    if digests:
        out["repo_digest"] = digests[0]
    return out


def git_facts(root: str):
    facts = {
        "parent_sha": None,
        "parent_branch": None,
        "parent_dirty": None,
        "submodules": [],
        "submodules_dirty": [],
    }
    if not root or not os.path.isdir(os.path.join(root, ".git")):
        return facts

    def g(*args, cwd=root):
        p = run(["git", "-C", cwd] + list(args), check=False)
        return (p.stdout or "").strip() if p.returncode == 0 else None

    facts["parent_sha"] = g("rev-parse", "HEAD")
    facts["parent_branch"] = g("rev-parse", "--abbrev-ref", "HEAD")
    dirty = g("status", "--porcelain")
    facts["parent_dirty"] = bool(dirty)

    # Enumerate submodules from .gitmodules (works even when not initialised).
    gm = os.path.join(root, ".gitmodules")
    paths = []
    if os.path.isfile(gm):
        p = run(
            [
                "git",
                "config",
                "--file",
                gm,
                "--get-regexp",
                r"^submodule\..*\.path$",
            ],
            check=False,
        )
        for line in (p.stdout or "").splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                paths.append(parts[1].strip())
    for path in paths:
        full = os.path.join(root, path)
        sha = g("rev-parse", "HEAD", cwd=full) if os.path.isdir(full) else None
        describe = g("describe", "--tags", "--always", cwd=full) if sha else None
        sub_dirty = g("status", "--porcelain", cwd=full) if sha else None
        facts["submodules"].append(
            {"path": path, "sha": sha, "describe": describe, "dirty": bool(sub_dirty)}
        )
        if sub_dirty:
            facts["submodules_dirty"].append(path)
    return facts


def atomic_write_json(path: str, data: dict) -> None:
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".lkg-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load_json(path: str):
    if not os.path.isfile(path):
        return None
    try:
        with open(path) as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        die(f"{path} is not valid JSON: {exc}")


def dotted_get(data, field: str):
    cur = data
    for part in field.split("."):
        if isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


def dotted_set(data, field: str, value) -> None:
    parts = field.split(".")
    cur = data
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], (dict, list)):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_config(args) -> int:
    config = compose_config(args.project, args.file, args.env_file)
    json.dump(config, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def cmd_check_ports(args) -> int:
    config = compose_config(args.project, args.file, args.env_file)
    rows, ok = check_ports(config, args.spec)
    print("port preflight (resolved compose config):")
    print(fmt_port_check(rows))
    if args.json_out:
        atomic_write_json(
            args.json_out,
            {
                "project": args.project,
                "config_sha256": config_hash(config),
                "ok": ok,
                "rows": rows,
            },
        )
    if not ok:
        print(
            "FAIL: resolved compose config does not publish the required ports. "
            "A deploy from this config would leave containers healthy but unreachable.",
            file=sys.stderr,
        )
        return 1
    print("OK: every expected service publishes its loopback host port")
    return 0


def cmd_collect(args) -> int:
    config = compose_config(args.project, args.file, args.env_file)
    rows, ok = check_ports(config, args.spec)
    services = ps_map(args.project, args.file, args.env_file)

    stamp = args.stamp or datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    git_sha_short = "nogit"
    git_facts_data = git_facts(args.git_root)
    if git_facts_data.get("parent_sha"):
        git_sha_short = git_facts_data["parent_sha"][:7]

    images = []
    ports = {}
    for row in rows:
        svc = row["service"]
        facts = services.get(svc, {})
        container = facts.get("container")
        inspected = inspect_container(container) if container else {}
        image_id = (inspected.get("Image") or "") or None
        image_info = image_facts(row.get("image") or "", image_id)
        image_ref = row.get("image") or ""
        images.append(
            {
                "service": svc,
                "image": image_ref,
                "image_id": image_info.get("image_id"),
                "repo_digest": image_info.get("repo_digest"),
                # Service name is part of the tag: several services can share one
                # image ref (e.g. python:3.11-slim in the sim), and a shared tag
                # would let one service's pin overwrite another's.
                "rollback_tag": "dana-lastgood/%s:%s-%s"
                % (svc, stamp, git_sha_short),
                "container": container,
                "container_health": facts.get("health"),
            }
        )
        ports[svc] = {
            "published": row["expected_published"],
            "target": row["expected_target"],
            "health_path": row["path"],
        }

    health = None
    if args.health_json and os.path.isfile(args.health_json):
        health = load_json(args.health_json)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "healthy" if (ok and health and health.get("all_healthy")) else "unverified",
        "promoted_at": now_utc(),
        "runtime": "compose",
        "project": args.project,
        "profile": args.profile,
        "recorded_by": args.recorded_by,
        "compose": {
            "files": [os.path.abspath(f) for f in args.file],
            "env_file": os.path.abspath(args.env_file) if args.env_file else None,
            "config_sha256": config_hash(config),
            "project_name": args.project,
            "port_check_ok": ok,
        },
        "git": git_facts_data,
        "images": images,
        "ports": ports,
        "health": health
        or {"checked_at": None, "all_healthy": None, "verdicts": {}},
        "schedule": {
            "last_check_at": now_utc(),
            "last_success_at": now_utc() if ok else None,
            "next_retry_at": None,
            "consecutive_failures": 0,
        },
    }
    atomic_write_json(args.out, payload)
    print(f"collected deploy facts -> {args.out}")
    print(f"  project={args.project} profile={args.profile}")
    print(f"  config_sha256={payload['compose']['config_sha256']}")
    print(f"  services={len(images)} port_check_ok={ok}")
    return 0 if ok else 1


def cmd_record(args) -> int:
    candidate = load_json(args.input)
    if candidate is None:
        die(f"candidate file not found: {args.input}")
    missing = [k for k in REQUIRED_STATE_KEYS if k not in candidate]
    if missing:
        die(f"candidate missing keys: {', '.join(missing)}")
    if candidate.get("status") != "healthy":
        die(
            "refusing to promote a non-healthy candidate (status=%r). "
            "Promotion requires every health gate to pass." % candidate.get("status"),
            code=3,
        )

    state = os.path.abspath(args.state)
    os.makedirs(os.path.dirname(state), exist_ok=True)
    prev = os.path.join(os.path.dirname(state), "last_good.prev.json")

    existing = load_json(state)
    if existing is not None:
        if args.rotate:
            atomic_write_json(prev, existing)
            print(f"rotated previous good state -> {prev}")
        if existing.get("compose", {}).get("config_sha256") == candidate.get(
            "compose", {}
        ).get("config_sha256"):
            # Same resolved config: keep the original promotion time and attempt count
            # so repeated idempotent runs do not look like new deploys.
            candidate["promoted_at"] = existing.get("promoted_at") or candidate.get(
                "promoted_at"
            )
            candidate["schedule"] = existing.get("schedule") or candidate.get("schedule")

    atomic_write_json(state, candidate)
    history = os.path.join(os.path.dirname(state), "last_good.history.jsonl")
    try:
        with open(history, "a") as handle:
            handle.write(
                json.dumps(
                    {
                        "at": now_utc(),
                        "config_sha256": candidate["compose"]["config_sha256"],
                        "parent_sha": candidate.get("git", {}).get("parent_sha"),
                        "images": [i.get("image_id") for i in candidate.get("images", [])],
                        "source": args.source,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        with open(history) as handle:
            lines = handle.readlines()
        if len(lines) > 50:
            with open(history, "w") as handle:
                handle.writelines(lines[-50:])
    except OSError as exc:  # history is best-effort, never fatal
        print(f"warning: could not append history: {exc}", file=sys.stderr)

    print(f"promoted last-good state -> {state}")
    print(f"  config_sha256={candidate['compose']['config_sha256']}")
    print(f"  images={len(candidate.get('images', []))}")
    return 0


def cmd_get(args) -> int:
    data = load_json(args.state)
    if data is None:
        if args.default is not None:
            sys.stdout.write(args.default + "\n")
            return 0
        die(f"state file not found: {args.state}", code=3)
    value = dotted_get(data, args.field)
    if value is None:
        if args.default is not None:
            sys.stdout.write(args.default + "\n")
            return 0
        return 1
    if isinstance(value, (dict, list)):
        json.dump(value, sys.stdout, sort_keys=True)
        sys.stdout.write("\n")
    elif isinstance(value, bool):
        sys.stdout.write(("true" if value else "false") + "\n")
    else:
        sys.stdout.write(f"{value}\n")
    return 0


def cmd_set(args) -> int:
    data = load_json(args.state)
    if data is None:
        die(f"state file not found: {args.state}", code=3)
    if args.field.startswith("schedule.") and args.int:
        dotted_set(data, args.field, int(args.value))
    else:
        dotted_set(data, args.field, args.value)
    atomic_write_json(args.state, data)
    return 0


def cmd_validate(args) -> int:
    data = load_json(args.state)
    if data is None:
        print(f"FAIL: no state file at {args.state}", file=sys.stderr)
        return 3
    problems = []
    missing = [k for k in REQUIRED_STATE_KEYS if k not in data]
    if missing:
        problems.append("missing keys: " + ", ".join(missing))
    if data.get("schema_version") != SCHEMA_VERSION:
        problems.append(
            "schema_version=%r (expected %d)" % (data.get("schema_version"), SCHEMA_VERSION)
        )
    sha = (data.get("compose") or {}).get("config_sha256") or ""
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        problems.append("compose.config_sha256 is not a sha256")
    if data.get("runtime") == "compose" and not data.get("images"):
        problems.append("runtime=compose but images[] is empty")
    for img in data.get("images") or []:
        if not img.get("image"):
            problems.append(f"image entry without image ref: {img}")
        if not (img.get("image_id") or img.get("rollback_tag")):
            problems.append(f"image entry without image_id/rollback_tag: {img}")
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 4
    print(
        "OK: state schema v%d valid (project=%s config=%s images=%d)"
        % (
            data["schema_version"],
            data.get("project"),
            sha[:12],
            len(data.get("images") or []),
        )
    )
    return 0


def cmd_show(args) -> int:
    data = load_json(args.state)
    if data is None:
        print(f"no state file at {args.state}")
        return 3
    compose = data.get("compose") or {}
    git = data.get("git") or {}
    print(f"project        : {data.get('project')}")
    print(f"profile        : {data.get('profile')}  runtime={data.get('runtime')}")
    print(f"status         : {data.get('status')}")
    print(f"promoted_at    : {data.get('promoted_at')}")
    print(f"config_sha256  : {compose.get('config_sha256')}")
    print(f"parent_sha     : {git.get('parent_sha')} ({git.get('parent_branch')})")
    print(f"submodules     : {len(git.get('submodules') or [])}")
    print("images:")
    for img in data.get("images") or []:
        print(
            "  %-13s %-28s %s"
            % (
                img.get("service"),
                img.get("image"),
                (img.get("image_id") or "")[:19],
            )
        )
    sched = data.get("schedule") or {}
    print(
        "schedule       : last_check=%s last_success=%s next_retry=%s failures=%s"
        % (
            sched.get("last_check_at"),
            sched.get("last_success_at"),
            sched.get("next_retry_at"),
            sched.get("consecutive_failures"),
        )
    )
    return 0


def cmd_order(args) -> int:
    """Print services in startup order.

    Combines two constraints:
      * depends_on (condition: service_healthy) is a HARD constraint — a service
        never starts before a dependency it declares.
      * The documented production tiers are a PREFERENCE among independent
        services, so the order stays legible and matches ops runbooks:
        datastores -> kb -> guardrails -> tracing -> orchestrator -> webui.
    Implemented as Kahn's algorithm picking the lowest-tier ready node each step.
    """
    config = compose_config(args.project, args.file, args.env_file)
    services = config.get("services") or {}

    tiers = {
        "postgres": 10,
        "redis": 11,
        "litellm": 30,
        "kb": 20,
        "guardrails": 30,
        "tracing": 40,
        "orchestrator": 50,
        "webui": 60,
        "evaluation": 70,
    }

    deps = {}
    for name, conf in services.items():
        raw = conf.get("depends_on") or {}
        names = list(raw.keys()) if isinstance(raw, dict) else list(raw)
        deps[name] = [d for d in names if d in services]

    order = []
    done = set()
    while len(order) < len(services):
        ready = [
            n
            for n in services
            if n not in done and all(d in done for d in deps.get(n, []))
        ]
        if not ready:
            die("dependency cycle detected in compose depends_on graph")
        ready.sort(key=lambda n: (tiers.get(n, 70), list(services).index(n)))
        winner = ready[0]
        done.add(winner)
        order.append(winner)

    for name in order:
        print(name)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dana GPU last-known-good state helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_compose_args(p):
        p.add_argument("--project", required=True, help="compose project name (-p)")
        p.add_argument(
            "-f",
            "--file",
            action="append",
            required=True,
            help="compose file (repeat, in layering order)",
        )
        p.add_argument("--env-file", default=None)
        p.add_argument(
            "--spec",
            action="append",
            default=None,
            help="service spec string (svc:published:target:path ...); repeatable",
        )

    p_config = sub.add_parser("config")
    add_compose_args(p_config)
    p_config.set_defaults(func=cmd_config)

    p_ports = sub.add_parser("check-ports")
    add_compose_args(p_ports)
    p_ports.add_argument("--json-out", default=None)
    p_ports.set_defaults(func=cmd_check_ports)

    p_order = sub.add_parser("order")
    add_compose_args(p_order)
    p_order.set_defaults(func=cmd_order)

    p_collect = sub.add_parser("collect")
    add_compose_args(p_collect)
    p_collect.add_argument("--out", required=True)
    p_collect.add_argument("--git-root", default=None)
    p_collect.add_argument("--health-json", default=None)
    p_collect.add_argument("--profile", default="gpu")
    p_collect.add_argument("--recorded-by", default="deploy/gpu/state.py")
    p_collect.add_argument("--stamp", default=None)
    p_collect.set_defaults(func=cmd_collect)

    p_record = sub.add_parser("record")
    p_record.add_argument("--state", required=True)
    p_record.add_argument("--input", required=True)
    p_record.add_argument("--source", default="deploy")
    p_record.add_argument(
        "--no-rotate", dest="rotate", action="store_false", default=True
    )
    p_record.set_defaults(func=cmd_record)

    p_get = sub.add_parser("get")
    p_get.add_argument("--state", required=True)
    p_get.add_argument("--field", required=True)
    p_get.add_argument("--default", default=None)
    p_get.set_defaults(func=cmd_get)

    p_set = sub.add_parser("set")
    p_set.add_argument("--state", required=True)
    p_set.add_argument("--field", required=True)
    p_set.add_argument("--value", required=True)
    p_set.add_argument("--int", action="store_true")
    p_set.set_defaults(func=cmd_set)

    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--state", required=True)
    p_validate.set_defaults(func=cmd_validate)

    p_show = sub.add_parser("show")
    p_show.add_argument("--state", required=True)
    p_show.set_defaults(func=cmd_show)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if hasattr(args, "spec") and not args.spec:
        args.spec = [GPU_SERVICES]
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
