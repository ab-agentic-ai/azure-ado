# ADO-MCP — Azure DevOps Compliance Agent

A read-only chat assistant for inspecting Azure DevOps configuration. The React + TypeScript frontend is published on GitHub Pages; a Python FastAPI backend runs in Docker on your Mac mini and makes Azure DevOps REST API calls.

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

Open the local Vite URL, usually `http://localhost:5173`. In Connection settings, enter the Azure DevOps organization (the part after `dev.azure.com/`), optional project, and choose PAT or CLI SSO. Set the local API URL if it differs from `http://localhost:8000`.

## GitHub Pages

The included Actions workflow builds the `frontend` directory and deploys it to Pages when changes reach `main`. In the GitHub repository, open **Settings → Pages** and select **GitHub Actions** as the build and deployment source. Set the repository variable `ADO_API_BASE_URL` to the HTTPS API origin routed to your Mac mini (for example, your authenticated Cloudflare Access hostname). The generated site is available at `https://<owner>.github.io/azure-ado/`.

For a Pages site to reach your Mac mini API, the API must have a network route and the backend CORS allowlist must include that exact Pages origin. By default the API binds to localhost and accepts local Vite origins only. Do not expose port 8000 directly to the public internet. If using your existing Cloudflare setup, route the API through an authenticated Cloudflare Access application and set `CORS_ORIGINS` to the Pages origin. The frontend sends browser credentials so a Cloudflare Access session can authorize the request. Example:

```sh
CORS_ORIGINS=https://your-owner.github.io docker compose up --build -d
```

Keep tunnel credentials and DNS configuration outside this repository.

## API

- `GET /api/health` — liveness check
- `POST /api/chat` — body: `{ "prompt": "list projects", "organization": "org", "project": null, "auth": { "mode": "pat", "pat": "..." } }`; choose `"mode": "sso"` to use the mounted Azure CLI session.

The backend is read-only. Query responses are bounded to 200 items and avoid returning variable values/secrets.
