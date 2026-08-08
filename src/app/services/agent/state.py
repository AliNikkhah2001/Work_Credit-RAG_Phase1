# ============================================================
# RAG Agent Platform — LangGraph Agent State
# ============================================================

from typing import List, Optional, Dict, Any, Annotated, TypedDict
from langgraph.graph import add_messages


class AgentState(TypedDict):
    """State for the LangGraph agent."""
    messages: Annotated[List[Dict[str, Any]], add_messages]
    current_query: str
    context: Optional[str]
    reasoning_trace: List[str]
    iteration: int
    max_iterations: int
    confidence_score: Optional[float]
    final_response: Optional[str]
