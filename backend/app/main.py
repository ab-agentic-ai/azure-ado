from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(body: ChatRequest):
    topic = detect_topic(body.prompt)
    if topic is None:
        return {"answer": "I can inspect projects, permissions, repository policies, repositories, agent pools, library groups, and environments.", "suggestions": list(TOPICS)}
    if requires_project(topic) and not body.project:
        return {"answer": f"Enter a project name so I can look up {topic}.", "suggestions": ["projects"]}
    try:
        client = AdoClient(body.organization, body.auth.mode, body.auth.pat)
        data = await client.inspect(topic, body.project, body.prompt)
    except AdoError as exc:
        return {"answer": str(exc), "error": True}
    label = f" in {body.project}" if body.project and requires_project(topic) else ""
    if not data:
        answer = f"No {topic} found{label}."
    else:
        answer = f"Found {len(data)} {topic}{label}."
    return {"answer": answer, "data": data[:200], "truncated": len(data) > 200}
