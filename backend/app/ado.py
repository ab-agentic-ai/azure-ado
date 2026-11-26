"""Read-only Azure DevOps REST API access."""

from __future__ import annotations

import base64
import os
from typing import Any
from urllib.parse import quote

import httpx
from azure.identity import AzureCliCredential

API_VERSION = "7.1"
RESOURCE = "499b84ac-1321-427f-aa17-267ca6975798"
PROJECT_NAMESPACE = "52d39943-cb85-4d7f-8fa8-c6baac873819"
LIBRARY_NAMESPACE = "b7e84409-6553-448a-bbb2-af228e07cbeb"


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

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        params = {"api-version": API_VERSION, **(params or {})}
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.get(self.base + path, params=params, headers=self.headers)
        if response.status_code == 401:
            raise AdoError("Azure DevOps rejected the credentials. Check the PAT or refresh `az login`.")
        if response.status_code == 403:
            raise AdoError("Your Azure DevOps identity does not have permission to read this resource.")
        if response.status_code == 404:
            raise AdoError("The requested Azure DevOps resource was not found. Check the organization and project name.")
        if response.is_error:
            raise AdoError(f"Azure DevOps returned HTTP {response.status_code}: {response.text[:300]}")
        return response.json()

    async def projects(self) -> list[dict[str, Any]]:
        return (await self.get("/_apis/projects", {"$top": 1000})).get("value", [])

    async def project_id(self, project: str) -> str:
        data = await self.get(f"/_apis/projects/{quote(project, safe='')}")
        return data["id"]

    async def acl_rows(self, namespace_id: str, token: str) -> list[dict[str, Any]]:
        namespace = await self.get(f"/_apis/securitynamespaces/{namespace_id}")
        acl_data = await self.get(f"/_apis/accesscontrollists/{namespace_id}", {
            "token": token, "includeExtendedInfo": "true", "recurse": "false",
        })
        actions = namespace.get("actions", [])
        rows = []
        for acl in acl_data.get("value", []):
            for descriptor, ace in acl.get("acesDictionary", {}).items():
                allowed, denied = int(ace.get("allow", 0)), int(ace.get("deny", 0))
                rows.append({
                    "descriptor": descriptor,
                    "allow": [a.get("displayName") or a.get("name") for a in actions if allowed & int(a.get("bit", 0))],
                    "deny": [a.get("displayName") or a.get("name") for a in actions if denied & int(a.get("bit", 0))],
                })
        return rows

    async def inspect(self, topic: str, project: str | None, prompt: str = "") -> list[dict[str, Any]]:
        if topic == "projects":
            items = await self.projects()
            return [{"name": x.get("name"), "state": x.get("state"), "visibility": x.get("visibility"), "id": x.get("id")} for x in items]

        pid = await self.project_id(project) if project else None
        if topic == "repositories":
            data = await self.get(f"/{quote(project or '', safe='')}/_apis/git/repositories")
            return [{"name": x.get("name"), "defaultBranch": x.get("defaultBranch"), "remoteUrl": x.get("remoteUrl")} for x in data.get("value", [])]
        if topic == "policies":
            data = await self.get(f"/{quote(project or '', safe='')}/_apis/policy/configurations", {"$top": 1000})
            return [{"type": x.get("type", {}).get("displayName"), "isEnabled": x.get("isEnabled"), "isBlocking": x.get("isBlocking"), "settings": x.get("settings")} for x in data.get("value", [])]
        if topic == "agent pools":
            data = await self.get("/_apis/distributedtask/pools", {"poolType": "automation"})
            return [{"name": x.get("name"), "isHosted": x.get("isHosted"), "poolType": x.get("poolType"), "size": x.get("size")} for x in data.get("value", [])]
        if topic == "library groups":
            data = await self.get(f"/{quote(project or '', safe='')}/_apis/distributedtask/variablegroups", {"$top": 1000})
            groups = data.get("value", [])
            if "permission" in prompt.lower() or "security" in prompt.lower():
                rows = []
                for group in groups:
                    access = await self.get(f"/{quote(project or '', safe='')}/_apis/pipelines/pipelinepermissions/variablegroup/{group.get('id')}", {"api-version": "7.1-preview.1"})
                    library_token = f"Library/Project/{pid}/VariableGroup/{group.get('id')}"
                    try:
                        security = await self.acl_rows(LIBRARY_NAMESPACE, library_token)
                    except AdoError as exc:
                        security = [{"error": str(exc)}]
                    rows.append({"name": group.get("name"), "id": group.get("id"), "openAccess": access.get("allPipelines", {}).get("authorized", False), "authorizedPipelines": [p.get("id") for p in access.get("pipelines", []) if p.get("authorized")], "securityPermissions": security})
                return rows
            return [{"name": x.get("name"), "type": x.get("type"), "description": x.get("description"), "variables": list((x.get("variables") or {}).keys()), "isShared": x.get("isShared")} for x in groups]
        if topic == "environments":
            data = await self.get(f"/{quote(project or '', safe='')}/_apis/distributedtask/environments", {"$top": 1000})
            environments = data.get("value", [])
            if "permission" in prompt.lower() or "security" in prompt.lower():
                rows = []
                for env in environments:
                    access = await self.get(f"/{quote(project or '', safe='')}/_apis/pipelines/pipelinepermissions/environment/{env.get('id')}", {"api-version": "7.1-preview.1"})
                    rows.append({"name": env.get("name"), "id": env.get("id"), "openAccess": access.get("allPipelines", {}).get("authorized", False), "authorizedPipelines": [p.get("id") for p in access.get("pipelines", []) if p.get("authorized")]})
                return rows
            return [{"name": x.get("name"), "description": x.get("description"), "resourceCount": x.get("resourceCount")} for x in environments]
        if topic == "permissions":
            return await self.acl_rows(PROJECT_NAMESPACE, f"$PROJECT:vstfs:///Classification/TeamProject/{pid}")
        raise AdoError("I couldn't match that request to a supported read-only query.")


TOPICS = {
    "policies": ("branch protection", "repository policy", "repository policies", "policy", "policies"),
    "library groups": ("library group", "variable group", "variable groups"),
    "environments": ("environment", "environments"),
    "agent pools": ("agent pool", "agent pools", "pool"),
    "repositories": ("repository", "repositories", "repo", "repos"),
    "permissions": ("permission", "permissions", "security", "access"),
    "projects": ("project", "projects"),
}


def detect_topic(prompt: str) -> str | None:
    text = prompt.lower()
    matches = [(len(term), topic) for topic, terms in TOPICS.items() for term in terms if term in text]
    return max(matches)[1] if matches else None


def requires_project(topic: str) -> bool:
    return topic in {"permissions", "policies", "repositories", "library groups", "environments"}
