from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agents.state import AgentState
from agents.nodes.topic_research import topic_agent_node, research_agent_node
from agents.nodes.content_gen import writer_agent_node, image_agent_node
from agents.nodes.synthesis_scheduler import synthesis_qa_agent_node, scheduler_agent_node

def create_social_media_graph():
    # Initialize the graph
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("topic_agent", topic_agent_node)
    workflow.add_node("research_agent", research_agent_node)
    workflow.add_node("writer_agent", writer_agent_node)
    workflow.add_node("image_agent", image_agent_node)
    workflow.add_node("synthesis_qa_agent", synthesis_qa_agent_node)
    workflow.add_node("scheduler_agent", scheduler_agent_node)

    # Define Edges
    workflow.set_entry_point("topic_agent")
    
    workflow.add_edge("topic_agent", "research_agent")
    workflow.add_edge("research_agent", "writer_agent")
    
    def check_writer_progress(state: AgentState) -> Literal["writer_agent", "image_agent"]:
        approved_platforms = state.get("approved_platforms") or []
        platforms_written = state.get("platforms_written_this_round") or []
        platforms_to_write = [p for p in state.get('platforms', []) if p not in approved_platforms and p not in platforms_written]
        
        if len(platforms_to_write) > 0:
            return "writer_agent"
        return "image_agent"

    workflow.add_conditional_edges(
        "writer_agent",
        check_writer_progress,
        {
            "writer_agent": "writer_agent",
            "image_agent": "image_agent"
        }
    )
    
    workflow.add_edge("image_agent", "synthesis_qa_agent")
    
    def check_qa_result(state: AgentState) -> Literal["writer_agent", "scheduler_agent"]:
        if state.get("is_brand_voice_aligned") is False and state.get("retry_count", 0) < 3:
            return "writer_agent"
        return "scheduler_agent"

    workflow.add_conditional_edges(
        "synthesis_qa_agent",
        check_qa_result,
        {
            "writer_agent": "writer_agent",
            "scheduler_agent": "scheduler_agent"
        }
    )

    def decide_after_review(state: AgentState) -> str:
        if state.get("status") == "REJECTED":
            return "writer_agent"
        return "end"

    workflow.add_conditional_edges(
        "scheduler_agent",
        decide_after_review,
        {
            "writer_agent": "writer_agent",
            "end": END
        }
    )

    # Checkpointer for state persistence
    memory = MemorySaver()
    
    # Use interrupt_before to stop the graph EXACTLY at the review node
    app = workflow.compile(
        checkpointer=memory,
        interrupt_before=["scheduler_agent"] 
    )
    
    return app
