#!/usr/bin/env python3
"""Start LibreChat with the ADO API and expose it using a Cloudflare Quick Tunnel."""

from __future__ import annotations

import os
import re
import secrets
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
URL_FILE = ROOT / ".secrets" / "librechat-url.txt"
COMPOSE = [
    "docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.librechat.yml",
    "--profile", "librechat",
]
TUNNEL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.IGNORECASE)
LOCAL_MODEL = "qwen3:1.7b"


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text().splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
    return values


def write_env(updates: dict[str, str], remove: set[str] | None = None) -> None:
    remove = remove or set()
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    output: list[str] = []
    written: set[str] = set()
    for line in lines:
        key = line.partition("=")[0].strip()
        if key in remove:
            continue
        if key in updates:
            output.append(f"{key}={updates[key]}")
            written.add(key)
        else:
            output.append(line)
    output.extend(f"{key}={value}" for key, value in updates.items() if key not in written)
    ENV_FILE.write_text("\n".join(output).rstrip() + "\n")
    ENV_FILE.chmod(0o600)


def ensure_configuration() -> dict[str, str]:
    secret_dir = ROOT / ".secrets"
    secret_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    values = read_env()
    defaults = {
        "ADO_ORGANIZATION": "ab-org",
        "ADO_DEFAULT_PROJECT": "",
        "LIBRECHAT_PORT": "3080",
        "LIBRECHAT_DOMAIN_CLIENT": "http://localhost:3080",
        "LIBRECHAT_DOMAIN_SERVER": "http://localhost:3080",
        "LIBRECHAT_SESSION_COOKIE_SECURE": "false",
        "CORS_ORIGINS": "http://localhost:5173,http://127.0.0.1:5173",
        "API_PORT": "8000",
    }
    values["CORS_ORIGINS"] = defaults["CORS_ORIGINS"]
    for key, value in defaults.items():
        if key not in values:
            values[key] = value

    for key, size in (
        ("LIBRECHAT_CREDS_KEY", 32),
        ("LIBRECHAT_CREDS_IV", 16),
        ("LIBRECHAT_JWT_SECRET", 32),
        ("LIBRECHAT_JWT_REFRESH_SECRET", 32),
        ("LIBRECHAT_MEILI_MASTER_KEY", 32),
        ("LIBRECHAT_RAG_DB_PASSWORD", 32),
    ):
        if not values.get(key):
            values[key] = secrets.token_hex(size)

    write_env(values, {"PAGES_ORIGIN", "ADO_API_URL", "QUICK_TUNNEL_ALLOWED_EMAIL", "CLOUDFLARE_TUNNEL_TOKEN_FILE"})
    return values


def command(args: list[str], env: dict[str, str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    process_env = os.environ.copy()
    process_env.update(env)
    return subprocess.run(args, cwd=ROOT, env=process_env, check=True, text=True, capture_output=capture)


def compose(args: list[str], env: dict[str, str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return command([*COMPOSE, *args], env, capture=capture)


def wait_for_http(url: str, description: str, timeout: int = 180) -> None:
    deadline = time.monotonic() + timeout
    last_error = "no response"
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=5) as response:
                if response.status < 500:
                    return
                last_error = f"HTTP {response.status}"
        except (URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(3)
    raise SystemExit(f"{description} did not become ready at {url}: {last_error}")


def wait_for_quick_tunnel(env: dict[str, str]) -> str:
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        logs = compose(["logs", "--no-color", "--tail=200", "cloudflared-librechat"], env, capture=True).stdout
        urls = TUNNEL_PATTERN.findall(logs)
        if urls:
            return urls[-1]
        time.sleep(3)
    raise SystemExit("Cloudflare did not print a Quick Tunnel URL; inspect `docker compose logs cloudflared-librechat`.")


def wait_for_ollama(env: dict[str, str], timeout: int = 90) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            compose(["exec", "-T", "ollama", "ollama", "list"], env, capture=True)
            return
        except subprocess.CalledProcessError:
            time.sleep(3)
    raise SystemExit("The local Ollama service did not become ready; inspect `docker compose logs ollama`.")


def main() -> int:
    values = ensure_configuration()
    try:
        port = int(values["LIBRECHAT_PORT"])
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise SystemExit("LIBRECHAT_PORT must be an integer between 1 and 65535.") from None

    environment = dict(values)
    environment["LOCAL_UID"] = str(os.getuid())
    environment["LOCAL_GID"] = str(os.getgid())

    compose(["pull"], environment)
    compose(["up", "--build", "-d", "--remove-orphans"], environment)
    wait_for_ollama(environment)
    compose(["exec", "-T", "ollama", "ollama", "pull", LOCAL_MODEL], environment)
    compose(["up", "-d", "--force-recreate", "cloudflared-librechat"], environment)
    wait_for_http(f"http://127.0.0.1:{port}/health", "LibreChat", timeout=240)

    public_url = wait_for_quick_tunnel(environment)
    write_env({
        "LIBRECHAT_DOMAIN_CLIENT": public_url,
        "LIBRECHAT_DOMAIN_SERVER": public_url,
        "LIBRECHAT_SESSION_COOKIE_SECURE": "true",
    })
    environment.update(read_env())
    compose(["up", "-d", "--no-deps", "--force-recreate", "librechat"], environment)
    wait_for_http(f"http://127.0.0.1:{port}/health", "LibreChat", timeout=180)
    wait_for_http(public_url, "Cloudflare Quick Tunnel", timeout=90)

    URL_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    URL_FILE.write_text(public_url + "\n")
    URL_FILE.chmod(0o600)
    print(f"LibreChat local URL: http://127.0.0.1:{port}")
    print(f"LibreChat remote URL: {public_url}")
    print("Create your first admin account with:")
    print("docker compose -f docker-compose.yml -f docker-compose.librechat.yml --profile librechat exec librechat npm run create-user")
    print(f"The current tunnel URL is saved in {URL_FILE.relative_to(ROOT)} and will change when the Quick Tunnel restarts.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Command failed with exit code {exc.returncode}: {exc.cmd[0]}") from None
