from typing import Dict, Any
import logging
import os
from langchain_core.runnables import RunnableConfig
from core.llm import get_llm, generate_image, safe_invoke
from core.utils import save_llm_output, save_image_from_url, save_image_to_outputs
from agents.state import AgentState
from memory.vector_db import search_past_posts, search_past_feedback

logger = logging.getLogger(__name__)

def writer_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Writer Agent: Creates content for each platform based on research.
    """
    logger.info(f"--- START: Writer Agent (Platforms: {state['platforms']}) ---")
    llm = get_llm()
    post_contents = state.get("post_contents") or {}
    approved_platforms = state.get("approved_platforms") or []
    platform_feedbacks = state.get("platform_feedbacks") or {}
    platforms_written = state.get("platforms_written_this_round") or []
    
    # Check if this is a retry and we have feedback from Human
    human_feedback_section = ""
    if state.get("status") == "REJECTED" and state.get("feedback"):
        # Human rejected (Prioritize this)
        human_feedback_section = f"\nLƯU Ý QUAN TRỌNG TỪ NGƯỜI DUYỆT:\n{state['feedback']}\nBạn PHẢI sửa lại bài viết theo yêu cầu trên."
        logger.info(f"Rewriting based on human feedback: {state['feedback'][:100]}...")
    
    # Search Long-Term Memory (ChromaDB)
    memory_section = ""
    try:
        search_query = state.get('selected_title')
        if not search_query:
            search_query = state.get('topic') or "social media post"
            
        past_posts = search_past_posts(search_query, n_results=1)
        past_feedbacks = search_past_feedback(search_query, n_results=2)
        
        memories = []
        if past_posts and past_posts.get('documents') and len(past_posts['documents'][0]) > 0:
            memories.append("MẪU BÀI ĐĂNG THÀNH CÔNG TRONG QUÁ KHỨ (Hãy tham khảo văn phong và cấu trúc):\n" + past_posts['documents'][0][0])
            
        if past_feedbacks and past_feedbacks.get('documents') and len(past_feedbacks['documents'][0]) > 0:
            feedbacks = "\n- ".join(past_feedbacks['documents'][0])
            memories.append("LỜI PHÊ TỪ CÁC LẦN TRƯỚC (Hãy tuyệt đối tránh lặp lại lỗi này):\n- " + feedbacks)
            
        if memories:
            memory_section = "\n\n--- DỮ LIỆU TỪ BỘ NHỚ DÀI HẠN (LONG-TERM MEMORY) ---\n" + "\n\n".join(memories) + "\n--------------------------------------------------"
            logger.info("Successfully loaded long-term memory into prompt.")
    except Exception as e:
        logger.warning(f"Failed to fetch long-term memory: {e}")
    
    platforms_to_write = [p for p in state['platforms'] if p not in approved_platforms and p not in platforms_written]
    
    if platforms_to_write:
        platform = platforms_to_write[0]
        logger.info(f"Writing content for {platform}...")
        
        # Platform specific QA feedback
        qa_feedback_section = ""
        if platform in platform_feedbacks:
            qa_feedback_section = f"\nLỖI CẦN SỬA (TỪ LẦN KIỂM DUYỆT TRƯỚC):\n{platform_feedbacks[platform]}\nBạn PHẢI khắc phục lỗi này."
            
        prompt = f"""Bạn là một chuyên gia Copywriter. Hãy viết một bài đăng mạng xã hội cho nền tảng {platform}.
        Tiêu đề: {state.get('selected_title', '')}
        Thông tin nghiên cứu: {state.get('research_brief', '')}
        {human_feedback_section}
        {qa_feedback_section}
        {memory_section}
        
        Yêu cầu riêng cho {platform}:
        - Nếu là Instagram: Cần hook mạnh, icon sinh động, và 10-15 hashtags.
        - Nếu là LinkedIn: Cần giọng văn chuyên nghiệp, có cấu trúc rõ ràng (Problem-Agitation-Solution), ít hashtag.
        - Nếu là Twitter: Ngắn gọn, súc tích, dưới 280 ký tự.
        - Nếu là TikTok: Đây là nội dung cho DẠNG ẢNH CUỘN (Photo Scroll). Hãy chia nội dung thành 5-7 Slides. Mỗi Slide gồm: [Tiêu đề Slide] và [Nội dung ngắn gọn/Bullet points]. Slide cuối là CTA.
        - Nếu là Facebook: Viết dài vừa phải, khoảng 2-3 đoạn, chú trọng vào tương tác ở cuối bài.
        
        Nội dung bài viết:
        """
        response = safe_invoke(llm, prompt)
        save_llm_output(f"post_{platform}", prompt, response.content)
        post_contents[platform] = response.content
        platforms_written.append(platform)
        
        logger.info(f"--- END: Writer Agent (Finished {platform}) ---")
        return {
            "post_contents": post_contents,
            "platforms_written_this_round": platforms_written,
            "status": "WRITING"
        }
    
    # If no platforms left to write, we proceed
    logger.info("--- END: Writer Agent (All required platforms written) ---")
    return {
        "status": "GENERATING_IMAGE"
    }

def image_agent_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Generate or provide an image for the post.
    """
    logger.info("--- START: Image Agent ---")
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    
    if state.get("image_url"):
        logger.info("Image already generated. Skipping.")
        return {"status": "QUALITY_ASSURANCE"}
        
    llm = get_llm()
    
    # Step 1: Create a visual prompt
    prompt_gen_msg = f"""Dựa trên nội dung bài viết sau, hãy tạo một prompt tiếng Anh chi tiết để tạo ảnh minh họa.
    Nội dung: {state['selected_title']}
    
    YÊU CẦU QUAN TRỌNG: 
    - CHỈ trả về đoạn văn bản Prompt bằng tiếng Anh.
    - KHÔNG thêm lời dẫn (ví dụ: 'Here is the prompt...').
    - KHÔNG thêm ký tự đặc biệt hay định dạng Markdown.
    """
    prompt_response = safe_invoke(llm, prompt_gen_msg)
    save_llm_output("image_prompt_raw", prompt_gen_msg, prompt_response.content)
    # Clean the prompt just in case
    image_prompt = prompt_response.content.strip().replace("`", "").replace("Prompt:", "").strip()
    logger.info(f"Visual prompt generated: {image_prompt[:100]}...")
    
    # Step 2: Generate image via OpenRouter
    # logger.info("Calling image generator API via OpenRouter...")
    # try:
    #     url = generate_image(image_prompt)
    #     save_image_from_url(url, "final_post_image")
    #     logger.info("Image successfully generated and saved to tmp.")
    # except Exception as e:
    #     logger.error(f"Error generating image: {e}")
    #     url = "https://via.placeholder.com/1024x1024.png?text=Image+Generation+Failed"
    
    # TEMPORARY: Use placeholder to save tokens during testing
    raw_url = "assets/placeholder.png"
    
    # Save to outputs directory for serving via API
    filename = f"post_{thread_id}.png"
    relative_url = save_image_to_outputs(raw_url, filename)
    
    # Construct full backend URL
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    url = f"{backend_url}{relative_url}" if relative_url else raw_url
        
    logger.info(f"--- END: Image Agent (URL: {url}) ---")
    return {
        "image_prompt": image_prompt,
        "image_url": url,
        "status": "QUALITY_ASSURANCE"
    }
