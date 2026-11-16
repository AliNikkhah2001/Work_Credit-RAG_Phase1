#!/usr/bin/env python3
"""Authenticated + delayed screenshots for Jenkins, KB manager, WebUI, manager APIs.

Uses Playwright (preferred). Waits for real UI selectors — never treats a raw
JSON ``/health`` page as a successful UI capture. Default settle: 10 seconds.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# name, url, kind, wait_selector (CSS; empty = body only)
# Prefer Swagger /docs and real frontends over raw JSON /health (those render white).
TARGETS_DEFAULT: list[tuple[str, str, str, str]] = [
    ("jenkins-status", "http://127.0.0.1:8085/login", "login_jenkins", "#j_username, input[name='j_username'], #main-panel, .jenkins-button"),
    ("kb-manager-docs", "http://127.0.0.1:8000/docs", "swagger", ".swagger-ui, .opblock, #swagger-ui"),
    ("kb-manager-redoc", "http://127.0.0.1:8000/redoc", "page", "#redoc, redoc, .api-content, body"),
    ("webui-main", "http://127.0.0.1:13000/", "webui", "body, #app, .app, [class*='chat']"),
    ("webui-alt", "http://127.0.0.1:8088/", "webui", "body, #app, .app"),
    ("webui-stage", "http://127.0.0.1:13100/", "webui", "body, #app, .app"),
    ("manager-ui", "http://127.0.0.1:9000/", "page", "body"),
    ("manager-docs", "http://127.0.0.1:9000/docs", "swagger", ".swagger-ui, .opblock, #swagger-ui"),
    ("orch-docs", "http://127.0.0.1:8100/docs", "swagger", ".swagger-ui, .opblock, #swagger-ui"),
    ("guard-docs", "http://127.0.0.1:8200/docs", "swagger", ".swagger-ui, .opblock, #swagger-ui"),
    ("gemma-docs", "http://127.0.0.1:18000/docs", "swagger", ".swagger-ui, .opblock, body"),
]


def find_chrome() -> str | None:
    for c in (
        "/usr/local/bin/chromium",
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
    ):
        try:
            subprocess.run([c, "--version"], capture_output=True, timeout=5, check=False)
            return c
        except (FileNotFoundError, OSError):
            continue
    return None


def chrome_shot(chrome: str, url: str, out: Path, settle_ms: int) -> bool:
    udir = out.parent / f".chrome-profile-{out.stem}"
    udir.mkdir(parents=True, exist_ok=True)
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        f"--user-data-dir={udir}",
        "--window-size=1400,900",
        f"--virtual-time-budget={max(settle_ms, 8000)}",
        f"--screenshot={out}",
        url,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    return out.is_file() and out.stat().st_size > 5000


def playwright_available() -> str | None:
    for py in ("/opt/dana-playwright/bin/python", sys.executable):
        try:
            r = subprocess.run(
                [py, "-c", "from playwright.sync_api import sync_playwright; print('ok')"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if r.returncode == 0 and "ok" in (r.stdout or ""):
                return py
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def shot_with_playwright(
    py: str,
    url: str,
    out: Path,
    *,
    settle_s: float,
    wait_selector: str,
    jenkins_user: str | None = None,
    jenkins_pass: str | None = None,
    kind: str = "page",
    webui_email: str | None = None,
    webui_password: str | None = None,
) -> bool:
    script = r'''
import sys, time
from playwright.sync_api import sync_playwright
url, out, settle, kind, user, password, wait_sel, wemail, wpass = sys.argv[1:10]
settle = float(settle)
with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox", "--disable-gpu"])
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    # Wait for UI chrome (Swagger / WebUI / Jenkins) — avoid blank SPA shells
    for sel in [s.strip() for s in wait_sel.split(",") if s.strip()]:
        try:
            page.wait_for_selector(sel, timeout=20000, state="visible")
            break
        except Exception:
            continue
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass

    if kind == "login_jenkins" and user and password:
        try:
            if page.locator("#j_username").count():
                page.fill("#j_username", user)
                page.fill("input[name='j_password']", password)
                page.click("button[type=submit], input[type=submit]")
            elif page.locator("input[name='j_username']").count():
                page.fill("input[name='j_username']", user)
                page.fill("input[name='j_password']", password)
                page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle", timeout=30000)
            page.goto(url.split("/login")[0].rstrip("/") + "/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector("#main-panel, .dashboard, a.model-link, .jenkins-button", timeout=20000)
        except Exception as e:
            sys.stderr.write(f"jenkins login warn: {e}\n")

    if kind == "webui" and wemail and wpass:
        # Optional sign-in when landing on auth form
        try:
            if page.locator("input[type='email'], input[name='email']").count():
                page.fill("input[type='email'], input[name='email']", wemail)
                page.fill("input[type='password']", wpass)
                page.click("button[type='submit']")
                page.wait_for_load_state("networkidle", timeout=30000)
        except Exception as e:
            sys.stderr.write(f"webui login warn: {e}\n")

    if kind == "swagger":
        try:
            page.wait_for_selector(".opblock, .swagger-ui .info, .information-container", timeout=25000)
        except Exception:
            pass

    time.sleep(settle)
    # Reject near-empty captures (raw JSON /health is typically tiny + white)
    page.screenshot(path=out, full_page=True)
    browser.close()
'''
    r = subprocess.run(
        [
            py,
            "-c",
            script,
            url,
            str(out),
            str(settle_s),
            kind,
            jenkins_user or "",
            jenkins_pass or "",
            wait_selector or "body",
            webui_email or "",
            webui_password or "",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    log = out.parent / f"{out.stem}.py.log"
    if r.returncode != 0:
        log.write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
        return False
    if not out.is_file() or out.stat().st_size < 8000:
        log.write_text(
            (r.stdout or "") + "\n" + (r.stderr or "") + f"\nTOO_SMALL size={out.stat().st_size if out.is_file() else 0}\n",
            encoding="utf-8",
        )
        return False
    # Soft blank detection via Pillow when available
    try:
        from PIL import Image  # type: ignore

        im = Image.open(out).convert("RGB")
        px = list(im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata())
        n = max(1, len(px))
        white = sum(1 for r0, g0, b0 in px if r0 > 245 and g0 > 245 and b0 > 245)
        if white / n > 0.92 and out.stat().st_size < 40000:
            log.write_text(f"BLANK_WHITE white%={100*white/n:.1f} size={out.stat().st_size}\n", encoding="utf-8")
            return False
    except Exception:
        pass
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True, help="screenshots directory")
    ap.add_argument("--delay", type=float, default=10.0, help="seconds settle after UI ready")
    ap.add_argument("--jenkins-user", default=os.environ.get("JENKINS_USER", "admin"))
    ap.add_argument(
        "--jenkins-pass-file",
        type=Path,
        default=Path(os.environ.get("JENKINS_PASS_FILE", "/splunk-data/production/.jenkins-admin-pass")),
    )
    ap.add_argument("--webui-email", default=os.environ.get("WEBUI_EMAIL", "admin@localhost"))
    ap.add_argument("--webui-password", default=os.environ.get("WEBUI_PASSWORD", "admin"))
    args = ap.parse_args(argv)

    out: Path = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    jpass = ""
    if args.jenkins_pass_file.is_file():
        jpass = args.jenkins_pass_file.read_text(encoding="utf-8", errors="ignore").strip()

    py = playwright_available()
    chrome = find_chrome()
    results: list[dict[str, Any]] = []

    for name, url, kind, wait_sel in TARGETS_DEFAULT:
        dest = out / f"{name}.png"
        ok = False
        method = "none"
        if py:
            ok = shot_with_playwright(
                py,
                url,
                dest,
                settle_s=args.delay,
                wait_selector=wait_sel,
                jenkins_user=args.jenkins_user if kind == "login_jenkins" else None,
                jenkins_pass=jpass if kind == "login_jenkins" else None,
                kind=kind,
                webui_email=args.webui_email if kind == "webui" else None,
                webui_password=args.webui_password if kind == "webui" else None,
            )
            method = "playwright"
        if not ok and chrome and kind != "login_jenkins":
            time.sleep(min(args.delay, 5))
            ok = chrome_shot(chrome, url, dest, int(max(args.delay, 8) * 1000))
            method = "chrome"
        if not ok:
            (out / f"{name}.url.txt").write_text(url + "\n", encoding="utf-8")
            method = "stub"
        results.append({"name": name, "url": url, "ok": ok, "method": method, "kind": kind})
        print(f"[shot] {name}: {'OK' if ok else 'FAIL'} via {method} ({url})")

    (out / "gallery.json").write_text(
        json.dumps({"delay_s": args.delay, "shots": results}, indent=2) + "\n",
        encoding="utf-8",
    )
    ok_n = sum(1 for r in results if r["ok"])
    print(f"[shot] done {ok_n}/{len(results)}")
    return 0 if ok_n >= max(1, len(results) // 2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
