# Marketplace-Only User Access Implementation Plan

> **For agentic workers:** This plan is executed inline. The current task policy prohibits spawning implementation agents.

**Goal:** Enable immediate signup for regular LibreChat users while limiting them to Marketplace agents shared by an administrator.

**Architecture:** Enable local email registration in Docker configuration. Patch the pinned LibreChat v0.8.9 source during the reproducible image build to synchronize USER-specific permissions, filter the model selector by role, and reject non-agent generation requests on the server. Preserve the existing ADMIN permissions and agent resource ACLs.

**Tech Stack:** Docker Compose, LibreChat v0.8.9, TypeScript/React, Node.js API, YAML.

**Spec:** `docs/superpowers/specs/2026-11-26-marketplace-only-user-access.md`

## Global Constraints

- Existing ADMIN account and stored data remain intact.
- New registrations immediately receive the USER role.
- USER can use Marketplace agents shared with their account or group.
- USER cannot create, share, or publicly publish agents.
- Direct non-agent model endpoints are unavailable to USER, even by direct API request.
- ADMIN retains full model and agent choices.
- Do not add or run tests unless the user asks; validate with image build and runtime checks instead.

## Review Focus

- Stored USER role permissions may predate this deployment; startup synchronization must update those permissions without modifying ADMIN.
- A user may call model endpoints directly or use a stale conversation; server enforcement must reject those requests.
- Agent-backed model specs and search results must remain visible to USER when the referenced agent is shared.
- Public Marketplace listing must not bypass the existing per-agent ACL.
- Registration must be available without weakening email login or authentication configuration.

---

### Task 1: Signup and USER policy initialization

**Files:**
- Modify: `docker-compose.librechat.yml`
- Modify: `librechat.yaml` only for enabling Marketplace in the interface; keep global agent create/share values unset so ADMIN is unaffected.
- Modify: `scripts/build_librechat_custom.py`
- Patch source: `.cache/librechat-v0.8.9/api/server/index.js` through the build script.

**Interfaces:**
- Uses LibreChat `updateInterfacePermissions` and `updateAccessPermissions` startup functions already imported in the pinned `api/server/index.js`.
- USER policy values: `agents.use=true`, `agents.create=false`, `agents.share=false`, `agents.share_public=false`, `marketplace.use=true`.
- Registration environment setting: `ALLOW_REGISTRATION=true`.

- [x] Set `ALLOW_REGISTRATION` to true in Compose; preserve email login, unverified email login, and social login settings.
- [x] Add a USER-only permission sync after LibreChat's standard interface permission sync. Persist the five values above on startup, including for an existing USER role; do not alter ADMIN.
- [x] Enable Marketplace in the UI configuration without applying restrictive global agent settings to ADMIN.
- [x] Build the custom image and inspect the resulting config/startup logs without printing secrets.

### Task 2: Role-aware model selector

**Files:**
- Modify: `scripts/build_librechat_custom.py`
- Patch source: `.cache/librechat-v0.8.9/client/src/components/Chat/Menus/Endpoints/ModelSelector.tsx`.

**Interfaces:**
- Use the authenticated user role from LibreChat's existing `useAuthContext` hook.
- USER-visible choices are the agents endpoint, model specs that resolve to agents, and corresponding agent search results. ADMIN selector behavior is unchanged.

- [x] Filter selector choices and search results for USER, preserving selection rendering for shared agents.
- [x] Leave ADMIN model specs, custom endpoints, and direct providers available.
- [x] Rebuild the image and verify the selector changes compile as part of the production build.

### Task 3: Server enforcement and rollout

**Files:**
- Modify: `scripts/build_librechat_custom.py`
- Patch source: `.cache/librechat-v0.8.9/api/server/middleware/buildEndpointOption.js`.

**Interfaces:**
- The generation middleware already determines whether a request uses the agents endpoint.
- Authenticated non-admin requests to every non-agent endpoint receive HTTP 403 with the message `This account can use Marketplace agents only.`

- [x] Add the guard before provider/model execution, leaving agent requests to existing agent ACL and permission middleware.
- [x] Build the custom LibreChat image and restart the LibreChat Compose service.
- [x] Verify service health, registration enabled state, and stored USER/ADMIN permission separation using the local deployment; do not expose account credentials or tunnel tokens.

End-to-end signup and authenticated request flows were not exercised because that would create a persistent user and require account credentials. The production client/server image build and service health checks passed.

## Self-Review

- Spec coverage: registration and role assignment are Task 1; USER/admin UI separation is Task 2; direct API blocking and preserving agent ACLs are Task 3.
- Task interfaces agree: Task 1 supplies USER role policy; Task 2 uses authenticated role; Task 3 independently enforces role restrictions at request time.
- Admin safety: configuration avoids global restrictive agent settings; startup writes only USER permissions.
- Per-user/group agent sharing continues to use LibreChat's existing agent resource ACL.
