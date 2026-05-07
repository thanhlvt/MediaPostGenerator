from typing import Dict, Any
import logging
import os
from langchain_core.runnables import RunnableConfig
from core.llm import get_llm, generate_image, safe_invoke, safe_stream_invoke
from core.utils import save_llm_output, save_image_from_url, save_image_to_outputs
from core.events import event_dispatcher
from agents.state import AgentState
from memory.vector_db import search_past_posts, search_past_feedback

logger = logging.getLogger(__name__)

async def writer_agent_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Writer Agent: Creates content for a specific platform based on research.
    """
    # In parallel mode, 'current_platform' should be set. 
    # Fallback to platforms[0] if not present (for backward compatibility)
    platform = state.get("current_platform")
    if not platform:
        platforms = state.get("platforms", [])
        approved = state.get("approved_platforms", [])
        written = state.get("platforms_written_this_round", [])
        to_write = [p for p in platforms if p not in approved and p not in written]
        if not to_write:
            return {"status": "GENERATING_IMAGE"}
        platform = to_write[0]

    logger.info(f"--- START: Writer Agent (Platform: {platform}) ---")
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    llm = get_llm()
    post_contents = state.get("post_contents") or {}
    platform_feedbacks = state.get("platform_feedbacks") or {}
    
    # Check if this is a retry and we have feedback from Human
    human_feedback_section = ""
    if state.get("feedback"):
        human_feedback_section = f"\nLƯU Ý QUAN TRỌNG TỪ NGƯỜI DUYỆT:\n{state['feedback']}\nBạn PHẢI sửa lại bài viết theo yêu cầu trên."
    
    # Platform specific QA feedback
    qa_feedback_section = ""
    if platform in platform_feedbacks:
        qa_feedback_section = f"\nLỖI CẦN SỬA (TỪ LẦN KIỂM DUYỆT TRƯỚC):\n{platform_feedbacks[platform]}\nBạn PHẢI khắc phục lỗi này."
        
    # Check if we have an existing post to revise
    current_post_section = ""
    if platform in post_contents and (human_feedback_section or qa_feedback_section):
        current_post_section = f"\nNỘI DUNG BÀI VIẾT HIỆN TẠI (CẦN SỬA LẠI):\n---\n{post_contents[platform]}\n---\n"
        
    # Search Long-Term Memory (ChromaDB) - Cached or per-node
    memory_section = ""
    try:
        niche = state.get("niche")
        search_query = state.get('selected_title') or state.get('topic') or "social media post"
        past_posts = search_past_posts(search_query, n_results=1, niche=niche)
        past_feedbacks = search_past_feedback(search_query, n_results=2, niche=niche)
        memories = []
        if past_posts and past_posts.get('documents') and len(past_posts['documents'][0]) > 0:
            memories.append("MẪU BÀI ĐĂNG THÀNH CÔNG TRONG QUÁ KHỨ:\n" + past_posts['documents'][0][0])
        if past_feedbacks and past_feedbacks.get('documents') and len(past_feedbacks['documents'][0]) > 0:
            feedbacks = "\n- ".join(past_feedbacks['documents'][0])
            memories.append("LỜI PHÊ TỪ CÁC LẦN TRƯỚC:\n- " + feedbacks)
        if memories:
            memory_section = "\n\n--- DỮ LIỆU TỪ BỘ NHỚ DÀI HẠN ---\n" + "\n\n".join(memories)
    except: pass

    platform_requirements = {
        "Instagram": "Cần hook mạnh, icon sinh động, và 10-15 hashtags.",
        "LinkedIn": "Cần giọng văn chuyên nghiệp, có cấu trúc rõ ràng (Problem-Agitation-Solution), ít hashtag.",
        "Twitter": "Ngắn gọn, súc tích, dưới 280 ký tự.",
        "TikTok": "Đây là nội dung cho DẠNG ẢNH CUỘN (Photo Scroll). Hãy chia nội dung thành 5-7 Slides. Mỗi Slide gồm: [Tiêu đề Slide] và [Nội dung ngắn gọn/Bullet points]. Slide 1: Hook bằng insight bất ngờ hoặc câu hỏi gây tò mò. Slide cuối là CTA.",
        "Facebook": "Viết dài vừa phải, khoảng 2-3 đoạn, chú trọng vào tương tác ở cuối bài."
    }
    specific_requirement = platform_requirements.get(platform, "Viết nội dung phù hợp với đặc thù của nền tảng.")
        
    prompt = f"""Bạn là một chuyên gia Copywriter. Hãy viết một bài đăng mạng xã hội cho nền tảng {platform}.
    Tiêu đề: {state.get('selected_title', '')}
    RESEARCH BRIEF (chỉ dùng thông tin trong này): {state.get('research_brief', '')}
    {human_feedback_section}
    {qa_feedback_section}
    {current_post_section}
    {memory_section}
    
    Yêu cầu riêng cho {platform}:
    - {specific_requirement}
    """
    
    full_response = ""
    full_reasoning = ""
    await event_dispatcher.publish(thread_id, {"type": "start", "platform": platform})
    
    try:
        async for token_obj in safe_stream_invoke(prompt):
            if token_obj["type"] == "reasoning":
                full_reasoning += token_obj["content"]
                await event_dispatcher.publish(thread_id, {"type": "reasoning", "platform": platform, "content": token_obj["content"]})
            else:
                token = token_obj["content"]
                full_response += token
                await event_dispatcher.publish(thread_id, {"type": "token", "platform": platform, "content": token})
        
        await event_dispatcher.publish(thread_id, {"type": "end", "platform": platform})
        
        # Combine reasoning and response for the audit log
        combined_output = f"--- REASONING ---\n{full_reasoning}\n\n--- CONTENT ---\n{full_response}"
        save_llm_output(f"post_{platform}", prompt, combined_output)
        
        logger.info(f"--- END: Writer Agent (Finished {platform}) ---")
        return {
            "post_contents": {platform: full_response},
            "platforms_written_this_round": [platform]
        }
    except Exception as e:
        logger.error(f"Error during streaming for {platform}: {e}")
        await event_dispatcher.publish(thread_id, {"type": "error", "message": f"Error on {platform}: {str(e)}"})
        raise e

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
        "image_url": url
    }
