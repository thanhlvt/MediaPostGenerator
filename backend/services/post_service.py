import uuid
import asyncio
import logging
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from core.db import save_post_to_db, update_post_status, get_post_by_id, get_all_posts
from agents.nodes.topic_research import generate_sub_topics
from services.workflow_service import run_graph_task, graph_app
from memory.vector_db import add_post_to_memory, add_feedback_to_memory

logger = logging.getLogger(__name__)

async def start_single_generation(topic: str, niche: str, platforms: List[str]):
    """
    Business logic for starting a single post generation.
    """
    thread_id = str(uuid.uuid4())
    initial_state = {
        "topic": topic,
        "niche": niche,
        "platforms": platforms,
        "status": "START",
        "retry_count": {},
        "error_count": 0,
        "review_history": []
    }
    
    # Fire and forget (will wait for SSE in background)
    asyncio.create_task(run_graph_task(thread_id, initial_state, True))
    return thread_id

async def start_batch_generation(topic: str, niche: str, platforms: List[str], quantity: int):
    """
    Business logic for starting batch generation.
    """
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")
        
    # Generate sub-topics for the entire batch
    sub_topics = generate_sub_topics(topic, niche, quantity)
    
    thread_ids = []
    for sub_topic in sub_topics:
        thread_id = str(uuid.uuid4())
        thread_ids.append(thread_id)
        
        initial_state = {
            "topic": sub_topic,
            "niche": niche,
            "platforms": platforms,
            "status": "START",
            "retry_count": {},
            "error_count": 0,
            "review_history": []
        }
        
        # Batch generation does NOT wait for SSE
        asyncio.create_task(run_graph_task(thread_id, initial_state, False))
        
        # Small delay between spawning tasks
        await asyncio.sleep(0.5)
        
    return thread_ids

async def submit_post_review(thread_id: str, action: str, feedback: Optional[str] = None):
    """
    Business logic for human-in-the-loop review.
    """
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = await graph_app.aget_state(config)
    
    state = {}
    if state_snapshot and state_snapshot.values:
        state = state_snapshot.values
    else:
        # Rehydrate from DB if graph state is lost
        db_post = get_post_by_id(thread_id)
        if not db_post:
            raise HTTPException(status_code=404, detail="Post not found.")
        
        state = {
            "topic": db_post.topic,
            "niche": db_post.niche,
            "selected_title": db_post.topic,
            "research_brief": db_post.research_brief,
            "post_contents": db_post.post_contents or {},
            "image_url": db_post.image_url,
            "image_prompt": db_post.image_prompt,
            "status": db_post.status,
            "platforms": list((db_post.post_contents or {}).keys()) or ["TikTok", "Facebook", "Twitter"],
            "error_count": 0,
            "retry_count": {},
            "review_history": []
        }
        await graph_app.aupdate_state(config, state, as_node="scheduler_agent")

    new_status = "APPROVED" if action.upper() == "APPROVE" else "REJECTED"
    
    # Save to memory if approved
    if new_status == "APPROVED":
        post_contents = state.get("post_contents", {})
        topic = state.get("selected_title", "Unknown Topic")
        niche = state.get("niche", "Unknown Niche")
        
        for platform, content in post_contents.items():
            post_id = f"{thread_id}_{platform}"
            metadata = {"platform": platform, "topic": topic, "niche": niche}
            try:
                add_post_to_memory(post_id, content, metadata)
            except Exception as e:
                logger.error(f"Failed to save post to memory: {e}")
                
        update_post_status(thread_id, "APPROVED")
                
    elif new_status == "REJECTED" and feedback:
        topic = state.get("selected_title", "Unknown Topic")
        niche = state.get("niche", "Unknown Niche")
        metadata = {"topic": topic, "niche": niche}
        try:
            add_feedback_to_memory(str(uuid.uuid4()), feedback, metadata)
        except Exception as e:
            logger.error(f"Failed to save feedback to memory: {e}")
        
        update_post_status(thread_id, "REJECTED")
    
    update_dict = {"status": new_status, "feedback": feedback}
    if new_status == "REJECTED":
        update_dict["approved_platforms"] = []
        update_dict["platform_feedbacks"] = {}
        update_dict["platforms_written_this_round"] = []

    await graph_app.aupdate_state(config, update_dict, as_node="scheduler_agent")
    
    # Resume the graph
    asyncio.create_task(run_resume_workflow(thread_id, config))
    
    return new_status

async def run_resume_workflow(thread_id: str, config: dict):
    """Helper to resume the graph after review"""
    try:
        async for event in graph_app.astream(None, config=config):
            # event is a dict: {node_name: node_output}
            for node_output in event.values():
                if isinstance(node_output, dict) and "status" in node_output:
                    update_post_status(thread_id, node_output["status"])
             
        state_snapshot = await graph_app.aget_state(config)
        if state_snapshot and state_snapshot.values:
            state = state_snapshot.values
            current_status = state.get("status", "PENDING_REVIEW")

            # If interrupted before scheduler_agent, writing is done → ready for review
            if state_snapshot.next and "scheduler_agent" in state_snapshot.next:
                current_status = "PENDING_REVIEW"

            update_post_status(thread_id, current_status)

            if current_status == "PENDING_REVIEW":
                save_post_to_db(
                    thread_id=thread_id,
                    topic=state.get("selected_title", ""),
                    niche=state.get("niche", ""),
                    research_brief=state.get("research_brief", ""),
                    post_contents=state.get("post_contents", {}),
                    image_url=state.get("image_url"),
                    image_prompt=state.get("image_prompt"),
                    status=current_status
                )
        from core.events import event_dispatcher
        await event_dispatcher.end_stream(thread_id)
    except Exception as e:
        logger.error(f"Graph resumption failed for {thread_id}: {e}")
        from core.events import event_dispatcher
        await event_dispatcher.end_stream(thread_id)
