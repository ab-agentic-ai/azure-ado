# Azure DevOps Compliance Assistant

A read-only assistant for inspecting Azure DevOps configuration, served through the LibreChat interface. LibreChat, MongoDB, the FastAPI adapter, and Cloudflare Tunnel run in Docker on the Mac mini.

## What it can inspect

DevOps-Agent routes natural-language questions through local Qwen3 to a fixed read-only Azure DevOps catalog. Current coverage includes:

- Organization projects and project metadata
- Project teams and member names
- Repositories, branches/refs, pull requests, and repository policies
- Pipeline project settings (security/general flags, run retention, build retention defaults and limits), definitions, and recent runs
- Work items (type, state, assignee, priority, iteration, area, and timestamps), plus area and iteration paths
- Test plans and test runs
- Artifact feeds and package metadata
- Agent pools
- Environments and pipeline authorization
- Variable group names, descriptions, variable keys, and pipeline authorization (variable values are never returned)
- Project security permissions, with action names and explicit/effective/inherited allow/deny where ADO returns it
- Project-scoped security groups and their member names

Ask for focused lists or reports such as `project overview for Agentic-Ai`, `release readiness in Agentic-Ai`, `delivery flow for Agentic-Ai`, or `access review for Agentic-Ai`. Release readiness surfaces policy configuration counts, recent run outcomes, environment access, work items, and branch inventory. Delivery flow summarizes pipeline runs, work items, pull requests, iterations, and branches. These are evidence summaries, not compliance certifications.

For details, ask `pipeline project settings in Agentic-Ai`, `permission groups in Agentic-Ai`, or `project details for Agentic-Ai`. The pipeline settings report includes the general and retention controls shown under Project Settings → Pipelines → Settings, plus safe pipeline definition metadata. It never returns variable values. Explicit project names in the latest message take precedence over remembered context.

Qwen selects an operation from a fixed allowlist and helps resolve follow-up context. The Python backend validates the selection, makes the REST calls, and renders the returned ADO data; Qwen cannot choose arbitrary URLs, run shell commands, or modify ADO. Explicit resource names and named report requests also have deterministic routing if Qwen is unavailable. The model does not train on conversations. Only a small local project/topic hint is remembered; ADO result sets are not persisted in that memory.

### Automatic recovery and learning

The agent retries transient network errors and ADO throttling/server responses at most twice, honoring a bounded `Retry-After`. Identity responses are normalized whether ADO returns a list or a wrapped object; if identity lookup still fails, permission rows remain available with an unresolved-identity label instead of crashing the whole response. Unexpected parser/API failures are caught and shown as readable errors rather than provider HTTP 500s.

For future diagnosis, the local SQLite memory stores only a hashed user key, operation category, sanitized error category, occurrence count, and timestamp. A successful query clears that operation's stored issue. It never stores prompts, PATs, identities, or ADO results. Qwen model weights are not modified and the agent does not rewrite or execute code; automatic recovery is limited to these predefined safe behaviors.

### Bounds and access behavior

Collection requests are paged and capped at 500 records per operation. Composite reports show a compact sample; ask for a focused resource query to see more detail. Azure DevOps may restrict results based on the PAT scopes, project membership, service configuration, or API version. When a report section is denied or unavailable, it is labeled instead of being presented as an empty result. An empty permissions result only means no non-empty entries were visible in the requested scope; verify in ADO if you expected grants.

The agent is read-only. It does not retrieve variable values, service connection credentials, secret-bearing configuration, or pipeline logs. Work item queries use fixed, bounded read templates. No tool can bypass ADO authorization, service limits, or missing API support.

## Start LibreChat

Prerequisites: Docker Desktop, Python 3, and an internet connection to pull the service images and the Qwen3 model. The local model is about 1.4 GB on disk.

```sh
python3 scripts/start_librechat.py
```

The script generates unique LibreChat secrets in the ignored `.env`, starts the Docker services, opens a Cloudflare Quick Tunnel, and prints the current remote URL. LibreChat is also available locally at `http://127.0.0.1:3080`. The Quick Tunnel URL is saved to `.secrets/librechat-url.txt` with owner-only permissions.

Quick Tunnel URLs are temporary and change when the tunnel restarts. Run the script again to start a new tunnel and get its new URL. For a stable URL, configure a Cloudflare Public Hostname on a domain you own.

Only LibreChat is exposed through Cloudflare. The ADO API and MongoDB ports are not public. Account registration is enabled; new users receive the regular `USER` role.

The LibreChat Admin Panel is available locally on the Mac mini at `http://127.0.0.1:3000`. It is bound to loopback and is not exposed through Cloudflare. Sign in with the existing LibreChat administrator account, then open **Users** to list and count registered users.

## Create your LibreChat account

Create the first administrator account from the Mac mini terminal. The command prompts for your email and password; enter them directly in the terminal:

```sh
docker compose -f docker-compose.yml -f docker-compose.librechat.yml --profile librechat exec librechat npm run create-user
```

## Connect Azure DevOps

1. Open the printed LibreChat URL and sign in with the account you created.
2. Choose **DevOps-Agent** as the endpoint.
3. When LibreChat asks for the endpoint API key, enter your Azure DevOps PAT. The PAT is used as the Bearer credential for the read-only ADO query and is encrypted in LibreChat's MongoDB store.
4. Ask for projects directly, or include a project in the request, such as `list repositories in project My Project`. You may set `ADO_DEFAULT_PROJECT` in `.env` if you usually query one project.

## Local open model

**Qwen3 1.7B** runs in a local Ollama container. It interprets ADO requests and recent conversation context; the adapter executes only whitelisted read-only ADO queries using the PAT supplied to DevOps-Agent and renders the exact returned rows in readable tables. DevOps-Agent also keeps a small local memory of each user's most recently selected project and query type, so follow-ups in a new chat can use that context. It does not train or change model weights, and it does not store ADO result sets in this memory. This memory is stored in the ignored `.secrets/devops-agent-memory.sqlite3` file. No provider account or API key is needed, and ADO data stays on the Mac. In Docker Desktop on macOS, inference is CPU-only and may be slower than a hosted model. Review important permission/security interpretations against the exact table.

Qwen3 is also exposed as a selectable **Qwen3 (Local)** model in LibreChat. Use that model to create a LibreChat Agent and add the built-in **Web Search** tool in the Agent Builder. Web search is configured with LibreChat's keyless public Keenable provider; search terms and public page content are sent to that service when the tool is used. DevOps-Agent remains the ADO-connected endpoint.

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

The API is read-only. Individual collection calls are capped at 500 records; composite reports show a short sample. Variable values, service connection credentials, secret-bearing configuration, and pipeline logs are not returned.
