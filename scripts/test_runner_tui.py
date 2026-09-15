#!/usr/bin/env python3
"""
Work Credit RAG Phase 1 — Full Project Test Runner (Python TUI)
Runs comprehensive tests with progress bars, stats, and live TUI dashboard
"""

import sys
import subprocess
import time
import shutil
import os
import tempfile
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any

# ─── Colors ────────────────────────────────────────────────────────
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    NC = '\033[0m'

@dataclass
class TestResult:
    name: str
    status: str  # PASS, FAIL, SKIP
    details: str
    duration: float

class TestRunner:
    def __init__(self):
        self.start_time = time.time()
        self.results: List[TestResult] = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.total = 0
        self.term_width = shutil.get_terminal_size().columns

    def draw_box(self, title: str, width: int = 70):
        w = min(width, self.term_width - 2)
        print(f"{Colors.CYAN}┌{'─' * (w-2)}┐{Colors.NC}")
        print(f"{Colors.CYAN}│{Colors.BOLD} {title.ljust(w-4)} {Colors.CYAN}│{Colors.NC}")
        print(f"{Colors.CYAN}└{'─' * (w-2)}┘{Colors.NC}")

    def progress_bar(self, current: int, total: int, label: str, width: int = 40):
        pct = int(current * 100 / total) if total > 0 else 0
        filled = int(pct * width / 100)
        bar = '#' * filled + '-' * (width - filled)
        sys.stdout.write(f"\r{Colors.CYAN}[{Colors.GREEN}{bar}{Colors.CYAN}] {Colors.BOLD}{pct:3d}%{Colors.NC} {label}")
        sys.stdout.flush()

    def run_test(self, name: str, cmd: str, timeout: int = 30) -> TestResult:
        self.progress_bar(1, 1, name)  # Just show the name
        start = time.time()
        try:
            # Write command to a temp file to avoid shell quoting issues
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                f.write('#!/bin/bash\n')
                f.write(cmd + '\n')
                temp_path = f.name
            os.chmod(temp_path, 0o755)
            
            result = subprocess.run(
                ['bash', temp_path], capture_output=True, text=True, timeout=timeout
            )
            os.unlink(temp_path)
            duration = time.time() - start
            if result.returncode == 0:
                status = "PASS"
                self.passed += 1
            else:
                status = "FAIL"
                self.failed += 1
            details = result.stdout.strip() or result.stderr.strip()
        except subprocess.TimeoutExpired:
            duration = timeout
            status = "FAIL"
            self.failed += 1
            details = f"Timeout after {timeout}s"
        except Exception as e:
            duration = time.time() - start
            status = "FAIL"
            self.failed += 1
            details = str(e)

        res = TestResult(name, status, details, duration)
        self.results.append(res)
        self.total += 1

        # Clear progress line
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()
        return res

    def run_cmd(self, cmd: str, timeout: int = 30) -> tuple:
        """Run command and return (success, output, duration)"""
        start = time.time()
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return (result.returncode == 0, result.stdout.strip() or result.stderr.strip(), time.time() - start)
        except subprocess.TimeoutExpired:
            return (False, f"Timeout after {timeout}s", timeout)
        except Exception as e:
            return (False, str(e), time.time() - time.time())

    def log_test(self, name: str, status: str, details: str, duration: float):
        self.results.append(TestResult(name, status, details, duration))
        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failed += 1
        else:
            self.skipped += 1
        self.total += 1

def run_phase1(runner: TestRunner):
    runner.draw_box("PHASE 1: PREREQUISITES & INFRASTRUCTURE")
    tests = [
        ("nvidia-smi", "command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null"),
        ("CUDA Toolkit", "command -v nvcc >/dev/null && nvcc --version 2>/dev/null | grep release"),
        ("cuDNN", "ldconfig -p 2>/dev/null | grep -q libcudnn"),
        ("Python 3.11", "python3.11 --version 2>/dev/null"),
        ("HF Cache /tmp/hf_clean", "[[ -d /tmp/hf_clean ]] && du -sh /tmp/hf_clean 2>/dev/null"),
        ("Gemma GGUF", "[[ -f /tmp/hf_clean/models--unsloth--gemma-4-31B-it-GGUF/snapshots/c1ac76e99d5513b141e8adde7288b85c3f9c32ec/gemma-4-31B-it-UD-Q4_K_XL.gguf ]] && echo OK"),
        ("llama-server binary", "[[ -f /workspace/llama.cpp-src/build-cuda/bin/llama-server ]] && echo OK"),
        ("PostgreSQL", "pg_isready -h 127.0.0.1 -U postgres -d kb_manager 2>/dev/null"),
    ]
    print(f"{Colors.BOLD}Checking infrastructure...{Colors.NC}\n")
    for i, (name, cmd) in enumerate(tests):
        runner.progress_bar(i+1, len(tests), name)
        runner.run_test(name, cmd, 10)
    print(); print()

