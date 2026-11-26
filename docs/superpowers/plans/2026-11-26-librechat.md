# LibreChat Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run LibreChat with the read-only Azure DevOps assistant on the Mac mini and replace the GitHub Pages frontend with a tunneled LibreChat URL.

**Architecture:** Add an OpenAI-compatible adapter to FastAPI. Run the official stable LibreChat release, MongoDB persistence, and cloudflared in Docker Compose, with the Cloudflare Quick Tunnel targeting LibreChat only. Disable Pages after the replacement URL has been verified.

**Tech Stack:** FastAPI/Pydantic, LibreChat v0.8.9, Docker Compose, MongoDB 8, Cloudflare Tunnel.

**Spec:** `docs/superpowers/specs/2026-11-26-librechat-design.md`

## Global Constraints

- Preserve the existing read-only Azure DevOps query behavior.
- Do not expose the API or MongoDB ports publicly; only tunnel LibreChat on port 3080.
- Default Azure DevOps organization is `ab-org`.
- LibreChat registration is disabled; the user creates their admin account and password.
- No secrets enter source control.
- Remove Pages only after LibreChat's HTTPS tunnel URL responds.
- No automated tests are added or run; verify with Compose config, service health, and live HTTP responses.

## Review Focus

- Missing or malformed Bearer PAT must fail closed with HTTP 401.
- LibreChat streaming requests must receive valid SSE framing; ordinary requests must receive standard JSON completions.
- Non-text or empty latest-user messages must return an understandable HTTP 400 response.
- User PAT must be used only for the request and never logged or serialized in responses.
- Tunnel restarts may change the public URL; the script must report and save the current URL without pushing it to GitHub.

---

### Task 1: Add the LibreChat API adapter

**Files:**
- Modify: `backend/app/main.py`
- Modify: `README.md` (API section)

**Interfaces:**
- Consumes: existing `ChatRequest`, `AdoClient`, `detect_topic`, `requires_project`.
- Produces: `GET /v1/models` and `POST /v1/chat/completions` for LibreChat. The completion route uses the Bearer value as the PAT and `ADO_ORGANIZATION` as organization.

- [ ] Parse the latest user message and optional configured project.
- [ ] Return standard OpenAI-shaped JSON for non-streaming calls and standards-compliant `data:` SSE chunks for streaming calls.
- [ ] Return HTTP 401 for absent/invalid authorization shape and HTTP 400 for missing usable prompt.
- [ ] Keep tokens out of log and response bodies.
- [ ] Run `python3 -m compileall backend/app` and manually call `/v1/models`, unauthorized completion, and authorized completion with a non-secret test value to check response shape and fail-closed behavior.

### Task 2: Add LibreChat and tunnel services

**Files:**
- Modify: `docker-compose.yml`
- Create: `librechat.yaml`
- Modify: `.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `/v1` adapter from Task 1 and existing `ado-mcp_default` Compose network.
- Produces: LibreChat at `127.0.0.1:3080`, MongoDB named volume, and a `cloudflared-librechat` URL targeting `http://librechat:3080`.

- [ ] Pin the stable LibreChat image to `registry.librechat.ai/librechat-ai/librechat:v0.8.9` and MongoDB to `mongo:8.0.20`.
- [ ] Add LibreChat signing/encryption keys, default organization, and public URL to ignored `.env`; generate required keys locally if missing.
- [ ] Configure a user-provided PAT for the `ADO Read-only` custom endpoint in `librechat.yaml`.
- [ ] Disable email and social registration by default and document CLI admin creation.
- [ ] Keep MongoDB unpublished; bind LibreChat host port to loopback; only cloudflared container reaches LibreChat via internal network.
- [ ] Run `docker compose -f docker-compose.yml -f docker-compose.librechat.yml config --quiet` and `docker compose -f docker-compose.yml -f docker-compose.librechat.yml --profile librechat config --quiet`.

### Task 3: Replace Pages redeployment with LibreChat tunnel startup

**Files:**
- Modify: `scripts/redeploy.py` or replace it with `scripts/start_librechat.py`
- Modify: `.gitignore`
- Modify: `README.md`

**Interfaces:**
- Consumes: Docker Compose LibreChat/tunnel services from Task 2.
- Produces: command that starts LibreChat and Quick Tunnel, saves the current URL in an ignored local file, and prints it. It does not modify frontend runtime config or push commits.

- [ ] Start MongoDB and API, wait for health, start LibreChat, then start Quick Tunnel.
- [ ] Parse the HTTPS Quick Tunnel URL, check it responds, and save it under `.secrets/` with mode `0600`.
- [ ] Update README for local use, CLI account creation, remote URL, PAT setup, restart behavior, and URL rotation.
- [ ] Run the script against the user's Docker Desktop, verify local and tunneled HTTP responses, and do not expose API/Mongo host ports.

### Task 4: Remove GitHub Pages

**Files:**
- Delete: `.github/workflows/pages.yml`
- Modify: `README.md`
- Modify: `frontend/public/runtime-config.js` and `scripts/redeploy.py` only if still referenced after Task 3.

**Interfaces:**
- Consumes: verified LibreChat HTTPS URL from Task 3.
- Produces: repository without Pages deployment workflow and repository Pages configuration disabled.

- [ ] Confirm tunnel URL returns LibreChat login page before altering Pages.
- [ ] Remove the Pages Actions workflow and old Pages redeploy references.
- [ ] Disable GitHub Pages for `ab-agentic-ai/azure-ado` through the repository settings API.
- [ ] Verify Pages reports disabled, and confirm `main` is clean/pushed.

## Execution Notes

- User explicitly requested setup; implement inline in the existing workspace and push to `main` after service verification.
- The initial LibreChat administrator credentials are entered by the user using `docker compose -f docker-compose.yml -f docker-compose.librechat.yml --profile librechat exec librechat npm run create-user`.
- If the tunnel or image fails due external connectivity, leave Pages enabled and report the specific blocker; do not remove the fallback site.
