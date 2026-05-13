import asyncio
import uuid
import logging
from typing import Optional
from agents.orchestrator import create_social_media_graph
from core.db import save_post_to_db, update_post_status
from core.events import event_dispatcher

logger = logging.getLogger(__name__)

# Initialize the graph
graph_app = create_social_media_graph()

# Global semaphore to limit concurrent AI jobs (max 10 at a time)
MAX_CONCURRENT_JOBS = 10
job_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

async def run_graph_task(thread_id: str, initial_state: dict, wait_for_sse: bool = True):
    """
    Core business logic for running the LangGraph workflow.
    Handles DB initialization, status syncing, retries, and semaphore management.
    """
    config = {"configurable": {"thread_id": thread_id}}
    max_retries = 3
    
    # 1. Save initial record to DB IMMEDIATELY
    try:
        save_post_to_db(
            thread_id=thread_id,
            topic=initial_state.get("topic", ""),
            niche=initial_state.get("niche", ""),
            research_brief="",
            post_contents={},
            image_url=None,
            image_prompt=None
        )
        update_post_status(thread_id, "START")
    except Exception as e:
        logger.error(f"Failed to create initial DB record for {thread_id}: {e}")
        return

    for attempt in range(max_retries):
        try:
            # 2. Limit concurrent AI execution using semaphore
            async with job_semaphore:
                if wait_for_sse:
                    await event_dispatcher.wait_for_subscriber(thread_id)
                
                async for event in graph_app.astream(initial_state, config=config):
                    # event is a dict: {node_name: node_output}
                    for node_output in event.values():
                        if isinstance(node_output, dict) and "status" in node_output:
                            new_status = node_output["status"]
                            update_post_status(thread_id, new_status)
                    
                # Final snapshot for data persistence
                state_snapshot = await graph_app.aget_state(config)
                if state_snapshot and state_snapshot.values:
                    state = state_snapshot.values
                    # If the graph is interrupted before scheduler_agent, it means it's waiting for review
                    is_waiting_for_review = state_snapshot.next and "scheduler_agent" in state_snapshot.next
                    current_status = "PENDING_REVIEW" if is_waiting_for_review else state.get("status", "PENDING_REVIEW")
                    
                    # Force update final status in DB
                    update_post_status(thread_id, current_status)
                    
                    if current_status == "PENDING_REVIEW" or (state_snapshot.next and "scheduler_agent" in state_snapshot.next):
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
            
            await event_dispatcher.end_stream(thread_id)
            return
            
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed for {thread_id}: {e}")
            if attempt < max_retries - 1:
                update_post_status(thread_id, f"RETRYING ({attempt+1})")
                await asyncio.sleep(5)
                continue
            
            # Final failure handling
            try:
                update_post_status(thread_id, "ERROR")
                await graph_app.aupdate_state(config, {"status": "ERROR", "feedback": f"System Error: {str(e)}"})
                await event_dispatcher.publish(thread_id, {"type": "error", "message": str(e)})
            except:
                pass
            await event_dispatcher.end_stream(thread_id)
