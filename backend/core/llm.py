import os
import logging
from langchain_openai import ChatOpenAI
from openai import OpenAI
from dotenv import load_dotenv
import httpx
import json

load_dotenv()

logger = logging.getLogger(__name__)

# Fetch configurations from .env
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

DEFAULT_TEXT_MODEL = os.getenv("DEFAULT_TEXT_MODEL", "deepseek/deepseek-v4-flash")
DEFAULT_IMAGE_MODEL = os.getenv("DEFAULT_IMAGE_MODEL", "google/gemini-2.5-flash-image")

def get_model_for_agent(agent_type: str) -> str:
    """
    Lấy model_name được cấu hình trong DB cho từng loại agent.
    agent_type: 'topic', 'research', 'writer', 'qa', 'image'
    """
    from core.db import get_settings
    settings = get_settings()
    key = f"{agent_type}_model"
    if agent_type == 'image':
        return settings.get(key, DEFAULT_IMAGE_MODEL)
    return settings.get(key, DEFAULT_TEXT_MODEL)

# Image Placeholders from .env
DEFAULT_IMAGE_SIZE = os.getenv("DEFAULT_IMAGE_SIZE", "0.5K")
DEFAULT_IMAGE_ASPECT_RATIO = os.getenv("DEFAULT_IMAGE_ASPECT_RATIO", "1:1")

def get_llm(model_name: str = None, temperature: float = 0.7, agent_type: str = None):
    """
    Returns a LangChain ChatOpenAI instance configured for OpenRouter.
    """
    if not model_name:
        if agent_type:
            model_name = get_model_for_agent(agent_type)
        else:
            model_name = DEFAULT_TEXT_MODEL
    clean_client = httpx.Client(timeout=120.0)
    clean_async_client = httpx.AsyncClient(timeout=120.0)
    
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        max_retries=3,
        http_client=clean_client,
        http_async_client=clean_async_client,
        extra_body={
            "reasoning": {"effort": "high"}
        },
        model_kwargs={
            "extra_headers": {
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "MediaPostGenerator",
            }
        }
    )

def safe_invoke(llm, prompt, max_retries=3, delay=2.0):
    """
    Safely invoke the LLM with manual retry logic.
    Handles cases where OpenRouter returns an error inside the JSON payload 
    (which LangChain doesn't automatically retry because it's raised as a ValueError).
    """
    import time
    for attempt in range(max_retries):
        try:
            return llm.invoke(prompt)
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"LLM invoke failed: {str(e)}. Retrying in {delay}s... ({attempt+1}/{max_retries})")
                time.sleep(delay)
            else:
                logger.error(f"LLM invoke failed after {max_retries} attempts.")
                raise e

def generate_image(prompt: str, model: str = None):
    """
    Generate an image using OpenRouter's multimodal chat completion endpoint.
    """
    if model is None:
        if agent_type:
            model = get_model_for_agent(agent_type)
        else:
            model = DEFAULT_IMAGE_MODEL
        
    logger.info(f"Generating image ({DEFAULT_IMAGE_SIZE}, {DEFAULT_IMAGE_ASPECT_RATIO}) with model: {model}")
    
    url = f"{OPENROUTER_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "MediaPostGenerator"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "modalities": ["image"],
        "image_config": {
            "aspect_ratio": DEFAULT_IMAGE_ASPECT_RATIO,
            "image_size": DEFAULT_IMAGE_SIZE
        }
    }
    
    try:
        with httpx.Client() as client:
            response = client.post(url, headers=headers, json=payload, timeout=60.0)
            response.raise_for_status()
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                message = result["choices"][0]["message"]
                if "images" in message and len(message["images"]) > 0:
                    image_url = message["images"][0]["image_url"]["url"]
                    logger.info("Image generated successfully.")
                    return image_url
            
            logger.warning(f"No image found in OpenRouter response: {result}")
            return "https://via.placeholder.com/512x512.png?text=No+Image+In+Response"
            
    except Exception as e:
        logger.error(f"Image generation failed: {str(e)}")
        return "https://via.placeholder.com/512x512.png?text=AI+Image+Gen+Error"

class OpenRouterError(Exception):
    """Custom exception for OpenRouter specific errors."""
    def __init__(self, message, code=None, metadata=None):
        super().__init__(message)
        self.code = code
        self.metadata = metadata

