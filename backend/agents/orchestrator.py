from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Send

from agents.state import AgentState
from agents.nodes.topic_research import topic_agent_node, research_agent_node
from agents.nodes.content_gen import writer_agent_node, image_agent_node
from agents.nodes.synthesis_scheduler import platform_qa_agent_node, scheduler_agent_node

def create_social_media_graph():
    # --- Define Platform Sub-graph (The Worker) ---
    branch_builder = StateGraph(AgentState)
    branch_builder.add_node("writer", writer_agent_node)
    branch_builder.add_node("qa", platform_qa_agent_node)
    
    branch_builder.set_entry_point("writer")
    branch_builder.add_edge("writer", "qa")
    
    def check_platform_qa(state: AgentState) -> Literal["writer", END]:
        platform = state.get("current_platform")
        retries = state.get("retry_count", {}).get(platform, 0)
        if not state.get("is_brand_voice_aligned") and retries < 3:
            return "writer"
        return END

    branch_builder.add_conditional_edges("qa", check_platform_qa, {"writer": "writer", END: END})
    platform_branch = branch_builder.compile()

    # --- Define Main Graph ---
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("topic_agent", topic_agent_node)
    workflow.add_node("research_agent", research_agent_node)
    workflow.add_node("platform_branch", platform_branch) # Add the sub-graph as a node
    workflow.add_node("image_agent", image_agent_node)
    workflow.add_node("scheduler_agent", scheduler_agent_node)
    workflow.add_node("fan_out", lambda state: state)

    # Define Edges
    workflow.set_entry_point("topic_agent")
    workflow.add_edge("topic_agent", "research_agent")
    workflow.add_edge("research_agent", "fan_out")
    
    def initiate_parallel_processing(state: AgentState):
        platforms = state.get("platforms", [])
        approved = state.get("approved_platforms") or []
        to_process = [p for p in platforms if p not in approved]
        
        if not to_process:
            return "image_agent"
            
        # Send to the sub-graph node
        return [Send("platform_branch", {**state, "current_platform": p}) for p in to_process]

    workflow.add_conditional_edges(
        "fan_out", 
        initiate_parallel_processing,
        ["platform_branch", "image_agent"]
    )
    
    # Fan-in (Reduction): Connect the branches to the join node.
    # LangGraph will wait for all parallel branches to finish before running image_agent.
    workflow.add_edge("platform_branch", "image_agent")
    workflow.add_edge("image_agent", "scheduler_agent")

    def decide_after_review(state: AgentState) -> str:
        if state.get("status") == "REJECTED":
            return "research_agent"
        return END

    workflow.add_conditional_edges(
        "scheduler_agent",
        decide_after_review,
        {
            "research_agent": "research_agent",
            END: END
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
