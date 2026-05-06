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

# Image Placeholders from .env
DEFAULT_IMAGE_SIZE = os.getenv("DEFAULT_IMAGE_SIZE", "0.5K")
DEFAULT_IMAGE_ASPECT_RATIO = os.getenv("DEFAULT_IMAGE_ASPECT_RATIO", "1:1")

def get_llm(model_name: str = DEFAULT_TEXT_MODEL, temperature: float = 0.7):
    """
    Returns a LangChain ChatOpenAI instance configured for OpenRouter.
    """
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
