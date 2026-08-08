# ============================================================
# RAG Agent Platform — LangGraph Agent Graph
# ============================================================

import json
from typing import Dict, Any, List, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.secrets import get_openai_api_key
from app.services.agent.state import AgentState
from app.services.retrieval.service import get_retrieval_service
from app.db.session import SessionLocal


# ─── LLM Setup ──────────────────────────────────────────────────
def get_llm():
    """Get the OpenAI LLM instance."""
    api_key = get_openai_api_key()
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=api_key,
        base_url=settings.OPENAI_BASE_URL,
        temperature=0.7,
    )


# ─── Node Functions ────────────────────────────────────────────

def planner_node(state: AgentState) -> Dict[str, Any]:
    """Plan the task and decompose the query."""
    messages = state.get("messages", [])
    query = messages[-1].content if messages else ""

    plan = f"Analyzing query: {query}"
    
    return {
        "current_query": query,
        "reasoning_trace": state.get("reasoning_trace", []) + [plan],
        "iteration": state.get("iteration", 0) + 1,
    }


async def retriever_node(state: AgentState) -> Dict[str, Any]:
    """Retrieve relevant context from the vector database."""
    query = state.get("current_query", "")
    
    # Get database session
    db = SessionLocal()
    try:
        retrieval_service = get_retrieval_service(db)
        results = await retrieval_service.search(query, top_k=5, min_score=0.3)
        context = await retrieval_service.format_context(results)
        
        return {
            "context": context,
            "reasoning_trace": state.get("reasoning_trace", []) + [
                f"Retrieved {len(results)} relevant chunks"
            ],
        }
    finally:
        db.close()


def reasoner_node(state: AgentState) -> Dict[str, Any]:
    """Generate a response using the LLM with the retrieved context."""
    llm = get_llm()
    query = state.get("current_query", "")
    context = state.get("context", "")
    messages = state.get("messages", [])
    
    prompt = f"""You are a helpful RAG assistant. Use the following context to answer the user's question.

Context:
{context}

User question: {query}

Instructions:
1. Answer based ONLY on the provided context.
2. If the context doesn't contain the answer, say "I don't have enough information to answer that."
3. Cite which document the information comes from when possible.
4. Be concise and clear.
"""
    
    response = llm.invoke(prompt)
    
    return {
        "messages": [AIMessage(content=response.content)],
        "reasoning_trace": state.get("reasoning_trace", []) + ["Generated response using retrieved context"]
    }


def verifier_node(state: AgentState) -> Dict[str, Any]:
    """Verify the response quality."""
    messages = state.get("messages", [])
    response = messages[-1].content if messages else ""
    
    # Confidence score based on whether the response contains "don't have enough information"
    confidence_score = 0.8
    if "don't have enough information" in response.lower():
        confidence_score = 0.3
    
    return {
        "confidence_score": confidence_score,
        "final_response": response if confidence_score > 0.3 else "I need more context to give a confident answer."
    }


def should_continue(state: AgentState) -> str:
    """Determine if the agent should continue or end."""
    confidence = state.get("confidence_score", 0)
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 2)
    
    if confidence > 0.7:
        return "synthesize"
    elif iteration >= max_iterations:
        return "synthesize"
    else:
        return "reasoner"


def synthesizer_node(state: AgentState) -> Dict[str, Any]:
    """Synthesize the final response."""
    final_response = state.get("final_response", "No response generated.")
    
    return {
        "messages": [AIMessage(content=final_response)],
        "final_response": final_response,
    }


# ─── Build the Graph ───────────────────────────────────────────

def build_agent_graph():
    """Build and compile the LangGraph agent."""
    builder = StateGraph(AgentState)

    builder.add_node("planner", planner_node)
    builder.add_node("retriever", retriever_node)  # Now async!
    builder.add_node("reasoner", reasoner_node)
    builder.add_node("verifier", verifier_node)
    builder.add_node("synthesizer", synthesizer_node)

    builder.set_entry_point("planner")
    builder.add_edge("planner", "retriever")
    builder.add_edge("retriever", "reasoner")
    builder.add_edge("reasoner", "verifier")
    
    builder.add_conditional_edges(
        "verifier",
        should_continue,
        {
            "reasoner": "reasoner",
            "synthesize": "synthesizer",
        }
    )
    builder.add_edge("synthesizer", END)

    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)
    
    return graph


# ─── Singleton graph instance ──────────────────────────────────
_agent_graph = None

def get_agent_graph():
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_agent_graph()
    return _agent_graph
