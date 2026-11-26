# Azure DevOps Compliance Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build a read-only Azure DevOps compliance chat app with a GitHub Pages frontend and a local Dockerized Python API.

**Architecture:** A Vite React app calls a FastAPI service running on the Mac mini. The service calls Azure DevOps REST APIs using an in-memory PAT or Azure CLI SSO identity.

**Tech Stack:** React, TypeScript, Vite, Python 3.12, FastAPI, Docker, GitHub Actions Pages.

**Spec:** `docs/superpowers/specs/2026-11-26-azure-devops-compliance-agent-design.md`

## Global Constraints

- All Azure DevOps operations are read-only.
- Do not persist or commit PATs or Azure credentials.
- Backend listens on localhost by default.
- Frontend is static and supports a repository subpath deployment.

## Review Focus

- Missing/invalid PAT or expired SSO: return an actionable auth error.
- Unsupported prompt: return supported capabilities rather than a fabricated answer.
- Empty or large Azure DevOps collections: show empty state and bound rendered results.
- Hosted UI calling local API: provide configurable API base URL and explicit CORS origins.
- Azure CLI credentials unavailable in container: document login/mount process and return a clear SSO setup error.

---

### Task 1: Create FastAPI backend and Azure DevOps client

**Files:** Create `backend/app/main.py`, `backend/app/ado.py`, `backend/requirements.txt`, `backend/Dockerfile`, `backend/.dockerignore`.

**Interfaces:** `POST /api/chat` accepts `{prompt, organization, project?, auth:{mode, pat?}}` and returns `{answer, data?, suggestions?}`. `GET /api/health` returns `{status:"ok"}`.

- [x] Create health and chat endpoints with input validation and credential redaction.
- [x] Implement Azure DevOps REST access for projects, permissions, repository policies, agent pools, library groups, and environments.
- [x] Implement supported-topic intent matching; report unsupported prompts explicitly.
- [x] Resolve PAT from request only; resolve SSO from Azure CLI credentials in container.
- [x] Containerize with non-root runtime, localhost port 8000, configurable CORS origins and organization defaults.
- [x] Verify image build and health endpoint when Docker daemon is available.

### Task 2: Create React chat frontend

**Files:** Create `frontend/package.json`, `frontend/index.html`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`.

**Interfaces:** UI posts the Task 1 request to a configurable `VITE_API_BASE_URL` (default `http://localhost:8000`).

- [x] Build a responsive compliance assistant UI with PAT/SSO selector, organization/project inputs, chat transcript, capability prompt chips, result/error/loading states.
- [x] Keep PAT input masked and clear it after each request; do not store it in browser storage.
- [x] Render API answer and structured results as readable tables/cards.
- [x] Configure Vite base path using `GITHUB_REPOSITORY` for Pages builds.
- [x] Verify frontend production build.

### Task 3: Add GitHub Pages deployment and local operations docs

**Files:** Create `.github/workflows/pages.yml`, `docker-compose.yml`, `.gitignore`; update `README.md`.

- [x] Add a GitHub Pages Actions workflow; publishing still requires the repository Pages source to be set to **GitHub Actions** and the `ADO_API_BASE_URL` variable to be configured.
- [x] Configure Docker Compose to build the backend and mount Azure CLI config read-only for SSO, copying it into a temporary writable container cache.
- [x] Document local Docker setup, PAT scopes, SSO login, API URL, GitHub Pages enablement, and Cloudflare as an optional user-managed routing step.
- [x] Inspect the final diff and verify frontend build and Docker health.
