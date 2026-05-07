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
    prompt = f"""Bạn là một chuyên gia Topic Agent. Hãy đề xuất 1 tiêu đề bài đăng hấp dẫn 
    cho lĩnh vực '{state['niche']}' tập trung vào chủ đề '{state['topic']}'.
    
    YÊU CẦU QUAN TRỌNG:
    - CHỈ trả về danh sách 3 tiêu đề, mỗi tiêu đề trên 1 dòng.
    - KHÔNG thêm lời dẫn, không thêm số thứ tự 1, 2, 3 ở đầu.
    - Phù hợp với các nền tảng: {', '.join(state['platforms'])}.
    """
    
    # response = safe_invoke(llm, prompt)
    # save_llm_output("topic_suggestions", prompt, response.content)
    
    full_response = ""
    async for token in safe_stream_invoke(prompt):
        full_response += token
        await event_dispatcher.publish(thread_id, {"type": "topic_token", "content": token})
        
    save_llm_output("topic_suggestions", prompt, full_response)
    
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
    async for token in safe_stream_invoke(summary_prompt):
        full_brief += token
        await event_dispatcher.publish(thread_id, {"type": "brief_token", "content": token})
        
    save_llm_output("research_brief", summary_prompt, full_brief)
    logger.info("--- END: Research Agent (Brief generated) ---")
    
    return {
        "research_brief": full_brief,
        "status": "WRITING"
    }
