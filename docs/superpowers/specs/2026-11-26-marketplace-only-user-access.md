# Marketplace-Only User Access Design

## Intent

Allow people to create LibreChat accounts and immediately use Marketplace agents that an administrator shares with them, while keeping regular accounts out of direct model endpoints and agent creation.

## Current State

- The local LibreChat database has one `ADMIN` account.
- Email/password login is enabled, but `ALLOW_REGISTRATION` is false.
- Regular LibreChat users can currently select configured models/endpoints; LibreChat's default `USER` role can also create agents.
- The deployment runs a pinned LibreChat `v0.8.9` image built by `scripts/build_librechat_custom.py`.

## Approaches

1. **LibreChat configuration only:** Enable signup and Marketplace permissions. This is simpler but does not reliably prevent direct model endpoint requests.
2. **Role-aware UI plus server enforcement (selected):** Enable signup and configure USER role permissions, filter the model selector for non-admins, and reject non-agent model requests in LibreChat's server middleware. This keeps the existing admin experience and enforces Marketplace-only usage even if a user bypasses the selector.

## Design

- Enable local account registration. Existing first/administrator account remains `ADMIN`; later signups receive LibreChat's default `USER` role and can use the service immediately.
- Seed `USER` permissions for `AGENTS.USE=true`, `AGENTS.CREATE=false`, `AGENTS.SHARE=false`, `AGENTS.SHARE_PUBLIC=false`, and `MARKETPLACE.USE=true`.
- Keep `interface.modelSelect` enabled for admins. For non-admins, show only the Agents endpoint and model specs that resolve to agents; hide direct provider/custom model choices.
- Add a server guard to reject non-agent model endpoint requests from authenticated non-admin users with a clear 403 explanation. Allow the `ADMIN` role to use all existing endpoints.
- Keep LibreChat's resource-level agent permissions authoritative. Admins make agents available by sharing them with the USER role or everyone; unshared agents remain unavailable.
- Do not add pending-account approval, email/SAML/SSO setup, custom user roles, or an Admin Panel service in this change.

## Boundaries

- Sign-up is immediate. New users are not held for per-account approval.
- A user can chat only with agents that LibreChat's agent ACL grants to them; Marketplace visibility alone does not bypass resource permissions.
- The existing administrator and stored chats remain intact.

## Acceptance Criteria

1. The existing account remains `ADMIN`; a new registration receives `USER`.
2. A `USER` can open the Marketplace and chat with agents shared to their role or everyone.
3. A `USER` cannot create or share agents and cannot select direct provider/custom model endpoints from the UI.
4. A direct non-agent chat request from a non-admin receives HTTP 403 with a clear Marketplace-only message.
5. The `ADMIN` retains current model selection and direct endpoint access.
