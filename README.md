# Azure DevOps Compliance Assistant

A read-only assistant for inspecting Azure DevOps configuration, served through the LibreChat interface. LibreChat, MongoDB, the FastAPI adapter, and Cloudflare Tunnel run in Docker on the Mac mini.

## What it can inspect

- Azure DevOps projects
- Project and repository permissions
- Repositories and repository policies
- Agent pools
- Variable/library groups, including pipeline access and security permissions
- Project environments and pipeline authorization

The ADO adapter uses deterministic prompt matching and read-only REST calls. It uses the local Qwen3 open model to summarize results, then displays a readable table. If the model is unavailable, it falls back to a readable table without sending ADO data off the Mac. The ADO adapter does not change Azure DevOps configuration.

## Start LibreChat

Prerequisites: Docker Desktop, Python 3, and an internet connection to pull the service images and the Qwen3 model. The local model is about 1.4 GB on disk.

```sh
python3 scripts/start_librechat.py
```

The script generates unique LibreChat secrets in the ignored `.env`, starts the Docker services, opens a Cloudflare Quick Tunnel, and prints the current remote URL. LibreChat is also available locally at `http://127.0.0.1:3080`. The Quick Tunnel URL is saved to `.secrets/librechat-url.txt` with owner-only permissions.

Quick Tunnel URLs are temporary and change when the tunnel restarts. Run the script again to start a new tunnel and get its new URL. For a stable URL, configure a Cloudflare Public Hostname on a domain you own.

Only LibreChat is exposed through Cloudflare. The ADO API and MongoDB ports are not public. LibreChat account registration is disabled.

## Create your LibreChat account

Create the first administrator account from the Mac mini terminal. The command prompts for your email and password; enter them directly in the terminal:

```sh
docker compose -f docker-compose.yml -f docker-compose.librechat.yml --profile librechat exec librechat npm run create-user
```

## Connect Azure DevOps

1. Open the printed LibreChat URL and sign in with the account you created.
2. Choose **Azure DevOps Read-only** as the endpoint.
3. When LibreChat asks for the endpoint API key, enter your Azure DevOps PAT. The PAT is used as the Bearer credential for the read-only ADO query and is encrypted in LibreChat's MongoDB store.
4. Ask for projects directly, or include a project in the request, such as `list repositories in project My Project`. You may set `ADO_DEFAULT_PROJECT` in `.env` if you usually query one project.

## Local open model

The API uses **Qwen3 1.7B** in a local Ollama container to turn Azure DevOps results into a concise explanation plus a readable table. The model stays behind the API and is not shown as a separate LibreChat chat endpoint, so new chats go through Azure DevOps instead of giving generic model answers. No provider account or API key is needed, and ADO results stay on the Mac. Model inference is CPU-only in Docker Desktop on macOS, so answers may take longer than a hosted model. This is a compact model; review important permission/security interpretations against the table.

The Qwen3 1.7B model is about 1.4 GB and licensed under Apache 2.0. See [Ollama's Qwen3 model card](https://ollama.com/library/qwen3:1.7b) and [Ollama's Docker image documentation](https://ollama.com/blog/ollama-is-now-available-as-an-official-docker-image).

Create a PAT with only the Azure DevOps read scopes needed for the resources you inspect. Do not put the PAT in the repository or `.env`.

The default organization is `ab-org`; set `ADO_ORGANIZATION` in `.env` if needed. LibreChat uses this user's PAT. The existing `/api/chat` route still supports PAT or Azure CLI SSO for the legacy local frontend.

## Stop and restart

Stop the stack while keeping its MongoDB and LibreChat data:

```sh
docker compose -f docker-compose.yml -f docker-compose.librechat.yml --profile librechat down
```

Run `python3 scripts/start_librechat.py` to start it again. This starts a fresh Quick Tunnel, so use the newly printed URL.

## GitHub Pages

GitHub Pages is not used for LibreChat. The UI needs the LibreChat server and database, so it is served by the Docker stack instead. The Pages workflow has been removed and the repository Pages site disabled.

## API

- `GET /api/health` — FastAPI liveness
- `POST /api/chat` — legacy JSON chat route (PAT or Azure CLI SSO)
- `GET /v1/models` and `POST /v1/chat/completions` — internal OpenAI-compatible routes used by LibreChat

The API is read-only. Query responses are bounded to 200 items and do not return variable values or secrets.
