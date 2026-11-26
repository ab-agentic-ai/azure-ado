# ADO Project Intelligence Implementation Plan

## 1. Fix and generalize ADO client primitives

- Add safe JSON POST for fixed read-query endpoints and a paged request helper that honors continuation tokens, page-size ceilings, and reports truncation.
- Correct ACL decoding to expose explicit/effective/inherited allow and deny masks, decode action names, omit empty ACEs, and resolve identities where possible.
- Preserve `AdoError` distinctions so composite operations can report partial access.

## 2. Expand the fixed read-only catalog

- Add project metadata, teams/members, refs, pull requests, pipeline definitions/runs, work item summaries, areas/iterations, test plan/run summaries, feeds/packages, and security/resource access metadata.
- Keep endpoint parameters validated and bounded. Never return secret values, service endpoint authorization data, or pipeline logs.
- Normalize each response and include counts/paging metadata for large collections.

## 3. Integrate Qwen routing and business workflows

- Extend the allowed operation schema and deterministic fallback phrases.
- Validate model JSON strictly; model cannot supply methods, URLs, arbitrary queries, or unrecognized filters.
- Add project overview, release readiness, delivery flow, and access review composites with bounded concurrency and per-section partial errors.
- Render readable summaries and focused tables, showing named permission subjects and effective access.

## 4. Documentation and manual verification

- Update README with supported coverage, examples, required read scopes, report semantics, bounds, and security limits.
- Manually verify syntax, Compose configuration, tool routing with mocked/local examples where feasible, and clean response formatting. No new or existing test suite is run as part of this task.
- Review the final diff for accidental writes, secret fields, unbounded response paths, and credentials in logs.
