# ADO-MCP — Azure DevOps Compliance Agent

A read-only chat assistant for inspecting Azure DevOps configuration. The React + TypeScript frontend deploys to GitHub Pages; a Python FastAPI backend runs in Docker on your Mac mini and makes Azure DevOps REST API calls.

## Capabilities

- List projects and repository permissions/groups
- Inspect repositories and repository policies
- List agent pools
- Inspect variable/library groups, including pipeline access and security permissions
- List project environments and inspect pipeline authorization

The first version uses deterministic prompt matching and REST-backed summaries; it does not call an external language model or make configuration changes.

## Run the backend locally

Prerequisites: Docker Desktop and Azure CLI (`brew install azure-cli`). For SSO, sign in on the Mac mini first:

```sh
az login --scope "499b84ac-1321-427f-aa17-267ca6975798/.default"
```

Then start the API from this repository:

```sh
docker compose up --build -d
curl http://localhost:8000/api/health
```

The API binds to `127.0.0.1:8000`. Azure CLI credentials are mounted read-only and copied into the container's temporary cache for SSO. The host credential folder remains read-only. For PAT mode, paste a token into the frontend connection settings; the token is sent only for that request and then cleared. Grant only the Azure DevOps scopes required for the resources you need to inspect (typically project and graph read, code read, and build read).

If Docker cannot read your mounted Azure CLI files, start Compose with your macOS user and group IDs: `LOCAL_UID=$(id -u) LOCAL_GID=$(id -g) docker compose up --build -d`.

After refreshing an expired SSO session with `az login`, run `docker compose restart` so the container copies the updated Azure CLI cache.

To stop the service:

```sh
docker compose down
```

## Run the frontend locally

```sh
cd frontend
npm install
npm run dev
```

Open the local Vite URL, usually `http://localhost:5173`. Connection settings default to the `ab-org` organization; you can change it there. Enter an optional project, choose PAT or CLI SSO, and set the local API URL if it differs from `http://localhost:8000`.

## GitHub Pages

The repository is public so GitHub Pages is available on the free plan. The included Actions workflow builds the `frontend` directory and deploys it whenever changes reach `main`. In **Settings → Pages**, select **GitHub Actions** as the build and deployment source. The site URL for this repository is https://ab-agentic-ai.github.io/azure-ado/.

For a Pages site to reach your Mac mini API, the API must have a network route and the backend CORS allowlist must include that exact Pages origin. By default the API binds to localhost and accepts local Vite origins only. Do not expose port 8000 directly to the public internet. If using your existing Cloudflare setup, route the API through an authenticated Cloudflare Access application and set `CORS_ORIGINS` to the Pages origin. The frontend sends browser credentials so a Cloudflare Access session can authorize the request. Example:

```sh
CORS_ORIGINS=https://your-owner.github.io docker compose up --build -d
```

Keep tunnel credentials and DNS configuration outside this repository.

## Redeploy with a generated Cloudflare URL

The `cloudflared tunnel run --token ...` output belongs to your named `Mac-mini-ssh` tunnel. It reports the tunnel ID and connector status; it does not generate a web URL. Your screenshot currently shows only the private route `192.168.29.149/32`, which GitHub Pages cannot use as an API URL.

To get a URL directly from `cloudflared` output, the script defaults to a **Quick Tunnel**. Quick Tunnels print a temporary `trycloudflare.com` URL, which the script parses, writes to the frontend runtime config, and pushes to `main` to trigger a Pages rebuild. Set your email in `.env` so the generated URL is protected:

```sh
cp .env.example .env
python3 scripts/redeploy.py
```

Quick Tunnel URLs change when the tunnel restarts and are intended for development/testing, not as a stable production endpoint. The script creates a fresh URL each run and updates Pages automatically. Cloudflare documents that Quick Tunnel URLs are temporary and stop working when the process stops: [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

To use your existing named tunnel instead, add a **Public Hostname** route to `Mac-mini-ssh`, set its service to `http://ado-mcp-api:8000`, and set `ADO_API_URL` in `.env` to that hostname. Then save the tunnel token in an ignored local file and run:

```sh
python3 scripts/redeploy.py --mode named --save-token
python3 scripts/redeploy.py --mode named
```

This named-tunnel mode uses the stable URL from the Cloudflare route; it cannot discover that hostname from the run logs. The tunnel token is prompted without echo and stored at `.secrets/cloudflare-tunnel-token`, outside source control. The API URL is public configuration, not a secret. Both modes build/start the API and tunnel containers, wait for the API health check and tunnel connection/URL, update `frontend/public/runtime-config.js`, and push the URL change to `main` when it changes.

## API

- `GET /api/health` — liveness check
- `POST /api/chat` — body: `{ "prompt": "list projects", "organization": "org", "project": null, "auth": { "mode": "pat", "pat": "..." } }`; choose `"mode": "sso"` to use the mounted Azure CLI session.

The backend is read-only. Query responses are bounded to 200 items and avoid returning variable values/secrets.
