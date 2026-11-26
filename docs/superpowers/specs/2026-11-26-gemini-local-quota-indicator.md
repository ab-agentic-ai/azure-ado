# Gemini Local Quota Indicator Design

## Goal

Show a compact, context-window-style circular indicator in the LibreChat composer for locally observed Gemini request usage against the selected model's configured requests-per-minute limit.

## Current State

- LibreChat runs from a pinned `v0.8.9` source checkout under `.cache/librechat-v0.8.9`.
- `scripts/build_librechat_custom.py` patches the composer to place the model selector there and builds the custom image.
- Gemini models and the API key are configured in `.env`; Google model lists are passed through Docker Compose.
- Google's model rate-limit dashboard is not exposed as a live account-wide quota counter through the standard text chat endpoint. LibreChat's standard Google endpoint uses `streamGenerateContent`; Gemini Live models use the distinct bidirectional Live API.

## Design

- Add a compact circular quota meter beside the Gemini model selection in the composer. Resolve marketplace agents to their configured provider/model so Gemini-backed agents show the same meter.
- Meter value is requests started in this browser during the preceding 60 seconds divided by the configured RPM limit for the selected Gemini model.
- Keep request timestamps in browser local storage so a reload retains the rolling-minute count. Count attempts when sent, including failed/429 requests, to avoid implying unused capacity after a rejected call.
- Show an accessible tooltip or label with model name, `N of limit requests/min`, and a clear `This browser only` scope note. Announce state to assistive technology; do not rely on ring color alone.
- Update the meter when a request is sent, when its timestamp expires from the rolling window, and when the selected Gemini model changes. Hide the meter for non-Google endpoints and models without a configured RPM value.
- Keep per-model RPM limits in one maintained configuration map, initialized from the user's Google AI Studio quota screenshot. Treat limits as editable estimates because provider quotas can change.
- Preserve the existing context-window indicator and composer layout on narrow screens.

## Boundaries

- This is an estimate for requests sent from the current browser profile. It does not read Google account/project usage, include other browsers or AI Studio, or guarantee that Google will accept a request.
- This first version displays RPM only. It will not infer TPM/RPD usage from character counts or claim those quotas are exact.
- No automatic retry, delay, or model switching is added.
- No Gemini Live API models are added to the standard text-chat model list.

## Acceptance Criteria

1. Selecting an enabled Gemini text model or Gemini-backed marketplace agent displays its local rolling-minute request usage and configured RPM cap in the composer.
2. Sending a request increases usage immediately; the count drops after its 60-second window expires.
3. Reloading the page retains still-active request timestamps.
4. Changing model changes the cap and recomputes the displayed ratio for that model.
5. Non-Gemini selections and models with no configured cap show no quota ring.
6. The indicator communicates its local-only scope accessibly and leaves the existing context-window meter intact.
