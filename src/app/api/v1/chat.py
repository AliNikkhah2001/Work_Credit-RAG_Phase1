# ============================================================
# RAG Agent Platform — OpenAI-Compatible Chat Endpoint
# ============================================================

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import httpx

from app.core.config import settings
from app.core.secrets import get_openai_api_key, redact_sensitive_data
from app.services.agent.service import get_agent_service

router = APIRouter()


# ─── Request/Response Models ──────────────────────────────────
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "gpt-4o-mini"
    messages: List[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2048


@router.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest, req: Request):
    """
    OpenAI-compatible chat completion endpoint.
    Uses LangGraph agent for intelligent responses.
    """
    # Extract the last user message
    user_query = None
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_query = msg.content
            break
    
    if not user_query:
        raise HTTPException(
            status_code=400,
            detail="No user message found in request."
        )

    # If streaming is requested, use the agent with streaming
    if request.stream:
        from fastapi.responses import StreamingResponse
        
        agent_service = get_agent_service()
        
        async def generate():
            async for chunk in agent_service.stream_chat(
                query=user_query,
                conversation_id=str(req.client.host) if req.client else "anonymous",
                stream=True,
            ):
                yield chunk
        
        return StreamingResponse(
            generate(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    
    # Non-streaming mode: use OpenAI proxy
    try:
        api_key = get_openai_api_key()
    except ValueError as e:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API key not configured."
        )

    model_to_use = request.model or settings.OPENAI_MODEL or "gpt-4o-mini"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    openai_payload = {
        "model": model_to_use,
        "messages": [msg.dict() for msg in request.messages],
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.OPENAI_BASE_URL}/chat/completions",
                headers=headers,
                json=openai_payload,
            )

        if response.status_code != 200:
            error_text = redact_sensitive_data(response.text)
            if "model_not_found" in error_text:
                raise HTTPException(
                    status_code=400,
                    detail=f"Model '{model_to_use}' not found or not accessible."
                )
            raise HTTPException(
                status_code=response.status_code,
                detail=f"OpenAI API error: {error_text}"
            )

        return response.json()

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="OpenAI API request timed out"
        )
    except Exception as e:
        error_msg = redact_sensitive_data(str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error calling OpenAI API: {error_msg}"
        )
