# Marketplace Response and Opaque UI Design

## Intent

Make replies from all current and future Marketplace agents easier to scan, with a colorful Markdown presentation and a polished interface made from solid, opaque surfaces. Apply the experience globally so it does not depend on an individual agent or model.

## Current State

- LibreChat renders replies with one shared Markdown view and styles its content through `client/src/style.css`.
- The deployment supports a global theme in `librechat.yaml`, including separate light and dark palettes.
- LibreChat is rebuilt from an ignored pinned source checkout, so local source edits must be copied or applied by the tracked build script.
- The user selected visual styling of rendered Markdown, without changing agent prompts or generated response structure.

## Approaches

1. **Global Markdown styling and deployment theme (selected):** Add tracked CSS to the reproducible LibreChat build and configure a global light/dark theme with solid surfaces and colorful accents. Every existing and future Marketplace agent inherits the same presentation. This changes rendering without changing response content.
2. **Global agent instructions:** Ask each model to use more headings, tables, and callouts. This changes response content and model behavior, can conflict with an agent's own instructions, and is not guaranteed to be followed consistently.
3. **Per-agent styling:** Customize agents individually. This does not reliably cover future Marketplace agents and creates ongoing maintenance.

## Design

- Style rendered Markdown consistently for all agent replies: clear heading hierarchy, colored links and emphasis, readable lists, visually distinct quotations, refined tables, inline code, and syntax-highlighted fenced code blocks.
- Define a deployment-wide LibreChat theme with separate light and dark modes. Use solid backgrounds for page, panel, menu, and composer surfaces; use a small, consistent set of blue, teal, and violet accents for focus and response content.
- Keep text and interactive controls legible in both modes and preserve high-contrast preferences.
- Store custom CSS in a tracked patch file and have `scripts/build_librechat_custom.py` copy/import it into the pinned source before the image build. Do not make a manual edit only inside `.cache`.
- Do not change agent prompts, response structure, Marketplace permissions, or agent data.

## Boundaries

- This is a visual presentation change; models still decide what to say.
- The theme applies across the deployment, including users and agents added later.
- Existing conversations and agent records remain unchanged.

## Acceptance Criteria

- Current and future Marketplace-agent replies use the same styled Markdown presentation.
- Markdown headings, links, tables, quotes, inline code, and code blocks are visually distinct and readable.
- Light and dark modes use opaque solid surfaces and maintain readable contrast.
- Rebuilding the custom LibreChat image preserves the theme and Markdown styling.
