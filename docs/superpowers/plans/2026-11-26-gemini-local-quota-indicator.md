# Gemini Local Quota Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a composer ring showing local Gemini requests during the last minute against the selected model's configured RPM cap.

**Architecture:** Add a small React component to the pinned LibreChat client and patch the composer build script to install and mount it beside the model picker. Store per-model request timestamps in local storage and derive the rolling 60-second count in the browser.

**Tech Stack:** LibreChat v0.8.9, React, TypeScript, localStorage, Docker image build.

**Spec:** `docs/superpowers/specs/2026-11-26-gemini-local-quota-indicator.md`

## Global Constraints

- The meter covers only requests started by this browser profile.
- Display only configured RPM; do not claim TPM or RPD consumption.
- Do not add retry, queue, or automatic model switching behavior.
- Keep the current context-window indicator unchanged.

## Review Focus

- A `429` attempt must count locally so the ring does not understate requests sent.
- A model without an RPM entry must render no ring.
- Old or malformed localStorage values must be safely ignored.
- Switching models must show that model's own rolling count and configured cap.
- A fresh page load must preserve unexpired timestamps.

---

### Task 1: Implement the local Gemini RPM meter

**Files:**
- Create: `scripts/librechat_patches/GeminiQuotaIndicator.tsx`
- Modify: `scripts/build_librechat_custom.py`
- Runtime source generated at build: `.cache/librechat-v0.8.9/client/src/components/Chat/Input/GeminiQuotaIndicator.tsx`
- Runtime source patched at build: `.cache/librechat-v0.8.9/client/src/components/Chat/Input/Composer/Bar.tsx`

**Interfaces:**
- `GeminiQuotaIndicator({ endpoint, model, agentId, isSubmitting }: ...)` resolves an `agents` endpoint through the selected marketplace agent's `provider` and `model`, then renders only for Google models with configured RPM.
- The configured caps are: `gemini-3.5-flash-lite: 15`, `gemini-3.1-flash-lite: 15`, `gemini-2.5-flash-lite: 10`, `gemini-3.6-flash: 5`, and `gemini-3.8-flash: 5`.

- [ ] Add the component with per-model rolling 60-second localStorage timestamps, expiration refresh, malformed-data handling, and an accessible circular meter/label.
- [ ] Extend the build script to copy the component into the pinned checkout and mount it beside the model selector using the active conversation endpoint/model and submit state.
- [ ] Build the custom LibreChat Docker image and recreate the local LibreChat service.
- [ ] Check the service status and visually inspect the composer; confirm the model picker and existing context indicator remain present.
