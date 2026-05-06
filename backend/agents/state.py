from typing import Annotated, List, TypedDict, Optional
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # Metadata & Input
    topic: str
    niche: str
    platforms: List[str] # e.g., ["Instagram", "LinkedIn", "Twitter"]
    
    # Processed Data
    research_brief: Optional[str]
    suggested_titles: List[str]
    selected_title: Optional[str]
    
    # Generated Content
    # Dictionary mapping platform to its specific content
    post_contents: dict # { "Instagram": "...", "LinkedIn": "..." }
    image_prompt: Optional[str]
    image_url: Optional[str]
    
    # Quality & Scheduling
    is_brand_voice_aligned: bool
    fact_checked: bool
    retry_count: int
    scheduled_times: dict # { "Instagram": "2024-05-06 18:00", ... }
    approved_platforms: List[str] # Platforms that passed QA
    platform_feedbacks: dict # { "Instagram": "Too many hashtags", ... }
    platforms_written_this_round: List[str] # Tracks progress within a generation loop
    
    # Human Review
    status: str # "START", "RESEARCHING", "WRITING", "WAITING_FOR_REVIEW", "APPROVED", "REJECTED"
    feedback: Optional[str]
    review_history: List[str]
    
    # Errors/Retries
    error_count: int
