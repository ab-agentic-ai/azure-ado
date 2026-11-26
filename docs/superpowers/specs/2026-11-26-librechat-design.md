# LibreChat Integration Design

## Intent

Replace the custom GitHub Pages frontend with the LibreChat interface so the user can access the read-only Azure DevOps assistant remotely from a browser.

## Current State

- `backend/app/main.py` exposes a JSON `POST /api/chat` endpoint, with PAT or local Azure CLI SSO.
- `docker-compose.yml` runs that API and currently has tunnel profiles aimed at the API or a Pages frontend.
- The repository's Pages workflow publishes a static frontend, which cannot host LibreChat's server or database.
- The user has no custom hostname. Use a Cloudflare Quick Tunnel and document that its URL changes on tunnel restarts.

## Goals

- Run LibreChat and its MongoDB data store through Docker Compose beside the existing API.
- Expose LibreChat on port 3080 locally and through a Quick Tunnel; do not publish the API or MongoDB to the public network.
- Bridge LibreChat's OpenAI-compatible custom endpoint format to the existing read-only Azure DevOps query behavior.
- Use LibreChat local accounts with registration disabled by default. Provide the official CLI command for the user to create the first admin account.
- Remove GitHub Pages publishing configuration after the new app is reachable.
- Keep tokens and generated LibreChat signing/encryption secrets out of version control.

## Non-Goals

- Hosting LibreChat on GitHub Pages.
- Running an AI model or changing Azure DevOps resources.
- Providing a stable hostname without a configured Cloudflare Public Hostname/domain.
- Removing the existing public Pages URL before the Docker app has been verified.

## Approaches Considered

1. **LibreChat in local Docker with a Quick Tunnel (selected).** Uses the existing Mac mini, preserves the local Azure DevOps API, and provides remote browser access without a custom domain. The Quick Tunnel URL is temporary; the user creates the initial LibreChat admin account through the CLI.
2. **Keep the custom React app on Pages.** This avoids LibreChat's server/database, but does not satisfy the request for LibreChat's interface.
3. **Host the full LibreChat stack on a cloud platform.** Could provide a stable public URL, but introduces an external host/account and potentially paid resources; no such host was requested.

## Architecture

- Extend FastAPI with an OpenAI-compatible `/v1/models` and `/v1/chat/completions` surface used only by LibreChat on the internal Compose network.
- The adapter uses the Bearer value supplied by LibreChat as that user's Azure DevOps PAT, uses `ADO_ORGANIZATION` (default `ab-org`), and returns the existing deterministic read-only answer/data as a chat completion. Requests that ask for unsupported topics or omit the required project receive an explanatory completion.
- Run the official stable LibreChat release in Docker with MongoDB persistence and a mounted `librechat.yaml` custom endpoint pointing at `http://ado-mcp-api:8000/v1`.
- Run `cloudflared` as a Quick Tunnel targeting `http://librechat:3080`. Only LibreChat's UI/API is tunneled. The existing API remains internal to Compose and loopback-bound on the host.
- Set LibreChat registration off and provide a CLI command to create the first account/admin. The user owns and enters that password.
- Store the tunnel URL and generated LibreChat secrets in ignored local files / `.env` with restrictive permissions.
- After local and tunnel checks pass, change GitHub Pages to disabled and remove its workflow and now-unused frontend deployment plumbing.

## Constraints and Risks

- A Quick Tunnel address changes after a tunnel restart and does not provide the named tunnel's stable hostname.
- The current API's SSO mode depends on the Mac mini's Azure CLI cache. LibreChat will use each user's Azure DevOps PAT through the custom endpoint instead of sharing the host SSO session.
- The Pages workflow runs automatically on `main`; disable the repository Pages site and remove the workflow only after the replacement is reachable.
- Initial LibreChat account creation is a user handoff because the user must choose their own password.

## Success Criteria

- Compose configuration is valid and the LibreChat, MongoDB, API, and tunnel services start.
- `http://127.0.0.1:3080` serves LibreChat, `/health` reports healthy, and the tunnel output yields a reachable HTTPS URL.
- The ADO custom endpoint is configured with the user's own PAT entry, not a hard-coded shared credential.
- Pages configuration is disabled and `.github/workflows/pages.yml` is removed only after tunnel verification.
