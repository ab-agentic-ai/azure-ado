from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from .ado import AdoClient, AdoError, TOPICS, detect_topic, requires_project

app = FastAPI(title="ADO-MCP", version="0.1.0", description="Read-only Azure DevOps compliance assistant")
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type"], allow_credentials=True)


class Auth(BaseModel):
    mode: Literal["pat", "sso"] = "pat"
    pat: str | None = Field(default=None, repr=False)


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    organization: str = Field(min_length=1, max_length=200)
    project: str | None = Field(default=None, max_length=200)
    auth: Auth


class CompletionRequest(BaseModel):
    model: str = Field(default="ado-readonly", min_length=1, max_length=200)
    messages: list[dict] = Field(min_length=1, max_length=100)
    stream: bool = False


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(body: ChatRequest):
    return await query_ado(body.prompt, body.organization, body.project, body.auth.mode, body.auth.pat)


async def query_ado(prompt: str, organization: str, project: str | None, mode: str, pat: str | None):
    topic = detect_topic(prompt)
    if topic is None:
        return {"answer": "I can inspect projects, permissions, repository policies, repositories, agent pools, library groups, and environments.", "suggestions": list(TOPICS)}
    if requires_project(topic) and not project:
        return {"answer": f"Enter a project name so I can look up {topic}.", "suggestions": ["projects"]}
    try:
        client = AdoClient(organization, mode, pat)
        data = await client.inspect(topic, project, prompt)
    except AdoError as exc:
        return {"answer": str(exc), "error": True}
    label = f" in {project}" if project and requires_project(topic) else ""
    if not data:
        answer = f"No {topic} found{label}."
    else:
        answer = f"Found {len(data)} {topic}{label}."
    return {"answer": answer, "data": data[:200], "truncated": len(data) > 200}


@app.get("/v1/models")
async def models():
    return {"object": "list", "data": [{"id": "ado-readonly", "object": "model", "created": 0, "owned_by": "local"}]}


def text_content(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(str(part.get("text", "")) for part in value if isinstance(part, dict) and part.get("type") == "text").strip()
    return ""


def project_from_prompt(prompt: str) -> tuple[str | None, str]:
    match = re.search(r"\bproject\s*[:=]\s*[\"']?([^\"'\n,;]+)", prompt, re.IGNORECASE)
    if not match:
        match = re.search(r"\bin\s+(?:the\s+)?project\s+[\"']?(.+?)[\"']?(?:\s*[?.!,;]|$)", prompt, re.IGNORECASE)
    if not match:
        return None, prompt
    project = match.group(1).strip()
    cleaned = (prompt[:match.start()] + prompt[match.end():]).strip(" \t.,;:-")
    return (project or None), (cleaned or prompt)


def completion_content(result: dict) -> str:
    content = result.get("answer", "")
    if result.get("data"):
        content += "\n\n```json\n" + json.dumps(result["data"], ensure_ascii=False, indent=2) + "\n```"
        if result.get("truncated"):
            content += "\n\nResults were limited to the first 200 items."
    elif result.get("suggestions"):
        content += "\n\nSupported query types: " + ", ".join(result["suggestions"]) + "."
    return content


def completion_chunk(completion_id: str, created: int, model: str, delta: dict, finish_reason=None) -> str:
    payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(body: CompletionRequest, authorization: str | None = Header(default=None)):
    scheme, _, credential = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not credential.strip():
        raise HTTPException(status_code=401, detail="Provide your Azure DevOps PAT in the LibreChat endpoint settings.")

    user_message = next((message for message in reversed(body.messages) if message.get("role") == "user"), None)
    prompt = text_content(user_message.get("content")) if user_message else ""
    if not prompt:
        raise HTTPException(status_code=400, detail="The latest user message must contain text.")
    if len(prompt) > 4000:
        raise HTTPException(status_code=400, detail="Keep the latest user message under 4000 characters.")

    extracted_project, query = project_from_prompt(prompt)
    project = extracted_project or os.getenv("ADO_DEFAULT_PROJECT") or None
    organization = os.getenv("ADO_ORGANIZATION", "ab-org")
    result = await query_ado(query, organization, project, "pat", credential.strip())
    content = completion_content(result)
    completion_id = "chatcmpl-" + uuid.uuid4().hex
    created = int(time.time())

    if body.stream:
        async def events():
            yield completion_chunk(completion_id, created, body.model, {"role": "assistant"})
            yield completion_chunk(completion_id, created, body.model, {"content": content})
            yield completion_chunk(completion_id, created, body.model, {}, "stop")
            yield "data: [DONE]\n\n"
        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": body.model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
    }
