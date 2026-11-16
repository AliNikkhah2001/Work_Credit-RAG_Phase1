#!/usr/bin/env python3
"""Capture networking ports, disk, RAM, and NVIDIA GPU details for a health run."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path
from typing import Any


WATCH_PORTS = [
    3000, 3001, 8000, 8001, 8002, 8003, 8010, 8085, 8088,
    8100, 8200, 9000, 13000, 13100, 18000, 18100, 18200, 50000,
]


def run(cmd: list[str], timeout: float = 20.0) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "") + (("\n" + r.stderr) if r.returncode and r.stderr else "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"ERROR: {type(e).__name__}: {e}"


def port_probe(ports: list[int]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in ports:
        t0 = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.5)
        try:
            err = sock.connect_ex(("127.0.0.1", p))
            ms = round((time.perf_counter() - t0) * 1000, 1)
            out.append({"port": p, "open": err == 0, "connect_ms": ms})
        except OSError as e:
            out.append({"port": p, "open": False, "error": str(e)})
        finally:
            sock.close()
    return out


def parse_free(text: str) -> dict[str, Any]:
    #              total        used        free      shared  buff/cache   available
    for line in text.splitlines():
        if line.lower().startswith("mem:"):
            parts = line.split()
            if len(parts) >= 7:
                return {
                    "total_mb": _mib(parts[1]),
                    "used_mb": _mib(parts[2]),
                    "free_mb": _mib(parts[3]),
                    "available_mb": _mib(parts[6]),
                    "raw": line,
                }
    return {"raw": text[:500]}


def _mib(token: str) -> float | None:
    m = re.match(r"([0-9.]+)([KMGT]?i?)", token.replace(",", ""))
    if not m:
        try:
            return round(int(token) / 1024, 1)  # already KiB from `free -k`
        except ValueError:
            return None
    val = float(m.group(1))
    unit = m.group(2).upper()
    mult = {"": 1 / 1024, "K": 1 / 1024, "KI": 1 / 1024, "M": 1, "MI": 1, "G": 1024, "GI": 1024}.get(unit, 1)
    return round(val * mult, 1)


def parse_df(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        rows.append(
            {
                "filesystem": parts[0],
                "size": parts[1],
                "used": parts[2],
                "avail": parts[3],
                "use_pct": parts[4].rstrip("%"),
                "mount": parts[5],
            }
        )
    return rows


def parse_nvidia(text: str) -> list[dict[str, Any]]:
    gpus: list[dict[str, Any]] = []
    if not text or text.startswith("ERROR") or "NVIDIA-SMI has failed" in text:
        return [{"error": text[:300] if text else "nvidia-smi missing"}]
    # CSV query preferred
    for line in text.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 6 and parts[0].isdigit():
            gpus.append(
                {
                    "index": int(parts[0]),
                    "name": parts[1],
                    "mem_total_mb": _num(parts[2]),
                    "mem_used_mb": _num(parts[3]),
                    "util_pct": _num(parts[4]),
                    "temp_c": _num(parts[5]),
                }
            )
    if gpus:
        return gpus
    return [{"raw": text[:1000]}]


def _num(s: str) -> float | None:
    try:
        return float(re.sub(r"[^0-9.]+", "", s) or "nan")
    except ValueError:
        return None


def docker_ps() -> list[dict[str, str]]:
    text = run(["docker", "ps", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"])
    rows = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("ERROR"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            rows.append(
                {
                    "name": parts[0],
                    "image": parts[1],
                    "status": parts[2],
                    "ports": parts[3] if len(parts) > 3 else "",
                }
            )
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True, help="JSON output path")
    args = ap.parse_args(argv)

    free_txt = run(["free", "-h"])
    if "ERROR" in free_txt:
        free_txt = run(["free", "-m"])
    df_txt = run(["df", "-h", "/", "/splunk-data", "/var/lib/docker"])
    nvsmi = run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits",
        ]
    )
    ss = run(["ss", "-lntup"])
    if ss.startswith("ERROR"):
        ss = run(["netstat", "-lntp"])

    payload = {
        "schema_version": "host-inventory/v1",
        "hostname": socket.gethostname(),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ports": port_probe(WATCH_PORTS),
        "memory": parse_free(free_txt),
        "disk": parse_df(df_txt),
        "gpu": parse_nvidia(nvsmi),
        "docker": docker_ps(),
        "listening_raw": ss[:8000],
        "loadavg": os.getloadavg() if hasattr(os, "getloadavg") else None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    open_n = sum(1 for p in payload["ports"] if p.get("open"))
    print(f"[host] ports_open={open_n}/{len(WATCH_PORTS)} gpus={len(payload['gpu'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
