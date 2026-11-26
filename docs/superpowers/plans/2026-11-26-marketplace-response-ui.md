# Marketplace Response and Opaque UI Implementation Plan

> **For agentic workers:** Execute inline; implementation-agent delegation is disabled by the current task instructions.

**Goal:** Give every current and future Marketplace agent a colorful, readable Markdown presentation and apply solid, opaque UI surfaces globally.

**Architecture:** Define LibreChat's global light/dark deployment theme in `librechat.yaml`. Add a tracked Markdown CSS patch and make the pinned-source build copy and import it, so the visual treatment survives image rebuilds without modifying agent prompts.

**Tech Stack:** LibreChat v0.8.9, YAML theme tokens, CSS, Python build script, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-26-marketplace-response-ui-design.md`

## Global Constraints

- Styling applies to the shared Markdown renderer, not to individual agents or models.
- The theme covers both light and dark modes and uses solid surfaces.
- High-contrast preferences remain available.
- The custom CSS lives in tracked project files and is reapplied on every custom image build.
- Do not change response content, agent prompts, Marketplace permissions, or stored agent data.
- Do not add or run tests; verify with the production image build and runtime checks.

## Review Focus

- New CSS must stay scoped to Markdown and avoid breaking non-chat pages.
- Color tokens must be defined for both modes with sufficient text contrast.
- Existing high-contrast mode must override the custom colors as LibreChat intends.
- The patch must reapply cleanly after the pinned source files are reset.
- Build/import ordering must include the stylesheet in the production bundle.

---

### Task 1: Global theme and response styling

**Files:**
- Modify: `librechat.yaml`
- Create: `scripts/librechat_patches/agentic-response-theme.css`
- Modify: `scripts/build_librechat_custom.py`
- Patch source: `.cache/librechat-v0.8.9/client/src/main.jsx`

**Interfaces:**
- Use LibreChat's `interface.theme` inline definition: `{version: 1, name, modes: {light, dark}}`.
- Import the tracked CSS patch from the pinned client's `main.jsx` so the generated production bundle includes it.

- [x] Add the global theme with opaque page, chat, sidebar, composer, menu, popover, and code surfaces; use coordinated blue, teal, and violet accents and readable text colors in both modes.
- [x] Style Markdown headings, links, list markers, quotations, tables, inline code, fenced code panels, and syntax tokens. Keep selectors scoped to the rendered Markdown.
- [x] Copy the CSS patch into the LibreChat source and import it from `main.jsx` in the build script; reset `main.jsx` before each patch application to keep builds repeatable.

### Task 2: Build, restart, and verify

**Files:**
- Runtime: local LibreChat service only.

- [x] Build the pinned custom image and confirm the production build completes.
- [x] Recreate only the LibreChat container, retaining MongoDB, the Cloudflare tunnel, and named data volumes.
- [x] Check LibreChat health, confirm the deployment theme appears in runtime configuration, and confirm the compiled app includes the response stylesheet.

## Self-Review

- Spec coverage: universal response styling and both-mode opaque theme are Task 1; rebuild persistence and deployment verification are Task 2.
- Future Marketplace agents inherit the shared renderer/theme; no agent-specific setup is required.
- Existing agent instructions and generated response content remain unchanged.
