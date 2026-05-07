from typing import Dict, Any
import logging
from langchain_core.runnables import RunnableConfig
from core.llm import get_llm, safe_invoke, safe_stream_invoke
from core.search import direct_search
from core.utils import save_llm_output
from core.events import event_dispatcher
from agents.state import AgentState

logger = logging.getLogger(__name__)

async def topic_agent_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Topic Agent: Analyzes trends and suggests titles.
    """
    logger.info(f"--- START: Topic Agent (Niche: {state['niche']}, Topic: {state['topic']}) ---")
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    
    llm = get_llm()
    prompt = f"""Bạn là chuyên gia viết nội dung viral cho social media tại thị trường Việt Nam cho lĩnh vực '{state['niche']}'. 
    Hãy viết 1 tiêu đề bài đăng mạng xã hội cực kỳ hấp dẫn cho chủ đề: "{state['topic']}".

    TARGET AUDIENCE: Người từ 22–40 tuổi, đang quan tâm đến {state['niche']}, có nhu cầu hoặc lo ngại về {state['topic']}.

    ### YÊU CẦU:
    - Mỗi tiêu đề dưới 15 từ.
    - Bắt đầu bằng hook gây tò mò hoặc nỗi sợ (fear/curiosity trigger).
    - Dùng ngôn ngữ nói, gần gũi, tự nhiên như người thật nói chuyện.
    - KHÔNG dùng từ sáo rỗng: "bí quyết", "xem ngay", "đừng bỏ lỡ".
    - KHÔNG đánh số, KHÔNG thêm chú thích, KHÔNG thêm dấu nháy đơn hoặc nháy kép.
    - Chỉ trả về ĐÚNG 1 tiêu đề.
    - Phù hợp với các nền tảng: {', '.join(state['platforms'])}.

    ### 3 GÓC TIẾP CẬN BẮT BUỘC:
    1. Fear (Nỗi sợ mất mát/hệ quả): Phải có yếu tố open loop (người đọc cảm thấy thiếu thông tin, muốn xem tiếp). 
       VD tốt: "Vay 20 triệu, 6 tháng sau nhận cuộc gọi này — mình không ngờ"
       VD chưa tốt: "Gán nợ cả căn nhà vì vay nóng" (kết thúc rồi, không cần xem tiếp)
    2. Curiosity (Tò mò/Ngạc nhiên): Đưa ra thông tin gây bất ngờ hoặc phá vỡ lầm tưởng.
       VD: "Mình từng sợ vay ngân hàng, cho đến khi biết điều này"
    3. Social Proof (Trải nghiệm thật/Câu chuyện): Dùng ngôn ngữ cá nhân "mình", "người thật việc thật", có yếu tố open loop.
       VD: "Vay 50 triệu ngoài 3 tháng, trả lại 80 triệu — chuyện có thật"
    """
    
    # response = safe_invoke(llm, prompt)
    # save_llm_output("topic_suggestions", prompt, response.content)
    
    full_response = ""
    full_reasoning = ""
    async for token_obj in safe_stream_invoke(prompt):
        if token_obj["type"] == "reasoning":
            # Just publish to frontend, don't add to final response
            full_reasoning += token_obj["content"]
            await event_dispatcher.publish(thread_id, {"type": "topic_reasoning", "content": token_obj["content"]})
        else:
            token = token_obj["content"]
            full_response += token
            await event_dispatcher.publish(thread_id, {"type": "topic_token", "content": token})
        
    save_llm_output("topic_suggestions", prompt, full_response)
    if full_reasoning:
        save_llm_output("topic_reasoning", prompt, full_reasoning)
    
    # Clean and parse titles: remove empty lines and intro text
    raw_titles = [line.strip() for line in full_response.split("\n") if line.strip()]
    # Filter out lines that look like headers or intro text (e.g., lines ending with :)
    suggested_titles = [t for t in raw_titles if not t.endswith(":") and len(t) > 10]
    
    selected_title = suggested_titles[0] if suggested_titles else "Default Topic"
    logger.info(f"--- END: Topic Agent (Selected: {selected_title}) ---")
    
    return {
        "suggested_titles": suggested_titles,
        "selected_title": selected_title,
        "status": "RESEARCHING"
    }

async def research_agent_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Research Agent: Uses Tavily to collect information.
    """
    logger.info(f"--- START: Research Agent (Topic: {state['selected_title']}) ---")
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    
    query = f"Thông tin chi tiết, số liệu và sự thật thú vị về: {state['selected_title']}"
    search_results = direct_search(query)
    
    # Summarize results
    research_context = "\n".join([f"- {r['content']} (Source: {r['url']})" for r in search_results.get('results', [])])
    
    llm = get_llm()
    summary_prompt = f"""Dựa trên kết quả tìm kiếm sau, hãy tạo một bản 'Research Brief' ngắn gọn để Writer Agent có thể viết bài.
    Kết quả tìm kiếm:
    {research_context}
    
    Yêu cầu Research Brief:
    - Trích xuất ít nhất 3 facts/số liệu quan trọng.
    - Có nguồn rõ ràng.
    - Tóm tắt ý chính.
    """
    
    # summary_response = safe_invoke(llm, summary_prompt)
    # save_llm_output("research_brief", summary_prompt, summary_response.content)
    
    full_brief = ""
    full_reasoning = ""
    async for token_obj in safe_stream_invoke(summary_prompt):
        if token_obj["type"] == "reasoning":
            full_reasoning += token_obj["content"]
            await event_dispatcher.publish(thread_id, {"type": "brief_reasoning", "content": token_obj["content"]})
        else:
            token = token_obj["content"]
            full_brief += token
            await event_dispatcher.publish(thread_id, {"type": "brief_token", "content": token})
        
    save_llm_output("research_brief", summary_prompt, full_brief)
    if full_reasoning:
        save_llm_output("research_brief_reasoning", summary_prompt, full_reasoning)
    logger.info("--- END: Research Agent (Brief generated) ---")
    
    return {
        "research_brief": full_brief,
        "status": "WRITING"
    }
