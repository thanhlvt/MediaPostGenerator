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

def synthesis_qa_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Synthesis + QA Agent: Final check, brand voice alignment, and fact-checking.
    Also handles feedback from human review.
    """
    logger.info("--- START: Synthesis & QA Agent ---")
    llm = get_llm()
    
    if state.get("feedback"):
        logger.info(f"Processing feedback: {state['feedback']}")
        pass

    feedback_instruction = ""
    if state.get("feedback"):
        feedback_instruction = f"""
    LƯU Ý TỐI QUAN TRỌNG: 
    Bài viết này vừa được chỉnh sửa theo yêu cầu sau: "{state['feedback']}"
    Nếu nội dung bài viết thay đổi để tuân thủ yêu cầu trên (ví dụ: thay đổi mốc thời gian, thay đổi giọng văn, thêm bớt chi tiết... khác với Research Brief), BẠN PHẢI CHẤP NHẬN SỰ SAI LỆCH NÀY VÀ CHO 'PASSED'.
    """

    qa_prompt = f"""Hãy kiểm tra tính nhất quán và chất lượng của các bài đăng mạng xã hội sau:
    Nội dung: {state['post_contents']}
    Research Brief: {state['research_brief']}
    {feedback_instruction}
    
    Yêu cầu:
    - Kiểm tra xem các số liệu có khớp với Research Brief không (ngoại trừ các thay đổi do yêu cầu đặc biệt ở trên).
    - Kiểm tra xem giọng văn có phù hợp không.
    
    BẮT BUỘC: Bạn PHẢI trả về kết quả dưới định dạng JSON duy nhất. KHÔNG trả về gì khác ngoài JSON.
    Cú pháp JSON:
    {{
        "TikTok": {{"status": "PASSED"}},
        "Instagram": {{"status": "FAILED", "reason": "Mô tả lỗi cụ thể ở đây"}}
    }}
    Lưu ý: Thay thế các key bằng đúng tên nền tảng tương ứng.
    """
    response = safe_invoke(llm, qa_prompt)
    save_llm_output("qa_result", qa_prompt, response.content)
    logger.info(f"QA Result: {response.content}")
    
    # Parse JSON
    qa_result_json = extract_json(response.content)
    approved_platforms = []
    platform_feedbacks = {}
    
    if qa_result_json:
        for platform, res in qa_result_json.items():
            if res.get("status", "").upper() == "PASSED":
                approved_platforms.append(platform)
            else:
                platform_feedbacks[platform] = res.get("reason", "Không đạt yêu cầu QA")
    else:
        # Fallback
        is_passed = "PASSED" in response.content.upper()
        if is_passed:
            approved_platforms = list(state['post_contents'].keys())
        else:
            for p in state['post_contents'].keys():
                platform_feedbacks[p] = response.content
                
    current_retry = state.get("retry_count")
    if current_retry is None:
        current_retry = 0

    all_passed = len(approved_platforms) == len(state['post_contents'])
    
    if not all_passed:
        current_retry += 1
        logger.warning(f"QA Failed for some platforms. Incrementing retry_count to {current_retry}")

    if current_retry >= 3:
        logger.warning("Max retries reached. Forcing WAITING_FOR_REVIEW.")
        status = "WAITING_FOR_REVIEW"
    else:
        status = "WAITING_FOR_REVIEW" if all_passed else "WRITING"

    logger.info("--- END: Synthesis & QA Agent ---")
    return {
        "is_brand_voice_aligned": all_passed,
        "fact_checked": all_passed,
        "retry_count": current_retry,
        "status": status,
        "approved_platforms": approved_platforms,
        "platform_feedbacks": platform_feedbacks,
        "platforms_written_this_round": [] # Reset for next retry
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
    # If we are here after a human action, keep that status. Otherwise, it's the first hit.
    final_status = current_status if current_status in ["APPROVED", "REJECTED"] else "WAITING_FOR_REVIEW"
    
    logger.info("--- END: Scheduler Agent (Processing finished) ---")
    return {
        "scheduled_times": scheduled_times,
        "status": final_status
    }