def run_phase2(runner: TestRunner):
    runner.draw_box("PHASE 2: PYTHON ENVIRONMENTS")
    venvs = {
        "/tmp/orch-venv": "Orchestrator",
        "/tmp/kb-venv": "KB Manager",
        "/tmp/guard-venv": "Guardrails",
        "/tmp/webui-venv": "Open WebUI",
    }
    print(f"{Colors.BOLD}Validating virtual environments...{Colors.NC}\n")
    for i, (venv, name) in enumerate(venvs.items()):
        runner.progress_bar(i+1, len(venvs), name)
        runner.run_test(f"{name} venv", f"[[ -f {venv}/bin/python ]] && {venv}/bin/python -c 'import fastapi, uvicorn; print(\"fastapi {{}}, uvicorn {{}}\".format(fastapi.__version__, uvicorn.__version__))' 2>/dev/null", 10)
    print(); print()

def run_phase3(runner: TestRunner):
    runner.draw_box("PHASE 3: PORT BINDING & PROCESS VERIFICATION")
    ports = {
        18000: "Gemma (llama-server)",
        8000: "KB Manager",
        8200: "Guardrails",
        8100: "Orchestrator",
        13000: "Open WebUI",
        3000: "Tracing Fallback",
        3001: "Langfuse v2",
        2024: "LangGraph Studio",
        5432: "PostgreSQL",
    }
    print(f"{Colors.BOLD}Verifying all service ports...{Colors.NC}\n")
    for i, (port, name) in enumerate(ports.items()):
        runner.progress_bar(i+1, len(ports), f"Port {port} ({name})")
        runner.run_test(f"Port {port}", f"ss -tlnp 2>/dev/null | grep -q ':{port} '", 5)
    print(); print()

def run_phase4(runner: TestRunner):
    runner.draw_box("PHASE 4: HEALTH ENDPOINTS")
    health = {
        "http://127.0.0.1:18000/health": "Gemma",
        "http://127.0.0.1:8000/health": "KB Manager",
        "http://127.0.0.1:8200/health": "Guardrails",
        "http://127.0.0.1:8100/health": "Orchestrator",
        "http://127.0.0.1:13000/health": "Open WebUI",
        "http://127.0.0.1:3000/health": "Tracing Fallback",
        "http://127.0.0.1:3001/api/public/health": "Langfuse v2",
        "http://127.0.0.1:2024/ok": "LangGraph Studio",
    }
    print(f"{Colors.BOLD}Testing all health endpoints...{Colors.NC}\n")
    for i, (url, name) in enumerate(health.items()):
        runner.progress_bar(i+1, len(health), name)
        runner.run_test(f"{name} health", f"curl -sf --max-time 5 '{url}' >/dev/null", 10)
    print(); print()

