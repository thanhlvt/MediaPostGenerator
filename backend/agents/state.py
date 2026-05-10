from typing import Annotated, List, TypedDict, Optional, Dict, Any
from langgraph.graph.message import add_messages
import operator

def merge_dict(left: Any, right: Any) -> dict:
    """Merges two dictionaries safely. If right is explicitly {}, it clears the dict."""
    if right == {}: return {}
    if not isinstance(left, dict): left = {}
    if not isinstance(right, dict): right = {}
    return {**left, **right}

def merge_list(left: Any, right: Any) -> list:
    """Merges two lists safely. If right is explicitly [], it clears the list."""
    if right == []: return []
    if not isinstance(left, list): left = []
    if not isinstance(right, list): right = []
    return list(set(left + right))

def take_last(left: Any, right: Any) -> Any:
    """Always takes the latest value. Useful for status updates in parallel branches."""
    return right if right is not None else left

class AgentState(TypedDict):
    # Metadata & Input
    topic: Annotated[str, take_last]
    niche: Annotated[str, take_last]
    platforms: Annotated[List[str], merge_list] # e.g., ["Instagram", "LinkedIn", "Twitter"]
    current_platform: Annotated[Optional[str], take_last] # Used in parallel branches
    
    # Processed Data
    research_brief: Annotated[Optional[str], take_last]
    suggested_titles: Annotated[List[str], merge_list]
    selected_title: Annotated[Optional[str], take_last]
    
    # Generated Content
    # Dictionary mapping platform to its specific content
    post_contents: Annotated[dict, merge_dict] # { "Instagram": "...", "LinkedIn": "..." }
    image_prompt: Annotated[Optional[str], take_last]
    image_url: Annotated[Optional[str], take_last]
    
    # Quality & Scheduling
    is_brand_voice_aligned: Annotated[bool, take_last]
    fact_checked: Annotated[bool, take_last]
    retry_count: Annotated[Dict[str, int], merge_dict] # { "Instagram": 0, "LinkedIn": 1 }
    scheduled_times: Annotated[dict, merge_dict] # { "Instagram": "2024-05-06 18:00", ... }
    approved_platforms: Annotated[List[str], merge_list] # Platforms that passed QA
    platform_feedbacks: Annotated[dict, merge_dict] # { "Instagram": "Too many hashtags", ... }
    platforms_written_this_round: Annotated[List[str], merge_list] # Tracks progress
    
    # Human Review
    status: Annotated[str, take_last] # "START", "RESEARCHING", "WRITING", "PENDING_REVIEW", "APPROVED", "REJECTED"
    feedback: Annotated[Optional[str], take_last]
    review_history: Annotated[List[str], merge_list]
    
    # Errors/Retries
    error_count: Annotated[int, take_last]
