#!/usr/bin/env python3
# ============================================================
# OpenAI API Key Test Script (Secure Version)
# ============================================================
# Securely tests API key from environment variables
# Never logs or exposes the actual key
# ============================================================

import sys
import time
from datetime import datetime
from typing import Optional

import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

# Add src to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.core.config import settings
from app.core.secrets import get_openai_api_key, redacted_key, SecretManager

console = Console()

# ─── Configuration ────────────────────────────────────────────
TEST_MODEL = "gpt-4o-mini"


def print_header():
    """Print the test header."""
    header = """
╔══════════════════════════════════════════════════════════════════╗
║                    OpenAI API Connection Test                   ║
║                      (Secure Version)                           ║
╚══════════════════════════════════════════════════════════════════╝
"""
    console.print(Panel(header, style="bold blue", box=box.DOUBLE))


def test_api_key() -> bool:
    """Test if the API key is valid."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Testing API key validity...", total=None)

        try:
            api_key = get_openai_api_key()
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{settings.OPENAI_BASE_URL}/models",
                    headers=headers,
                )

            progress.update(task, completed=True)

            if response.status_code == 200:
                console.print("✅ [green]API key is valid[/green]")
                console.print(f"   🔑 Key: [dim]{redacted_key()}[/dim]")
                data = response.json()
                model_count = len(data.get("data", []))
                console.print(f"   📊 Available models: [bold]{model_count}[/bold]")
                return True
            elif response.status_code == 401:
                console.print("❌ [red]Invalid API key[/red]")
                console.print(f"   Status: {response.status_code}")
                return False
            else:
                console.print(f"⚠️  [yellow]Unexpected response: {response.status_code}[/yellow]")
                return False

        except ValueError as e:
            console.print(f"❌ [red]Configuration error: {str(e)}[/red]")
            return False
        except httpx.TimeoutException:
            console.print("❌ [red]Connection timeout - API endpoint unreachable[/red]")
            return False
        except Exception as e:
            console.print(f"❌ [red]Error: {str(e)}[/red]")
            return False


def test_chat_completion() -> Optional[dict]:
    """Test a simple chat completion."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Testing chat completion...", total=None)

        try:
            api_key = get_openai_api_key()
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": TEST_MODEL,
                "messages": [
                    {"role": "user", "content": "Reply with exactly 'OK' if you can read this."}
                ],
                "max_tokens": 10,
                "temperature": 0,
            }

            start_time = time.time()

            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{settings.OPENAI_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                )

            elapsed = time.time() - start_time
            progress.update(task, completed=True)

            if response.status_code == 200:
                data = response.json()
                console.print("✅ [green]Chat completion successful[/green]")
                console.print(f"   ⏱️  Response time: [bold]{elapsed:.2f}[/bold] seconds")

                choices = data.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content", "")
                    console.print(f"   💬 Response: [italic]\"{content}\"[/italic]")

                usage = data.get("usage", {})
                if usage:
                    console.print(f"   📝 Tokens used: [bold]{usage.get('total_tokens', 0)}[/bold]")

                return data
            else:
                console.print(f"❌ [red]Chat completion failed: {response.status_code}[/red]")
                return None

        except ValueError as e:
            console.print(f"❌ [red]Configuration error: {str(e)}[/red]")
            return None
        except Exception as e:
            console.print(f"❌ [red]Error: {str(e)}[/red]")
            return None


def main():
    """Run all tests."""
    print_header()

    # Show key status (redacted)
    table = Table(title="Configuration Status", box=box.ROUNDED)
    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("API Base URL", settings.OPENAI_BASE_URL)
    table.add_row("Test Model", TEST_MODEL)

    try:
        api_key = get_openai_api_key()
        table.add_row("API Key Status", "[green]✓ Configured[/green]")
        table.add_row("API Key (redacted)", redacted_key())
    except ValueError:
        table.add_row("API Key Status", "[red]✗ Missing or invalid[/red]")

    table.add_row("Timestamp", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
    console.print(table)
    console.print()

    # Test API key
    console.print("[bold]🔑 Testing API Credentials[/bold]")
    console.print("─" * 60)
    is_valid = test_api_key()
    console.print()

    if not is_valid:
        console.print("[red]❌ API key validation failed.[/red]")
        console.print("[yellow]Please check your .env file: OPENAI_API_KEY=your-key-here[/yellow]")
        sys.exit(1)

    # Test chat completion
    console.print("[bold]💬 Testing Chat Completion[/bold]")
    console.print("─" * 60)
    result = test_chat_completion()
    console.print()

    if result:
        console.print("[green]✅ All tests passed![/green]")
        console.print("[dim]Your OpenAI API key is working correctly.[/dim]")
        console.print()
        console.print("[bold]📋 Summary:[/bold]")
        console.print(f"   • API Key: [green]Valid[/green] (redacted: {redacted_key()})")
        console.print(f"   • Connection: [green]Successful[/green]")
        console.print(f"   • Model: [green]{TEST_MODEL}[/green]")
        console.print(f"   • Response: [green]Received[/green]")
        sys.exit(0)
    else:
        console.print("[red]❌ Tests failed. Please check your configuration.[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
