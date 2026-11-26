#!/usr/bin/env python3
"""Redeploy the API and a Cloudflare tunnel, then publish its API URL."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
DEFAULT_TOKEN_FILE = ".secrets/cloudflare-tunnel-token"
RUNTIME_CONFIG = ROOT / "frontend/public/runtime-config.js"
PAGE_ORIGIN = "https://ab-agentic-ai.github.io"


def run(args: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, check=True, capture_output=capture)


def read_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    result: dict[str, str] = {}
    for raw in ENV_FILE.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip("\"'")
    return result


def write_env(values: dict[str, str]) -> None:
    current = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    updated: list[str] = []
    written: set[str] = set()
    for line in current:
        key = line.partition("=")[0].strip()
        if key in values:
            updated.append(f"{key}={values[key]}")
            written.add(key)
        else:
            updated.append(line)
    for key, value in values.items():
        if key not in written:
            updated.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(updated).rstrip() + "\n")
    ENV_FILE.chmod(0o600)


def save_token(token_path: Path) -> None:
    token_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    token = getpass.getpass("Paste the Cloudflare tunnel token (input hidden): ").strip()
    if not token:
        raise SystemExit("No token entered.")
    token_path.write_text(token + "\n")
    token_path.chmod(0o600)
    print(f"Saved tunnel token to ignored local file: {token_path.relative_to(ROOT)}")


def validate_api_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise SystemExit("ADO_API_URL must be an HTTPS URL such as https://ado-api.your-domain.com")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise SystemExit("ADO_API_URL must contain only the public hostname, with no path, query, or fragment")
    if parsed.hostname.endswith(".example") or "your-domain" in parsed.hostname:
        raise SystemExit("Replace the example ADO_API_URL with the hostname configured on your Cloudflare tunnel.")
    return f"https://{parsed.hostname}" + (f":{parsed.port}" if parsed.port else "")


def write_runtime_config(api_url: str) -> bool:
    content = "window.ADO_MCP_CONFIG = Object.freeze({ apiBaseUrl: " + json.dumps(api_url) + " });\n"
    previous = RUNTIME_CONFIG.read_text() if RUNTIME_CONFIG.exists() else ""
    if content == previous:
        return False
    RUNTIME_CONFIG.write_text(content)
    return True


def wait_for_api(api_port: int) -> None:
    deadline = time.monotonic() + 60
    health_url = f"http://127.0.0.1:{api_port}/api/health"
    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, OSError):
            time.sleep(2)
    raise SystemExit(f"API did not become healthy at {health_url}")


def wait_for_tunnel() -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        logs = run(["docker", "compose", "logs", "--no-color", "--tail=150", "cloudflared"], capture=True).stdout
        if "Registered tunnel connection" in logs:
            return
        time.sleep(3)
    raise SystemExit("Cloudflare tunnel did not register; inspect `docker compose logs cloudflared`.")


def wait_for_quick_tunnel() -> str:
    deadline = time.monotonic() + 90
    pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.IGNORECASE)
    while time.monotonic() < deadline:
        logs = run(["docker", "compose", "logs", "--no-color", "--tail=100", "cloudflared-quick"], capture=True).stdout
        matches = pattern.findall(logs)
        if matches:
            return matches[-1]
        time.sleep(3)
    raise SystemExit("Cloudflare did not print a Quick Tunnel URL; inspect `docker compose logs cloudflared-quick`.")


def publish_runtime_config() -> None:
    run(["git", "add", "--", str(RUNTIME_CONFIG.relative_to(ROOT))])
    run(["git", "commit", "--only", "-m", "chore: update Cloudflare API URL", "--", str(RUNTIME_CONFIG.relative_to(ROOT))])
    run(["git", "push", "origin", "HEAD:main"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("quick", "named"), default="quick", help="quick generates a temporary URI; named uses the account tunnel and a configured hostname")
    parser.add_argument("--save-token", action="store_true", help="securely prompt for a named-tunnel token and save it locally")
    parser.add_argument("--api-url", help="HTTPS hostname already configured on a named tunnel")
    args = parser.parse_args()

    values = read_env()
    token_file = Path(values.get("CLOUDFLARE_TUNNEL_TOKEN_FILE", DEFAULT_TOKEN_FILE))
    if not token_file.is_absolute():
        token_file = ROOT / token_file

    if args.save_token:
        if args.mode != "named":
            raise SystemExit("--save-token is only for --mode named; Quick Tunnels do not use a token.")
        save_token(token_file)
        return 0

    api_url = None
    if args.mode == "named":
        api_url = args.api_url or values.get("ADO_API_URL") or os.getenv("ADO_API_URL")
        if not api_url:
            raise SystemExit("Set ADO_API_URL in .env or pass --api-url for the named tunnel's Public Hostname.")
        api_url = validate_api_url(api_url)
        if not token_file.is_file() or not token_file.read_text().strip():
            raise SystemExit(f"Tunnel token file is missing or empty: {token_file}. Run `python3 scripts/redeploy.py --mode named --save-token` first.")
        try:
            run(["git", "check-ignore", "-q", str(token_file.relative_to(ROOT))], capture=True)
        except ValueError:
            raise SystemExit("Keep the tunnel token file inside the repository's ignored .secrets directory.")
        except subprocess.CalledProcessError:
            raise SystemExit("Tunnel token file is not git-ignored; refusing to run with a token that could be committed.")
    else:
        allowed_email = values.get("QUICK_TUNNEL_ALLOWED_EMAIL", "")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", allowed_email) or allowed_email.endswith("@example.com"):
            raise SystemExit("Set QUICK_TUNNEL_ALLOWED_EMAIL in .env to protect the generated Quick Tunnel URL.")

    page_origin = values.get("PAGES_ORIGIN", PAGE_ORIGIN)
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+", page_origin):
        raise SystemExit("PAGES_ORIGIN must be an HTTPS origin, with no path.")
    try:
        api_port = int(values.get("API_PORT", "8000"))
        if not 1 <= api_port <= 65535:
            raise ValueError
    except ValueError:
        raise SystemExit("API_PORT must be an integer between 1 and 65535.")
    env_updates = {"CORS_ORIGINS": ",".join([page_origin, "http://localhost:5173", "http://127.0.0.1:5173"])}
    if args.mode == "named":
        env_updates.update({"ADO_API_URL": api_url or "", "CLOUDFLARE_TUNNEL_TOKEN_FILE": str(token_file.relative_to(ROOT))})
    write_env(env_updates)

    env = os.environ.copy()
    env["LOCAL_UID"] = str(os.getuid())
    env["LOCAL_GID"] = str(os.getgid())
    profile = "quick-tunnel" if args.mode == "quick" else "named-tunnel"
    tunnel_service = "cloudflared-quick" if args.mode == "quick" else "cloudflared"
    compose = ["docker", "compose", "--profile", profile]
    subprocess.run([*compose, "pull", tunnel_service], cwd=ROOT, env=env, check=True)
    up_command = [*compose, "up", "--build", "-d"]
    if args.mode == "quick":
        up_command.append("--force-recreate")
    subprocess.run(up_command, cwd=ROOT, env=env, check=True)
    wait_for_api(api_port)
    if args.mode == "quick":
        api_url = wait_for_quick_tunnel()
        write_env({"ADO_API_URL": api_url})
    else:
        wait_for_tunnel()

    api_url = validate_api_url(api_url or "")
    desired_runtime_config = "window.ADO_MCP_CONFIG = Object.freeze({ apiBaseUrl: " + json.dumps(api_url) + " });\n"
    if RUNTIME_CONFIG.exists() and RUNTIME_CONFIG.read_text() != desired_runtime_config:
        dirty = run(["git", "status", "--porcelain", "--", str(RUNTIME_CONFIG.relative_to(ROOT))], capture=True).stdout
        if dirty:
            raise SystemExit("runtime-config.js has local changes; commit or discard them before redeploying.")
    if write_runtime_config(api_url):
        publish_runtime_config()
        print("Updated the frontend runtime URL and pushed the Pages redeployment to main.")
    else:
        print("Frontend runtime URL is already current; no Pages config commit was needed.")
    print(f"Cloudflare API URL: {api_url}")
    print(f"Local API health: http://127.0.0.1:{api_port}/api/health")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Command failed with exit code {exc.returncode}: {exc.cmd[0]}") from None
