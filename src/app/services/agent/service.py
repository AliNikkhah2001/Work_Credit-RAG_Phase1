# ============================================================
# RAG Agent Platform — Agent Service
# ============================================================

import json
from typing import AsyncGenerator, Dict, Any, List

from langchain_core.messages import HumanMessage, AIMessage

from app.services.agent.graph import get_agent_graph
from app.services.agent.state import AgentState


class AgentService:
    """Service for interacting with the LangGraph agent."""

    def __init__(self):
        self.graph = get_agent_graph()

    async def stream_chat(
        self,
        query: str,
        conversation_id: str,
        stream: bool = True,
    ) -> AsyncGenerator[str, None]:
        """
        Process a chat query through the LangGraph agent.
        Yields NDJSON messages for streaming.
        """
        # Prepare initial state
        initial_state: AgentState = {
            "messages": [HumanMessage(content=query)],
            "current_query": query,
            "context": None,
            "reasoning_trace": [],
            "iteration": 0,
            "max_iterations": 2,
            "confidence_score": None,
            "final_response": None,
        }

        # Configuration for the graph execution
        config = {
            "configurable": {
                "thread_id": conversation_id,
            }
        }

        # Run the graph
        final_state = None
        async for event in self.graph.astream(
            initial_state,
            config=config,
            stream_mode="values",
        ):
            final_state = event
            
            # Extract response if available
            messages = event.get("messages", [])
            if messages and isinstance(messages[-1], AIMessage):
                response = messages[-1].content
                
                # Yield the thinking trace
                trace = event.get("reasoning_trace", [])
                if trace:
                    yield json.dumps({
                        "type": "thinking",
                        "data": trace[-1] if trace else "",
                    }) + "\n"
                
                # Yield the token (full response for now)
                yield json.dumps({
                    "type": "token",
                    "data": response,
                }) + "\n"

        # Done
        if final_state and final_state.get("final_response"):
            yield json.dumps({
                "type": "done",
                "data": final_state.get("final_response"),
            }) + "\n"


# ─── Singleton service ─────────────────────────────────────────
_agent_service = None

def get_agent_service():
    """Get or create the agent service singleton."""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