def run_phase5(runner: TestRunner):
    runner.draw_box("PHASE 5: FUNCTIONAL TESTS (E2E)")
    print(f"{Colors.BOLD}Running functional tests...{Colors.NC}\n")

    tests = [
        ("Gemma clean", 'curl -sf --max-time 30 "http://127.0.0.1:18000/v1/chat/completions" -H "Content-Type: application/json" -d \'{"model":"unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL","messages":[{"role":"user","content":"سلام"}],"temperature":0,"max_tokens":20,"chat_template_kwargs":{"enable_thinking":false}}\' | python3 -c "import sys,json; j=json.load(sys.stdin); c=j[\\"choices\\"][0][\\"message\\"][\\"content\\"]; assert \\"<unused\\" not in c; print(\\"OK: {}\\".format(c[:40]))" 2>/dev/null', 30),
        ("KB search", 'curl -sf --max-time 15 "http://127.0.0.1:8000/search/api" -H "Content-Type: application/json" -d \'{"query":"اعتبارسنجی چیست","top_k":3}\' | python3 -c "import sys,json; j=json.load(sys.stdin); assert len(j.get(\\"final_results\\",[]))>0; print(\\"OK: {}\\".format(len(j[\\"final_results\\"])))" 2>/dev/null', 15),
        ("Guardrails allowlist", 'curl -sf --max-time 5 "http://127.0.0.1:8200/v1/rails/check" -H "Content-Type: application/json" -d \'{"stage":"input","text":"درخواست حذف سابقه منفی قدیمی","request_id":"t"}\' | python3 -c "import sys,json; assert json.load(sys.stdin)[\\"allowed\\"]==True; print(\\"OK: allowed\\")" 2>/dev/null', 5),
        ("Guardrails block", 'curl -sf --max-time 5 "http://127.0.0.1:8200/v1/rails/check" -H "Content-Type: application/json" -d \'{"stage":"output","text":"این فرد حرامزاده است","request_id":"t"}\' | python3 -c "import sys,json; assert json.load(sys.stdin)[\\"allowed\\"]==False; print(\\"OK: blocked\\")" 2>/dev/null', 5),
        ("E2E RAG", None, 60),  # Special handling
        ("Langfuse traces", 'curl -sf --max-time 5 -u "pk-lf-seeded-public-001:sk-lf-seeded-secret-001" "http://127.0.0.1:3001/api/public/traces?limit=1" | python3 -c "import sys,json; d=json.load(sys.stdin); total=d.get(\\"meta\\",{}).get(\\"totalItems\\",0); assert total>0; print(\\"OK: {}\\".format(total))" 2>/dev/null', 10),
        ("Observe UI", 'curl -sf --max-time 5 "http://127.0.0.1:3000/api/observe/requests?limit=1" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d.get(\\"data\\"),list); print(\\"OK: {}\\".format(len(d[\\"data\\"])))" 2>/dev/null', 5),
    ]

    print(f"{Colors.BOLD}Running functional tests...{Colors.NC}\n")
    for i, (name, cmd, timeout) in enumerate(tests):
        runner.progress_bar(i+1, len(tests), name)
        if name == "E2E RAG":
            cmd = (
                "curl -sf --max-time 60 'http://127.0.0.1:8100/v1/chat/completions' "
                "-H 'Content-Type: application/json' "
                f"-H 'X-Request-ID: tui-test-{int(time.time())}' "
                "-d '{\"model\":\"gemma-4-31b\",\"messages\":[{\"role\":\"user\",\"content\":\"اعتبارسنجی چیست؟\"}],\"temperature\":0,\"max_tokens\":200}' "
                "| python3 -c \"import sys,json; j=json.load(sys.stdin); assert j['choices'][0]['finish_reason']=='stop'; c=len(j.get('rag',{}).get('citations',[])); assert c>0; print('OK: finish=stop, citations={}'.format(c))\" 2>/dev/null"
            )
        runner.run_test(name, cmd, timeout)
    print(); print()

def run_phase6(runner: TestRunner):
    runner.draw_box("PHASE 6: OBSERVABILITY & TRACING")
    print(f"{Colors.BOLD}Checking tracing stack...{Colors.NC}\n")
    tests = [
        ("Fallback JSONL", "[[ -f /tmp/langfuse_traces.jsonl ]] && wc -l /tmp/langfuse_traces.jsonl 2>/dev/null", 5),
        ("Observe /observe", 'curl -sf --max-time 5 "http://127.0.0.1:3000/observe" | grep -q "RAG Observer" 2>/dev/null', 5),
        ("Studio UI", 'curl -sf --max-time 5 "http://127.0.0.1:3000/studio" | grep -q "Local Studio" 2>/dev/null', 5),
        ("Studio API", 'curl -sf --max-time 5 "http://127.0.0.1:2024/ok" | grep -q "ok" 2>/dev/null', 5),
    ]
    print(f"{Colors.BOLD}Checking tracing stack...{Colors.NC}\n")
    for name, cmd, timeout in tests:
        runner.run_test(name, cmd, timeout)
    print(); print()

