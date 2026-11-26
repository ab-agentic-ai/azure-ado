# Azure DevOps Project Intelligence Design

## Intent

Expand DevOps-Agent from a handful of list operations into a practical, read-only Azure DevOps project intelligence assistant. Qwen selects a fixed operation; the Python backend validates it, calls ADO using the user's PAT, and returns readable summaries backed by normalized records.

## Interaction

- Continue using LibreChat's DevOps-Agent endpoint and the existing local Qwen model.
- Resolve project references from the request, conversation, configured default, or saved hint.
- Route to a fixed catalog of read-only operations. Never let model output choose a URL, HTTP method, or write operation.
- Support focused queries and composites such as project overview, release readiness, delivery flow, and access review.
- Return concise Markdown with counts, key findings, explicit partial-access notices, and bounded detail tables.

## Catalog and coverage

Cover projects; teams and membership; repositories, branches/refs, policies, and pull requests; pipeline definitions and recent runs; work items with counts and aging/status summaries; areas and iterations; environments and pipeline authorization; agent pools; variable group metadata and keys (never values); test plans/runs; package/feed metadata; and project/security permissions. Add project overview, release readiness, delivery health, and access review composites that call relevant catalog operations and synthesize their results.

All collection operations use paging, with a conservative default page size and a hard maximum. Responses report whether more results exist and distinguish empty results from inaccessible or unsupported resources. Aggregate reports use bounded samples and counts so they remain usable in chat.

## Access and security

- Read-only operations only. WIQL may use HTTP POST because that is ADO's query endpoint, but it remains a read query; fixed query templates, project scope, bounded results, and no arbitrary WIQL from the model.
- Never return variable values, service endpoint credentials, secret-bearing configuration, or pipeline logs.
- Permission reports decode named action bits and present identity display name/type when ADO resolves it. Show explicit and effective/inherited allow/deny separately; omit zero ACEs and label unresolved identities.
- Honor the PAT's actual scopes and the caller's project access. Per-resource errors are surfaced in a partial report rather than disguised as empty data.
- Qwen is an intent router and summarizer only; data returned from ADO is the source of truth. No weight training. Existing minimal project/topic memory remains local and stores no ADO result sets.

## Business workflows

- Release readiness: active pipeline health, recent failed runs, environment approvals/authorization, branch policy gaps, and open high-priority work.
- Delivery flow: work item state/age, iteration progress, recent build outcomes, and stale branches.
- Access review: named users/groups and effective permissions, pipeline access to environments/variable groups, and unresolved security identities.
- Repository hygiene: default branches, policy coverage, and stale refs.

These reports identify evidence and gaps; they do not claim compliance certification or modify ADO.

## Implementation shape

Keep one ADO client with safe GET and fixed-body read-query support, pagination helpers, endpoint handlers, and normalizers. Define a single operation registry with required project context and safe parameters. Qwen returns a JSON operation plus project/filters; server validation and deterministic phrase routing provide fallback. Composite workflows call registry operations with bounded concurrency and return per-operation status. Formatting is topic-aware and never dumps raw JSON.

## Out of scope

Writes to ADO, arbitrary REST paths, arbitrary WIQL, secret retrieval, model fine-tuning, and bypassing ADO authorization or service/API limits.