async def stream_llm_response(prompt: str, model_name: str = None, temperature: float = 0.7, agent_type: str = None):
    """
    Streams the LLM response from OpenRouter with detailed error handling (Async).
    Yields tokens (strings).
    """
    if not model_name:
        if agent_type:
            model_name = get_model_for_agent(agent_type)
        else:
            model_name = DEFAULT_TEXT_MODEL
    url = f"{OPENROUTER_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "MediaPostGenerator"
    }
    
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "stream": True,
        "reasoning": {"effort": "high"}
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                # Handle HTTP-level errors (OpenRouter error codes)
                if response.status_code != 200:
                    error_text = await response.aread()
                    error_text = error_text.decode("utf-8")
                    try:
                        error_json = json.loads(error_text)
                        error_msg = error_json.get("error", {}).get("message", error_text)
                        error_code = error_json.get("error", {}).get("code", response.status_code)
                    except:
                        error_msg = error_text
                        error_code = response.status_code
                    
                    logger.error(f"OpenRouter API Error {error_code}: {error_msg}")
                    
                    # Specific handling for OpenRouter codes
                    if error_code == 402:
                        raise OpenRouterError("Insufficient Credits: Vui lòng nạp thêm tiền vào tài khoản OpenRouter.", 402)
                    elif error_code == 429:
                        raise OpenRouterError("Rate Limited: Bạn đã vượt quá giới hạn lượt gọi API. Vui lòng thử lại sau.", 429)
                    elif error_code in [502, 503]:
                        raise OpenRouterError("Provider Error: Model hiện đang bận hoặc gặp sự cố. Vui lòng thử lại.", error_code)
                    else:
                        raise OpenRouterError(f"OpenRouter Error {error_code}: {error_msg}", error_code)

                # Process the stream
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            data_json = json.loads(data_str)
                            
                            # Check for error chunks in the stream
                            if "error" in data_json:
                                error_msg = data_json["error"].get("message", "Unknown stream error")
                                error_code = data_json["error"].get("code", 500)
                                logger.error(f"Stream error {error_code}: {error_msg}")
                                raise OpenRouterError(error_msg, error_code)
                                
                            if "choices" in data_json and len(data_json["choices"]) > 0:
                                delta = data_json["choices"][0].get("delta", {})
                                
                                # Comprehensive check for reasoning tokens (OpenAI, DeepSeek, Google, etc.)
                                reasoning_text = delta.get("reasoning") or delta.get("reasoning_content") or delta.get("thought")
                                if reasoning_text:
                                    yield {"type": "reasoning", "content": reasoning_text}
                                
                                # Standard content
                                if "content" in delta and delta["content"]:
                                    yield {"type": "content", "content": delta["content"]}
                        except json.JSONDecodeError:
                            continue

    except httpx.TimeoutException:
        logger.error("OpenRouter request timed out (408).")
        raise OpenRouterError("Request Timeout: Kết nối tới AI quá lâu, vui lòng thử lại.", 408)
    except httpx.RequestError as e:
        logger.error(f"HTTP Request Error: {str(e)}")
        raise OpenRouterError(f"Connection Error: Không thể kết nối tới OpenRouter. ({str(e)})")

async def safe_stream_invoke(prompt, model_name=None, temperature=0.7, max_retries=2, agent_type=None):
    """
    Wraps stream_llm_response with retry logic and full content aggregation (Async).
    """
    import asyncio
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            async for token in stream_llm_response(prompt, model_name, temperature, agent_type):
                yield token
            return # Success
        except OpenRouterError as e:
            last_error = e
            # Only retry on 408, 502, 503, 429
            if e.code in [408, 502, 503, 429] and attempt < max_retries:
                logger.warning(f"Retrying stream due to error {e.code}... ({attempt+1}/{max_retries})")
                await asyncio.sleep(2)
                continue
            raise e
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(f"Retrying stream due to unexpected error... ({attempt+1}/{max_retries})")
                await asyncio.sleep(2)
                continue
            raise e

def get_openai_client():
    """
    Returns a raw OpenAI client configured for OpenRouter.
    """
    clean_client = httpx.Client()
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
        http_client=clean_client,
    )

