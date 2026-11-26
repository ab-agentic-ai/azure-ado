# Azure DevOps Compliance Agent Design

## Intent

Create a chat-style Azure DevOps compliance assistant from the README, with a React and TypeScript UI hosted as a static GitHub Pages site and a Python API running locally in Docker on the Mac mini.

## Goals

- Let a user connect through a PAT or Azure CLI SSO session.
- Answer prompts about projects, permissions, repository policies, agent pools, library groups, and environments using Azure DevOps REST APIs.
- Keep credentials in the local backend and provide clear loading, error, and result states in the UI.
- Include GitHub Pages and local Docker configuration and setup instructions.

## Non-goals

- Publicly exposing the local API or configuring Cloudflare tunnels/DNS automatically.
- Using an external LLM service or sending Azure DevOps data to a third party. The first version uses deterministic intent matching and REST-backed summaries.
- Modifying Azure DevOps settings; this is a read-only inspection tool.

## Constraints and calls

- Frontend: React, TypeScript, Vite, static build under a repository subpath for GitHub Pages.
- Backend: Python 3.12, FastAPI, Docker, Azure DevOps REST API.
- PAT is submitted from the browser to the local API for the current session only and is not persisted. SSO uses an `az login` session available to the backend container via a mounted Azure CLI config directory.
- API binds to localhost by default. A user may later put it behind their already-configured Cloudflare setup, following the README.
- No credentials, Azure data, or Docker secrets are committed.

## Approaches

1. **Static frontend plus local API container (selected):** GitHub Pages hosts the UI while the user’s Mac mini runs the API. This meets the README’s hosting and local-backend requirements, with an API URL setting needed when using the hosted UI.
2. **Single container serving UI and API:** simpler local setup, but GitHub Pages cannot host the backend and the UI would not be separately hosted there.
3. **Hosted cloud API:** supports global access more directly, but contradicts the README’s local Mac mini backend and requires cloud credentials/infrastructure.

## Architecture

The UI contains connection settings and a chat transcript. Each prompt is sent to the local API with either a PAT or SSO mode and the organization/project context. The API maps supported prompt intents to read-only Azure DevOps REST calls, normalizes results, and returns a text answer plus structured data. Unsupported requests return suggested supported topics. The frontend is built with a configurable Vite base path and deployed by GitHub Actions to Pages.

## Open implementation details

- Select sensible API versions and REST endpoints for each listed Azure DevOps resource.
- Provide safe CORS configuration for local and GitHub Pages origins.
- Document PAT scopes, Azure CLI login, Docker startup, GitHub Pages setup, and optional Cloudflare routing without printing local secrets.
