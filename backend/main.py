from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from fastapi.responses import StreamingResponse
import uuid
import logging
import asyncio
import json

# Import the LangGraph application
from agents.orchestrator import create_social_media_graph
from agents.state import AgentState
from memory.vector_db import add_post_to_memory, add_feedback_to_memory
from core.db import init_db, save_post_to_db, update_post_status, get_all_posts, get_post_by_id
from core.events import event_dispatcher

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)

# Suppress ChromaDB telemetry errors
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)

app = FastAPI(title="Multi-Agent Social Media Generator API")

# Initialize the graph and database
graph_app = create_social_media_graph()
init_db()

import os
# Ensure output directory exists
OUTPUT_DIR = "assets/generated_images"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

# Mount static files to serve images
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Models ----
class GenerateRequest(BaseModel):
    topic: str
    niche: str
    platforms: List[str]

class ReviewRequest(BaseModel):
    action: str  # "APPROVE" or "REJECT"
    feedback: Optional[str] = None

# ---- Endpoints ----

@app.get("/")
async def root():
    return {"message": "Social Media Post Generator API is running"}

@app.post("/api/generate")
async def start_generation(request: GenerateRequest, background_tasks: BackgroundTasks):
    """
    Start the multi-agent pipeline to generate a post.
    """
    thread_id = str(uuid.uuid4())
    
    initial_state = {
        "topic": request.topic,
        "niche": request.niche,
        "platforms": request.platforms,
        "status": "START",
        "retry_count": {},
        "error_count": 0,
        "review_history": []
    }
    
    async def run_graph():
        config = {"configurable": {"thread_id": thread_id}}
        try:
            # Wait for frontend SSE connection to avoid dumping all early tokens into history
            await event_dispatcher.wait_for_subscriber(thread_id)
            
            async for event in graph_app.astream(initial_state, config=config):
                pass
            
            # Check if workflow reached review state
            state_snapshot = await graph_app.aget_state(config)
            if state_snapshot and state_snapshot.values:
                state = state_snapshot.values
                # Save to DB if finished OR waiting for review at the scheduler node
                if state.get("status") == "WAITING_FOR_REVIEW" or (state_snapshot.next and "scheduler_agent" in state_snapshot.next):
                    save_post_to_db(
                        thread_id=thread_id,
                        topic=state.get("selected_title", ""),
                        niche=state.get("niche", ""),
                        research_brief=state.get("research_brief", ""),
                        post_contents=state.get("post_contents", {}),
                        image_url=state.get("image_url"),
                        image_prompt=state.get("image_prompt")
                    )
            # Signal end of all streams for this thread
            await event_dispatcher.end_stream(thread_id)
        except Exception as e:
            logger.error(f"Graph execution failed: {e}")
            try:
                await graph_app.aupdate_state(config, {"status": "ERROR", "feedback": f"System Error: {str(e)}"})
                await event_dispatcher.publish(thread_id, {"type": "error", "message": str(e)})
            except:
                pass
            await event_dispatcher.end_stream(thread_id)

    background_tasks.add_task(run_graph)
    
    return {"message": "Pipeline started", "thread_id": thread_id}

@app.get("/api/status/{thread_id}")
async def get_status(thread_id: str):
    """
    Get the current state of the pipeline for a specific thread.
    """
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = graph_app.get_state(config)
    
    if not state_snapshot or not state_snapshot.values:
        # Fallback to Database
        db_post = get_post_by_id(thread_id)
        if db_post:
            return {
                "status": db_post.status,
                "suggested_titles": [],
                "selected_title": db_post.topic,
                "research_brief": db_post.research_brief,
                "post_contents": db_post.post_contents or {},
                "image_url": db_post.image_url,
                "image_prompt": db_post.image_prompt,
                "scheduled_times": {}
            }
        return {"status": "NOT_FOUND"}
    
    state = state_snapshot.values
    current_status = state.get("status", "PROCESSING")
    
    # If the graph has an interrupt at scheduler_agent OR the status is explicitly WAITING_FOR_REVIEW
    is_waiting = (len(state_snapshot.next) > 0 and "scheduler_agent" in state_snapshot.next) or (current_status == "WAITING_FOR_REVIEW")
    
    # If already approved or rejected, don't show as waiting
    if current_status in ["APPROVED", "REJECTED"]:
        is_waiting = False

    logger.info(f"Thread {thread_id} status: {current_status}, is_waiting: {is_waiting}")
    
    return {
        "status": "WAITING_FOR_REVIEW" if is_waiting else current_status,
        "suggested_titles": state.get("suggested_titles", []),
        "selected_title": state.get("selected_title"),
        "research_brief": state.get("research_brief"),
        "post_contents": state.get("post_contents", {}),
        "image_url": state.get("image_url"),
        "image_prompt": state.get("image_prompt"),
        "scheduled_times": state.get("scheduled_times", {})
    }

