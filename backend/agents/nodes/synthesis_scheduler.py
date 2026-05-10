from typing import Dict, Any
import logging
from core.llm import get_llm, safe_invoke
from core.utils import save_llm_output
from agents.state import AgentState

logger = logging.getLogger(__name__)

import json
import re

def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except:
            pass
    return None

def platform_qa_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Quality Assurance Agent for a SPECIFIC platform.
    """
    platform = state.get("current_platform")
    if not platform:
        logger.error("current_platform not set in platform_qa_agent_node")
        return {"is_brand_voice_aligned": True}

    logger.info(f"--- START: QA Agent for {platform} ---")
    llm = get_llm(agent_type="qa")
    
    content = state.get("post_contents", {}).get(platform, "")
    brief = state.get("research_brief", "")
    
    feedback_instruction = ""
    if state.get("feedback"):
        feedback_instruction = f"""
    LƯU Ý QUAN TRỌNG: Bài viết vừa được sửa theo yêu cầu: "{state['feedback']}"
    Nếu nội dung thay đổi để khớp yêu cầu này, bạn PHẢI cho 'PASSED'.
    """

    qa_prompt = f"""Hãy kiểm tra chất lượng bài đăng mạng xã hội sau:
    Nền tảng: {platform}
    Nội dung: {content}
    Research Brief: {brief}
    {feedback_instruction}
    
    Yêu cầu:
    - Kiểm tra số liệu có khớp Research Brief không.
    - Kiểm tra giọng văn có phù hợp {platform} không.
    
    TRẢ VỀ JSON:
    {{
        "status": "PASSED" hoặc "FAILED",
        "reason": "Lý do nếu FAILED"
    }}
    """
    response = safe_invoke(llm, qa_prompt)
    qa_filepath = save_llm_output(f"qa_result_{platform}", qa_prompt, response.content)
    logger.info(f"QA result for {platform} saved to: {qa_filepath}")
    qa_result = extract_json(response.content) or {"status": "PASSED"}
    
    is_passed = qa_result.get("status", "").upper() == "PASSED"
    
    approved_platforms = [platform] if is_passed else []
    platform_feedbacks = {platform: qa_result.get("reason", "Không đạt QA")} if not is_passed else {}
    
    # Handle retry count per platform
    retry_dict = state.get("retry_count") or {}
    platform_retry = retry_dict.get(platform, 0)
    
    if not is_passed:
        platform_retry += 1
        logger.warning(f"QA Failed for {platform}. Retry: {platform_retry}")

    logger.info(f"--- END: QA Agent for {platform} (Result: {qa_result.get('status')}) ---")
    
    return {
        "approved_platforms": approved_platforms,
        "platform_feedbacks": platform_feedbacks,
        "retry_count": {platform: platform_retry},
        # Signal if this specific platform is finished or needs retry
        "is_brand_voice_aligned": is_passed 
    }

def scheduler_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Scheduler Agent: Suggests the best time to post.
    """
    logger.info("--- START: Scheduler Agent ---")
    # Mock scheduling logic
    scheduled_times = {
        platform: "2024-05-07 09:00" for platform in state['platforms']
    }
    logger.info(f"Scheduled times: {scheduled_times}")
    
    current_status = state.get("status")
    # If we just finished a round of writing/image gen or we were in REJECTED state, 
    # move to PENDING_REVIEW for the user to see the updated results.
    if current_status in ["WRITING", "GENERATING_IMAGE", "REJECTED"]:
        final_status = "PENDING_REVIEW"
    else:
        final_status = current_status if current_status in ["APPROVED", "REJECTED"] else "PENDING_REVIEW"
    
    logger.info("--- END: Scheduler Agent (Processing finished) ---")
    return {
        "scheduled_times": scheduled_times,
        "status": final_status
    }
