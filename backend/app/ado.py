"""Bounded, read-only Azure DevOps REST API tools."""

from __future__ import annotations

import base64
import asyncio
import os
from typing import Any
from urllib.parse import quote

import httpx
from azure.identity import AzureCliCredential

API_VERSION = "7.1"
RESOURCE = "499b84ac-1321-427f-aa17-267ca6975798"
PROJECT_NAMESPACE = "52d39943-cb85-4d7f-8fa8-c6baac873819"
LIBRARY_NAMESPACE = "b7e84409-6553-448a-bbb2-af228e07cbeb"
PAGE_SIZE = 100
MAX_ITEMS = 500


class AdoError(RuntimeError):
    pass


class AdoClient:
    def __init__(self, organization: str, mode: str, pat: str | None = None):
        self.organization = organization.strip().rstrip("/")
        if not self.organization:
            raise AdoError("Enter an Azure DevOps organization name.")
        self.base = f"https://dev.azure.com/{quote(self.organization, safe='')}"
        if mode == "pat":
            if not pat:
                raise AdoError("Enter a PAT or choose Azure CLI SSO.")
            token = base64.b64encode(f":{pat}".encode()).decode()
            self.headers = {"Authorization": f"Basic {token}"}
        elif mode == "sso":
            try:
                token = AzureCliCredential().get_token(RESOURCE + "/.default").token
            except Exception as exc:
                raise AdoError("Azure CLI SSO is unavailable. Run `az login` on the Mac mini and restart the container.") from exc
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            raise AdoError("Choose PAT or Azure CLI SSO authentication.")

    async def request(self, method: str, path: str, params: dict[str, Any] | None = None, json_body: Any = None) -> Any:
        query = {"api-version": API_VERSION, **(params or {})}
        async with httpx.AsyncClient(timeout=30) as client:
            response = None
            for attempt in range(3):
                try:
                    response = await client.request(method, self.base + path, params=query, headers=self.headers, json=json_body)
                except httpx.HTTPError as exc:
                    if attempt == 2:
                        raise AdoError("Azure DevOps could not be reached after automatic retries. Check connectivity and try again.") from exc
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                if response.status_code not in {429, 502, 503, 504} or attempt == 2:
                    break
                try:
                    delay = min(max(float(response.headers.get("Retry-After", "0.5")), 0.25), 3.0)
                except ValueError:
                    delay = 0.5 * (2 ** attempt)
                await asyncio.sleep(delay)
        assert response is not None
        if response.status_code == 401:
            raise AdoError("Azure DevOps rejected the credentials. Check the PAT or refresh `az login`.")
        if response.status_code == 403:
            raise AdoError("Your Azure DevOps identity does not have permission to read this resource.")
        if response.status_code == 404:
            raise AdoError("The requested Azure DevOps resource was not found. Check the organization and project name.")
        if response.is_error:
            raise AdoError(f"Azure DevOps returned HTTP {response.status_code}: {response.text[:250]}")
        if response.status_code == 204 or not response.content:
            return {}
        data = response.json()
        continuation = response.headers.get("x-ms-continuationtoken")
        if continuation and isinstance(data, dict):
            data["_continuationToken"] = continuation
        return data

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self.request("GET", path, params)

    async def read_query(self, path: str, body: dict[str, Any], params: dict[str, Any] | None = None) -> Any:
        # ADO's WIQL endpoint is POST by API design, but only fixed, read-only query templates call this.
        return await self.request("POST", path, params, body)

    async def paged(self, path: str, params: dict[str, Any] | None = None, *, value_key: str = "value", cap: int = MAX_ITEMS) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        continuation = None
        capped = min(max(int(cap), 1), MAX_ITEMS)
        while len(rows) < capped:
            query = {"$top": min(PAGE_SIZE, capped - len(rows)), **(params or {})}
            if continuation:
                query["continuationToken"] = continuation
            data = await self.get(path, query)
            batch = data.get(value_key, []) if isinstance(data, dict) else []
            rows.extend(batch[:capped - len(rows)])
            continuation = (data.get("continuationToken") or data.get("_continuationToken")) if isinstance(data, dict) else None
            if not continuation:
                break
        return {"items": rows, "truncated": bool(continuation), "count": len(rows)}

    async def projects(self) -> list[dict[str, Any]]:
        return (await self.paged("/_apis/projects", {"stateFilter": "all"}))["items"]

    async def project_id(self, project: str) -> str:
        if not project or not project.strip():
            raise AdoError("Enter a project name for this query.")
        data = await self.get(f"/_apis/projects/{quote(project.strip(), safe='')}")
        return data["id"]

    async def graph_get(self, path: str, params: dict[str, Any] | None = None, version: str = "7.1") -> Any:
        url = f"https://vssps.dev.azure.com/{quote(self.organization, safe='')}{path}"
        query = {"api-version": version, **(params or {})}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=query, headers=self.headers)
        if response.status_code == 401:
            raise AdoError("Azure DevOps rejected the credentials. Check the PAT.")
        if response.status_code == 403:
            raise AdoError("Your PAT needs Azure DevOps Graph read access to list project groups and members.")
        if response.status_code == 404:
            raise AdoError("The Azure DevOps Graph resource was not found.")
        if response.is_error:
            raise AdoError(f"Azure DevOps Graph returned HTTP {response.status_code}: {response.text[:200]}")
        if not response.content:
            return {}
        data = response.json()
        continuation = response.headers.get("x-ms-continuationtoken")
        if continuation and isinstance(data, dict):
            data["_continuationToken"] = continuation
        return data

    async def graph_paged(self, path: str, params: dict[str, Any], version: str, cap: int = 500) -> list[dict[str, Any]]:
        rows, continuation = [], None
        while len(rows) < cap:
            query = dict(params)
            if continuation:
                query["continuationToken"] = continuation
            data = await self.graph_get(path, query, version)
            rows.extend(data.get("value", [])[:cap - len(rows)])
            continuation = data.get("continuationToken") or data.get("_continuationToken")
            if not continuation:
                break
        return rows

    async def identity_names(self, subject_descriptors: list[str]) -> dict[str, str]:
        names: dict[str, str] = {}
        for start in range(0, min(len(subject_descriptors), 1000), 25):
            batch = subject_descriptors[start:start + 25]
            try:
                url = f"https://vssps.dev.azure.com/{quote(self.organization, safe='')}/_apis/identities"
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(url, params={"subjectDescriptors": ",".join(batch), "api-version": "7.1"}, headers=self.headers)
                if response.is_error:
                    continue
                data = response.json()
                subjects = data.get("value", []) if isinstance(data, dict) else data
                if isinstance(subjects, list):
                    for subject in subjects:
                        if not isinstance(subject, dict):
                            continue
                        display = subject.get("providerDisplayName") or subject.get("customDisplayName") or subject.get("displayName") or subject.get("uniqueName")
                        if display:
                            for descriptor in (subject.get("subjectDescriptor"), subject.get("descriptor")):
                                if descriptor:
                                    names[descriptor] = display
            except (httpx.HTTPError, ValueError):
                continue
        return names

    async def project_groups(self, project_id: str) -> list[dict[str, Any]]:
        scope = await self.graph_get(f"/_apis/graph/descriptors/{quote(project_id, safe='')}")
        scope_descriptor = scope.get("value")
        if not scope_descriptor:
            raise AdoError("Azure DevOps did not return a Graph scope for this project.")
        groups = await self.graph_paged("/_apis/graph/groups", {"scopeDescriptor": scope_descriptor}, "7.0-preview.1", cap=200)
        groups = [group for group in groups if group.get("descriptor")]
        semaphore = asyncio.Semaphore(5)

        async def load_members(group: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
            async with semaphore:
                result = await self.graph_get(
                    f"/_apis/graph/memberships/{quote(group['descriptor'], safe='')}",
                    {"direction": "down"}, "7.1-preview.1",
                )
            return group, [member.get("memberDescriptor") for member in result.get("value", []) if member.get("memberDescriptor")]

        membership_results = await asyncio.gather(*(load_members(group) for group in groups), return_exceptions=True)
        members_by_group: dict[str, list[str]] = {}
        all_members: list[str] = []
        errors = []
        for result in membership_results:
            if isinstance(result, Exception):
                errors.append(result)
                continue
            group, descriptors = result
            members_by_group[group["descriptor"]] = descriptors[:100]
            all_members.extend(descriptors[:100])
        names = await self.identity_names(list(dict.fromkeys(all_members)))
        rows = []
        for group in groups:
            descriptors = members_by_group.get(group["descriptor"], [])
            rows.append({
                "name": group.get("displayName") or group.get("principalName") or "Unnamed group",
                "description": group.get("description"),
                "members": [names.get(descriptor, "Unresolved member") for descriptor in descriptors],
                "memberCount": len(descriptors),
                "membersTruncated": len(descriptors) >= 100,
            })
        if errors and not rows:
            raise AdoError(str(errors[0]))
        return rows

    async def acl_rows(self, namespace_id: str, token: str) -> list[dict[str, Any]]:
        namespace, acl_data = await self.get(f"/_apis/securitynamespaces/{namespace_id}"), await self.get(
            f"/_apis/accesscontrollists/{namespace_id}", {"token": token, "includeExtendedInfo": "true", "recurse": "false"}
        )
        actions = namespace.get("actions", [])
        descriptors = []
        for acl in acl_data.get("value", []):
            descriptors.extend(acl.get("acesDictionary", {}).keys())
        names: dict[str, dict] = {}
        # ACL descriptors are legacy identities; use the Identity API for display names.
        for offset in range(0, min(len(descriptors), 100), 25):
            batch = descriptors[offset:offset + 25]
            try:
                url = f"https://vssps.dev.azure.com/{quote(self.organization, safe='')}/_apis/identities"
                async with httpx.AsyncClient(timeout=30) as client:
                    response = None
                    for attempt in range(3):
                        try:
                            response = await client.get(url, params={"descriptors": ",".join(batch), "api-version": "7.1"}, headers=self.headers)
                        except httpx.HTTPError:
                            if attempt == 2:
                                raise
                            await asyncio.sleep(0.5 * (2 ** attempt))
                            continue
                        if response.status_code not in {429, 502, 503, 504} or attempt == 2:
                            break
                        try:
                            delay = min(max(float(response.headers.get("Retry-After", "0.5")), 0.25), 3.0)
                        except ValueError:
                            delay = 0.5 * (2 ** attempt)
                        await asyncio.sleep(delay)
                if response is None or response.is_error:
                    break
                identity_data = response.json()
                if isinstance(identity_data, dict):
                    subjects = identity_data.get("value", identity_data.get("identities"))
                    if subjects is None:
                        subjects = [item for item in identity_data.values() if isinstance(item, dict)]
                else:
                    subjects = identity_data
                if not isinstance(subjects, list):
                    break
                for subject in subjects:
                    if not isinstance(subject, dict):
                        continue
                    names[subject.get("descriptor", "")] = {
                        "displayName": subject.get("providerDisplayName") or subject.get("customDisplayName") or subject.get("displayName"),
                        "principalName": subject.get("uniqueName"),
                        "subjectKind": "Group" if subject.get("isContainer") else "User",
                    }
            except (AdoError, httpx.HTTPError, ValueError):
                break

        def decode(mask: int) -> list[str]:
            decoded = [action.get("displayName") or action.get("name") for action in actions if mask & int(action.get("bit", 0))]
            known_bits = 0
            for action in actions:
                try:
                    known_bits |= int(action.get("bit", 0))
                except (TypeError, ValueError):
                    continue
            remaining = mask & ~known_bits
            if remaining:
                decoded.append(f"Unmapped permission bits 0x{remaining:X}")
            if mask and not decoded:
                decoded.append(f"Unmapped permission mask 0x{mask:X}")
            return decoded

        rows = []
        for acl in acl_data.get("value", []):
            for descriptor, ace in acl.get("acesDictionary", {}).items():
                extended = ace.get("extendedInfo") or {}
                explicit_allow, explicit_deny = int(ace.get("allow", 0)), int(ace.get("deny", 0))
                effective_allow = int(extended.get("effectiveAllow", explicit_allow))
                effective_deny = int(extended.get("effectiveDeny", explicit_deny))
                inherited_allow = int(extended.get("inheritedAllow", effective_allow & ~explicit_allow))
                inherited_deny = int(extended.get("inheritedDeny", effective_deny & ~explicit_deny))
                if not any((explicit_allow, explicit_deny, effective_allow, effective_deny, inherited_allow, inherited_deny)):
                    continue
                subject = names.get(descriptor, {})
                rows.append({
                    "identity": subject.get("displayName") or subject.get("principalName") or "Unresolved identity",
                    "identityType": subject.get("subjectKind") or "Unknown",
                    "descriptor": descriptor,
                    "allow": decode(explicit_allow), "deny": decode(explicit_deny),
                    "effectiveAllow": decode(effective_allow), "effectiveDeny": decode(effective_deny),
                    "inheritedAllow": decode(inherited_allow), "inheritedDeny": decode(inherited_deny),
                })
        return rows

    async def inspect(self, topic: str, project: str | None, prompt: str = "", filters: dict | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        project_path = quote(project or "", safe="")
        if topic == "projects":
            return [{"name": x.get("name"), "state": x.get("state"), "visibility": x.get("visibility"), "id": x.get("id"), "url": x.get("url")} for x in await self.projects()]
        if topic == "agent pools":
            return [{"name": x.get("name"), "isHosted": x.get("isHosted"), "poolType": x.get("poolType"), "size": x.get("size")} for x in (await self.paged("/_apis/distributedtask/pools", {"poolType": "automation"}))["items"]]
        pid = await self.project_id(project or "")
        if topic == "project details":
            return [await self.get(f"/_apis/projects/{quote(project or '', safe='')}", {"includeCapabilities": "true"})]
        if topic == "project groups":
            return await self.project_groups(pid)
        if topic == "pipeline settings":
            definitions = (await self.paged(f"/{project_path}/_apis/build/definitions", {
                "includeAllProperties": "true", "includeLatestBuilds": "true",
            }))["items"]
            rows = []
            for definition in definitions:
                repository = definition.get("repository") or {}
                process = definition.get("process") or {}
                latest = definition.get("latestCompletedBuild") or definition.get("latestBuild") or {}
                variables = definition.get("variables") or {}
                rows.append({
                    "id": definition.get("id"), "name": definition.get("name"), "folder": definition.get("path"),
                    "type": definition.get("type"), "queueStatus": definition.get("queueStatus"),
                    "agentQueue": (definition.get("queue") or {}).get("name"),
                    "repository": repository.get("name"), "defaultBranch": repository.get("defaultBranch"),
                    "yamlFile": process.get("yamlFilename"), "variableNames": list(variables.keys()),
                    "triggerTypes": [trigger.get("triggerType") for trigger in (definition.get("triggers") or []) if isinstance(trigger, dict)],
                    "latestBuild": {"id": latest.get("id"), "number": latest.get("buildNumber"), "result": latest.get("result"), "finishTime": latest.get("finishTime")},
                })
            return rows
        if topic == "teams":
            teams = (await self.paged(f"/{project_path}/_apis/teams", {"$mine": "false"}))["items"]
            rows = []
            for team in teams[:50]:
                try:
                    members = await self.paged(f"/{project_path}/_apis/teams/{quote(team.get('id', ''), safe='')}/members", {"$top": 100})
                    rows.append({"team": team.get("name"), "description": team.get("description"), "members": [m.get("identity", {}).get("displayName") for m in members["items"]], "memberCount": members["count"], "truncated": members["truncated"]})
                except AdoError as exc:
                    rows.append({"team": team.get("name"), "error": str(exc)})
            return rows
        if topic == "repositories":
            repos = (await self.paged(f"/{project_path}/_apis/git/repositories"))["items"]
            return [{"id": r.get("id"), "name": r.get("name"), "defaultBranch": r.get("defaultBranch"), "size": r.get("size"), "isDisabled": r.get("isDisabled"), "remoteUrl": r.get("remoteUrl")} for r in repos]
        if topic in {"branches", "pull requests"}:
            repos = (await self.paged(f"/{project_path}/_apis/git/repositories"))["items"]
            rows = []
            for repo in repos[:50]:
                rid = quote(str(repo.get("id", "")), safe="")
                if topic == "branches":
                    refs = await self.paged(f"/{project_path}/_apis/git/repositories/{rid}/refs", {"filter": "heads/"})
                    rows.extend({"repository": repo.get("name"), "name": r.get("name", "").removeprefix("refs/heads/"), "objectId": r.get("objectId"), "isLocked": r.get("isLocked"), "isDefault": r.get("name") == repo.get("defaultBranch")} for r in refs["items"])
                else:
                    prs = await self.paged(f"/{project_path}/_apis/git/repositories/{rid}/pullrequests", {"searchCriteria.status": filters.get("status", "all")})
                    rows.extend({"repository": repo.get("name"), "id": p.get("pullRequestId"), "title": p.get("title"), "status": p.get("status"), "createdBy": p.get("createdBy", {}).get("displayName"), "source": p.get("sourceRefName"), "target": p.get("targetRefName"), "created": p.get("creationDate"), "url": p.get("url")} for p in prs["items"])
            return rows[:MAX_ITEMS]
        if topic == "policies":
            data = await self.paged(f"/{project_path}/_apis/policy/configurations"); return [{"id": p.get("id"), "type": p.get("type", {}).get("displayName"), "isEnabled": p.get("isEnabled"), "isBlocking": p.get("isBlocking"), "settings": p.get("settings")} for p in data["items"]]
        if topic in {"pipelines", "pipeline runs"}:
            pipelines = (await self.paged(f"/{project_path}/_apis/pipelines"))["items"]
            if topic == "pipelines":
                return [{"id": p.get("id"), "name": p.get("name"), "folder": p.get("folder"), "revision": p.get("revision"), "url": p.get("url")} for p in pipelines]
            rows = []
            for pipeline in pipelines[:50]:
                runs = await self.paged(f"/{project_path}/_apis/pipelines/{pipeline['id']}/runs", {"$top": 20}, cap=100)
                rows.extend({"pipeline": pipeline.get("name"), "id": r.get("id"), "state": r.get("state"), "result": r.get("result"), "created": r.get("createdDate"), "finished": r.get("finishedDate"), "url": r.get("_links", {}).get("web", {}).get("href")} for r in runs["items"])
            return rows[:MAX_ITEMS]
        if topic in {"library groups", "environments"}:
            if topic == "library groups":
                items = (await self.paged(f"/{project_path}/_apis/distributedtask/variablegroups"))["items"]
                rows = []
                for item in items:
                    row = {"name": item.get("name"), "id": item.get("id"), "type": item.get("type"), "description": item.get("description"), "variables": list((item.get("variables") or {}).keys()), "isShared": item.get("isShared")}
                    if filters.get("permissions"):
                        try:
                            access = await self.get(f"/{project_path}/_apis/pipelines/pipelinepermissions/variablegroup/{item.get('id')}", {"api-version": "7.1-preview.1"})
                            row["openAccess"] = access.get("allPipelines", {}).get("authorized", False)
                            row["authorizedPipelines"] = [p.get("id") for p in access.get("pipelines", []) if p.get("authorized")]
                        except AdoError as exc: row["accessError"] = str(exc)
                        try:
                            row["securityPermissions"] = await self.acl_rows(LIBRARY_NAMESPACE, f"Library/Project/{pid}/VariableGroup/{item.get('id')}")
                        except AdoError as exc: row["securityError"] = str(exc)
                    rows.append(row)
                return rows
            items = (await self.paged(f"/{project_path}/_apis/distributedtask/environments"))["items"]
            rows = []
            for env in items:
                row = {"name": env.get("name"), "id": env.get("id"), "description": env.get("description"), "resourceCount": env.get("resourceCount")}
                if filters.get("permissions"):
                    try:
                        access = await self.get(f"/{project_path}/_apis/pipelines/pipelinepermissions/environment/{env.get('id')}", {"api-version": "7.1-preview.1"})
                        row["openAccess"] = access.get("allPipelines", {}).get("authorized", False)
                        row["authorizedPipelines"] = [p.get("id") for p in access.get("pipelines", []) if p.get("authorized")]
                    except AdoError as exc: row["accessError"] = str(exc)
                rows.append(row)
            return rows
        if topic == "permissions":
            return await self.acl_rows(PROJECT_NAMESPACE, f"$PROJECT:vstfs:///Classification/TeamProject/{pid}")
        if topic == "work items":
            # Query template is fixed; user/model may only select one of these validated states.
            state = filters.get("state") if filters.get("state") in {"New", "Active", "Resolved", "Closed", "Removed"} else None
            where = f"[System.TeamProject] = '{project.replace(chr(39), chr(39) * 2)}'"
            if state: where += f" AND [System.State] = '{state}'"
            wiql = f"SELECT [System.Id] FROM WorkItems WHERE {where} ORDER BY [System.ChangedDate] DESC"
            result = await self.read_query(f"/{project_path}/_apis/wit/wiql", {"query": wiql}, {"$top": MAX_ITEMS})
            ids = [str(item["id"]) for item in result.get("workItems", [])[:MAX_ITEMS]]
            rows = []
            for start in range(0, len(ids), 200):
                batch = await self.get(f"/{project_path}/_apis/wit/workitems", {"ids": ",".join(ids[start:start + 200]), "fields": "System.Id,System.Title,System.WorkItemType,System.State,System.AssignedTo,System.CreatedDate,System.ChangedDate,System.Priority,System.IterationPath,System.AreaPath"})
                for item in batch.get("value", []):
                    f = item.get("fields", {})
                    rows.append({"id": item.get("id"), "type": f.get("System.WorkItemType"), "title": f.get("System.Title"), "state": f.get("System.State"), "assignedTo": (f.get("System.AssignedTo") or {}).get("displayName") if isinstance(f.get("System.AssignedTo"), dict) else f.get("System.AssignedTo"), "priority": f.get("Microsoft.VSTS.Common.Priority"), "created": f.get("System.CreatedDate"), "changed": f.get("System.ChangedDate"), "iteration": f.get("System.IterationPath"), "area": f.get("System.AreaPath"), "url": item.get("url")})
            return rows
        if topic in {"areas", "iterations"}:
            structure = "areas" if topic == "areas" else "iterations"
            data = await self.get(f"/{project_path}/_apis/wit/classificationnodes/{structure}", {"$depth": 10})
            rows = []
            def walk(node: dict, depth: int = 0):
                rows.append({"name": node.get("name"), "path": node.get("path"), "startDate": node.get("attributes", {}).get("startDate"), "finishDate": node.get("attributes", {}).get("finishDate"), "depth": depth})
                for child in node.get("children", []): walk(child, depth + 1)
            for child in data.get("children", []): walk(child)
            return rows[:MAX_ITEMS]
        if topic == "test plans":
            return (await self.paged(f"/{project_path}/_apis/testplan/plans", {"includePlanDetails": "true"}, cap=MAX_ITEMS))["items"]
        if topic == "test runs":
            rows = []
            for offset in range(0, MAX_ITEMS, PAGE_SIZE):
                page = await self.get(f"/{project_path}/_apis/test/runs", {"$skip": offset, "$top": PAGE_SIZE})
                items = page.get("value", []) if isinstance(page, dict) else page
                rows.extend(items[:PAGE_SIZE])
                if len(items) < PAGE_SIZE:
                    break
            return rows
        if topic in {"feeds", "packages"}:
            feeds = (await self.paged(f"/{project_path}/_apis/packaging/feeds", {"includeDeleted": "false"}))["items"]
            if topic == "feeds": return [{"name": x.get("name"), "id": x.get("id"), "description": x.get("description"), "visibility": x.get("visibility")} for x in feeds]
            rows = []
            for feed in feeds[:30]:
                pkgs = await self.paged(f"/{project_path}/_apis/packaging/feeds/{feed.get('id')}/packages", {"includeDeleted": "false"}, cap=100)
                rows.extend({"feed": feed.get("name"), "name": p.get("name"), "protocol": p.get("protocolType"), "versions": len(p.get("versions", [])), "isDeleted": p.get("isDeleted")} for p in pkgs["items"])
            return rows[:MAX_ITEMS]
        raise AdoError("I couldn't match that request to a supported read-only query.")


TOPICS = {
    "project details": ("project details", "project info", "project settings", "project configuration"),
    "projects": ("project list", "projects", "list projects"),
    "teams": ("team", "teams", "team members", "members of the team"),
    "project groups": ("permission groups", "project groups", "security groups", "groups and members"),
    "pipeline settings": ("pipeline project settings", "pipeline settings", "pipeline configuration"),
    "repositories": ("repository", "repositories", "repo", "repos"),
    "branches": ("branch", "branches", "stale branch", "refs"),
    "pull requests": ("pull request", "pull requests", "prs"),
    "policies": ("branch protection", "repository policy", "repository policies", "policy", "policies"),
    "pipelines": ("pipeline definition", "pipeline definitions", "pipelines", "pipeline", "pipeline list"),
    "pipeline runs": ("pipeline runs", "builds", "failed pipeline", "pipeline history", "pipeline run"),
    "work items": ("work item", "work items", "backlog", "bugs", "user stories", "tasks", "aging work"),
    "areas": ("area paths", "areas"), "iterations": ("iteration", "iterations", "sprints"),
    "test plans": ("test plan", "test plans"), "test runs": ("test run", "test runs", "test results"),
    "feeds": ("artifact feed", "artifact feeds", "feeds"), "packages": ("packages", "package inventory"),
    "agent pools": ("agent pool", "agent pools", "pool"),
    "library groups": ("library group", "variable group", "variable groups"),
    "environments": ("environment", "environments"),
    "permissions": ("permission", "permissions", "security", "access review"),
    "project overview": ("project overview", "overview of project", "project snapshot", "project inventory"),
    "release readiness": ("release readiness", "release ready", "ready to release", "release audit"),
    "delivery flow": ("delivery health", "delivery flow", "flow health", "engineering health"),
}


def detect_topic(prompt: str) -> str | None:
    text = prompt.lower()
    if "access review" in text or "permission audit" in text: return "access review"
    if "release readiness" in text or "ready to release" in text or "release audit" in text: return "release readiness"
    if "project overview" in text or "project snapshot" in text or "project inventory" in text: return "project overview"
    if "delivery health" in text or "delivery flow" in text or "flow health" in text: return "delivery flow"
    matches = [(len(term), topic) for topic, terms in TOPICS.items() for term in terms if term in text]
    return max(matches)[1] if matches else None


COMPOSITES = {"project overview", "release readiness", "delivery flow", "access review"}
PROJECT_TOPICS = set(TOPICS) - {"projects"}


def requires_project(topic: str) -> bool:
    return (topic in PROJECT_TOPICS and topic != "agent pools") or topic in COMPOSITES
