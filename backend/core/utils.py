import os
import base64
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def save_llm_output(agent_name: str, prompt: str, response: str, extension: str = "txt"):
    """
    Saves LLM prompt and output to the /app/tmp directory.
    """
    tmp_dir = "/app/tmp"
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{agent_name}.{extension}"
    filepath = os.path.join(tmp_dir, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=== PROMPT ===\n")
        f.write(prompt)
        f.write("\n\n=== RESPONSE ===\n")
        f.write(response)
    
    return filepath

def save_image_from_url(image_url: str, agent_name: str = "generated_image"):
    """
    Saves an image (Base64 or HTTP URL) to the /app/tmp directory.
    """
    tmp_dir = "/app/tmp"
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir, exist_ok=True)
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{agent_name}.png"
    filepath = os.path.join(tmp_dir, filename)
    
    try:
        if image_url.startswith("data:image"):
            # Handle Base64 Data URL
            header, encoded = image_url.split(",", 1)
            data = base64.b64decode(encoded)
            with open(filepath, "wb") as f:
                f.write(data)
        elif image_url.startswith("http"):
            # Handle standard URL
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(response.content)
        else:
            print(f"Unknown image URL format: {image_url[:50]}...")
            return None
            
        return filepath
    except Exception as e:
        print(f"Failed to save image to tmp: {e}")
        return None
def save_image_to_outputs(image_url: str, filename: str):
    """
    Saves an image to the backend's assets/generated_images directory.
    Returns the URL path (e.g., /outputs/xxx.png).
    """
    output_dir = "assets/generated_images"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        
    filepath = os.path.join(output_dir, filename)
    
    try:
        if image_url.startswith("data:image"):
            header, encoded = image_url.split(",", 1)
            data = base64.b64decode(encoded)
            with open(filepath, "wb") as f:
                f.write(data)
        elif image_url.startswith("http"):
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(response.content)
        elif os.path.exists(image_url):
            # If it's a local file (like the placeholder)
            import shutil
            shutil.copy(image_url, filepath)
        else:
            logger.error(f"Unknown image URL format or file not found: {image_url[:50]}")
            return None
            
        return f"/outputs/{filename}"
    except Exception as e:
        logger.error(f"Failed to save image to outputs: {e}")
        return None