def print_summary(runner: TestRunner):
    total_dur = time.time() - runner.start_time
    runner.draw_box("TEST SUMMARY DASHBOARD", 80)
    print(f"{Colors.BOLD}{'='*78}{Colors.NC}")
    print(f"{Colors.BOLD}{'Results:':<30} {Colors.GREEN}{runner.passed:4d}{Colors.NC}  {Colors.RED}{runner.failed:4d}{Colors.NC}  {Colors.YELLOW}{runner.skipped:4d}{Colors.NC}  {Colors.CYAN}{runner.total:4d}{Colors.NC}")
    print(f"{Colors.BOLD}{'Total Duration:':<30} {int(time.time() - runner.start_time)}s{Colors.NC}")
    print(f"{Colors.BOLD}{'Timestamp:':<30} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.NC}")
    print(f"{Colors.BOLD}{'='*78}{Colors.NC}\n")

    print(f"{Colors.BOLD}{'#':>3} │ {'TEST NAME':<28} │ {'STATUS':<6} │ {'DURATION':>8} │ {'DETAILS'}{Colors.NC}")
    print(f"{Colors.DIM}{'─'*78}{Colors.NC}")

    for idx, res in enumerate(runner.results, 1):
        details = res.details[:50] + ("…" if len(res.details) > 50 else "")
        if res.status == "PASS":
            status_col = f"{Colors.GREEN}PASS{Colors.NC}"
        elif res.status == "FAIL":
            status_col = f"{Colors.RED}FAIL{Colors.NC}"
        else:
            status_col = f"{Colors.YELLOW}SKIP{Colors.NC}"
        print(f"{idx:3d} │ {res.name:<28.28s} │ {status_col:6} │ {res.duration:>7.1f}s │ {details}")

    print()
    if runner.failed > 0:
        print(f"{Colors.RED}{Colors.BOLD}FAILED TESTS DETAIL:{Colors.NC}")
        for res in runner.results:
            if res.status == "FAIL":
                print(f"  {Colors.RED}▸ {res.name}{Colors.NC}: {res.details}")
        print()

    runner.draw_box("ACCESS URLS (via SSH tunnel)", 70)
    print("Run locally:")
    print("  ssh -p <ssh_port> root@<ssh_host> \\")
    print("    -L 13000:localhost:13000 -L 8100:localhost:8100 \\")
    print("    -L 3000:localhost:3000 -L 3001:localhost:3001 -L 2024:localhost:2024")
    print()
    print("Then open:")
    print("  🌐 WebUI:        http://localhost:13000")
    print("  🔧 Orchestrator: http://localhost:8100")
    print("  📊 Observe:      http://localhost:3000/observe")
    print("  🔍 Studio:       http://localhost:3000/studio")
    print("  📈 Langfuse:     http://localhost:3001 (admin@local.test / Langfuse-Admin-139b81ba)")
    print("  🎯 Smith Studio: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024")
    print()

    if runner.failed == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ ALL TESTS PASSED — SYSTEM READY{Colors.NC}")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ {runner.failed} TEST(S) FAILED — REVIEW ABOVE{Colors.NC}")
        return 1

def main():
    # Disable output buffering
    sys.stdout = open(sys.stdout.fileno(), mode='w', buffering=1)
    
    runner = TestRunner()
    
    # Header
    print(f"{Colors.BOLD}{Colors.MAGENTA}")
    print("╔═══════════════════════════════════════════════════════════════════════════════╗")
    print("║        ██████╗ ███████╗███████╗███╗   ██╗    ██████╗ ███████╗██████╗       ║")
    print("║        ██╔══██╗██╔════╝██╔════╝████╗  ██║    ██╔══██╗██╔════╝██╔══██╗      ║")
    print("║        ██████╔╝█████╗  █████╗  ██╔██╗ ██║    ██████╔╝█████╗  ██████╔╝      ║")
    print("║        ██╔══██╗██╔═══╝ ██╔══╝  ██║╚██╗██║    ██╔══██╗██╔════╝██╔══██╗      ║")
    print("║        ██║  ██║███████╗███████╗██║ ╚████║    ██║  ██║███████╗██║  ██║      ║")
    print("║        ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═══╝    ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝      ║")
    print("║                                                                              ║")
    print("║           R A G   P H A S E  1  —  F U L L  S Y S T E M  T E S T           ║")
    print("╚══════════════════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.NC}")
    print(f"{Colors.DIM}Instance: Vast.ai 50713720 | GPU: RTX 3090 24GB | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.NC}")
    print()

    run_phase1(runner)
    run_phase2(runner)
    run_phase3(runner)
    run_phase4(runner)
    run_phase5(runner)
    run_phase6(runner)

    return print_summary(runner)

if __name__ == "__main__":
    sys.exit(main())