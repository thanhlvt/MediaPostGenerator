from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from fastapi.responses import StreamingResponse
import logging
import json

# Import services and core modules
from core.db import init_db, get_all_posts, get_post_by_id, delete_post_by_id, delete_posts_batch, get_settings, update_settings
from core.events import event_dispatcher
from services.workflow_service import graph_app
from services import post_service

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

# Initialize database
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
    quantity: int = 1

class GenerateBatchRequest(BaseModel):
    topic: str
    niche: str
    platforms: List[str]
    quantity: int

class ReviewRequest(BaseModel):
    action: str  # "APPROVE" or "REJECT"
    feedback: Optional[str] = None

# ---- Endpoints ----

@app.get("/")
async def root():
    return {"message": "Social Media Post Generator API is running"}

@app.post("/api/generate")
async def start_generation(request: GenerateRequest):
    """
    Endpoint to start a single post generation.
    """
    thread_id = await post_service.start_single_generation(
        request.topic, request.niche, request.platforms
    )
    return {"message": "Pipeline started", "thread_id": thread_id}

@app.post("/api/generate/batch")
async def start_batch_generation(request: GenerateBatchRequest):
    """
    Endpoint to start batch post generation.
    """
    thread_ids = await post_service.start_batch_generation(
        request.topic, request.niche, request.platforms, request.quantity
    )
    return {
        "message": f"Batch generation started for {len(thread_ids)} posts",
        "thread_ids": thread_ids
    }

@app.get("/api/status/{thread_id}")
async def get_status(thread_id: str):
    """
    Get the current state of the pipeline for a specific thread.
    """
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = await graph_app.aget_state(config)
    
    if not state_snapshot or not state_snapshot.values:
        db_post = get_post_by_id(thread_id)
        if db_post:
            return {
                "status": db_post.status,
                "selected_title": db_post.topic,
                "research_brief": db_post.research_brief,
                "post_contents": db_post.post_contents or {},
                "image_url": db_post.image_url,
                "image_prompt": db_post.image_prompt,
                "created_at": db_post.created_at
            }
        return {"status": "NOT_FOUND"}
    
    state = state_snapshot.values
    current_status = state.get("status", "PROCESSING")
    is_waiting = (len(state_snapshot.next) > 0 and "scheduler_agent" in state_snapshot.next) or (current_status == "PENDING_REVIEW")
    
    if current_status in ["APPROVED", "REJECTED"]:
        is_waiting = False

    return {
        "status": "PENDING_REVIEW" if is_waiting else current_status,
        "selected_title": state.get("selected_title"),
        "research_brief": state.get("research_brief"),
        "post_contents": state.get("post_contents", {}),
        "image_url": state.get("image_url"),
        "image_prompt": state.get("image_prompt")
    }

@app.get("/api/settings")
async def fetch_settings():
    return get_settings()

@app.post("/api/settings")
async def save_settings(request: dict):
    update_settings(request)
    return {"status": "success"}

@app.get("/api/posts")
async def list_posts(page: int = 1, limit: int = 10):
    return get_all_posts(page=page, limit=limit)

@app.delete("/api/posts/{thread_id}")
async def delete_post(thread_id: str):
    success = delete_post_by_id(thread_id)
    if not success:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"status": "success", "message": "Post deleted"}

@app.post("/api/posts/delete-batch")
async def delete_batch(request: dict):
    thread_ids = request.get("thread_ids", [])
    if not thread_ids:
        return {"status": "error", "message": "No IDs provided"}
    count = delete_posts_batch(thread_ids)
    return {"status": "success", "message": f"Deleted {count} posts"}

@app.post("/api/review/{thread_id}")
async def review_post(thread_id: str, request: ReviewRequest):
    """
    Submit human review for a post.
    """
    new_status = await post_service.submit_post_review(
        thread_id, request.action, request.feedback
    )
    return {"message": f"Post {new_status.lower()} successfully."}

@app.get("/api/stream/{thread_id}")
async def stream_updates(thread_id: str):
    """
    SSE endpoint to stream tokens and status updates.
    """
    async def event_generator():
        yield f"data: {json.dumps({'type': 'connected'})}\n\n"
        async for event in event_dispatcher.subscribe(thread_id):
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