@app.get("/api/posts")
async def list_posts():
    """
    Get all posts from the database.
    """
    posts = get_all_posts()
    return posts


@app.post("/api/review/{thread_id}")
async def review_post(thread_id: str, request: ReviewRequest, background_tasks: BackgroundTasks):
    """
    Submit human review (Approve or Reject with feedback).
    """
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = graph_app.get_state(config)
    
    state = {}
    if state_snapshot and state_snapshot.values:
        state = state_snapshot.values
    else:
        # Fallback: Rehydrate state from Database
        db_post = get_post_by_id(thread_id)
        if not db_post:
            raise HTTPException(status_code=400, detail="Workflow state and database record not found.")
        
        # Construct a basic state from DB data to resume
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
        # Update the graph state so we can resume
        graph_app.update_state(config, state)
        logger.info(f"Rehydrated state from DB for thread {thread_id}")

    new_status = "APPROVED" if request.action.upper() == "APPROVE" else "REJECTED"
    
    # Save to long-term memory
    # state is already defined above from snapshot or rehydration
    if new_status == "APPROVED":
        post_contents = state.get("post_contents", {})
        topic = state.get("selected_title", "Unknown Topic")
        niche = state.get("niche", "Unknown Niche")
        
        for platform, content in post_contents.items():
            post_id = f"{thread_id}_{platform}"
            metadata = {
                "platform": platform,
                "topic": topic,
                "niche": niche
            }
            try:
                add_post_to_memory(post_id, content, metadata)
                logger.info(f"Saved {platform} post to memory.")
            except Exception as e:
                logger.error(f"Failed to save post to memory: {e}")
                
        # Update PostgreSQL
        update_post_status(thread_id, "APPROVED")
                
    elif new_status == "REJECTED" and request.feedback:
        topic = state.get("selected_title", "Unknown Topic")
        niche = state.get("niche", "Unknown Niche")
        metadata = {
            "topic": topic,
            "niche": niche
        }
        try:
            add_feedback_to_memory(feedback_id, request.feedback, metadata)
            logger.info(f"Saved human feedback to memory.")
        except Exception as e:
            logger.error(f"Failed to save feedback to memory: {e}")
    
    update_dict = {"status": new_status, "feedback": request.feedback}
    if new_status == "REJECTED":
        update_dict["approved_platforms"] = []
        update_dict["platform_feedbacks"] = {}
        update_dict["platforms_written_this_round"] = []
        
        # Immediately clear post_contents in DB and set status to REJECTED
        save_post_to_db(
            thread_id=thread_id,
            topic=state.get("selected_title", ""),
            niche=state.get("niche", ""),
            research_brief=state.get("research_brief", ""),
            post_contents=state.get("post_contents", {}),
            image_url=state.get("image_url"),
            image_prompt=state.get("image_prompt")
        )
        update_post_status(thread_id, "REJECTED")
        
    try:
        graph_app.update_state(
            config, 
            update_dict
        )
    except Exception as e:
        logger.error(f"Failed to update state: {e}")
    
    async def run_resume_graph():
        try:
            async for event in graph_app.astream(None, config=config):
                 pass
                 
            # Check if workflow reached review state
            state_snapshot = await graph_app.aget_state(config)
            if state_snapshot and state_snapshot.values:
                state = state_snapshot.values
                if state.get("status") == "WAITING_FOR_REVIEW":
                    save_post_to_db(
                        thread_id=thread_id,
                        topic=state.get("selected_title", ""),
                        research_brief=state.get("research_brief", ""),
                        post_contents=state.get("post_contents", {}),
                        image_url=state.get("image_url"),
                        image_prompt=state.get("image_prompt")
                    )
            await event_dispatcher.end_stream(thread_id)
        except Exception as e:
            logger.error(f"Graph execution failed: {e}")
            try:
                await graph_app.aupdate_state(config, {"status": "ERROR", "feedback": f"System Error: {str(e)}"})
                await event_dispatcher.publish(thread_id, {"type": "error", "message": str(e)})
            except:
                pass
            await event_dispatcher.end_stream(thread_id)

    background_tasks.add_task(run_resume_graph)
    
    return {"message": f"Post {new_status.lower()} successfully."}

@app.get("/api/stream/{thread_id}")
async def stream_updates(thread_id: str):
    """
    SSE endpoint to stream tokens and status updates to the frontend.
    """
    async def event_generator():
        # Yield an initial event to confirm connection
        yield f"data: {json.dumps({'type': 'connected'})}\n\n"
        
        async for event in event_dispatcher.subscribe(thread_id):
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no" # Essential for Nginx
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
