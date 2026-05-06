import os
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import logging
import time

# Suppress ChromaDB telemetry errors (must be done before other imports)
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)

# Default embedding function
default_ef = embedding_functions.DefaultEmbeddingFunction()

def get_chroma_client():
    """
    Initialize and return the ChromaDB client with retry logic.
    Connects strictly to the external chroma service.
    """
    chroma_host = os.getenv("CHROMA_HOST", "chroma")
    chroma_port = os.getenv("CHROMA_PORT", "8000")

    # Disable telemetry
    settings = Settings(anonymized_telemetry=False)

    max_retries = 10
    retry_interval = 3

    for i in range(max_retries):
        try:
            logger.info(f"Attempting to connect to ChromaDB (Attempt {i+1}/{max_retries})...")
            client = chromadb.HttpClient(
                host=chroma_host, 
                port=chroma_port,
                settings=settings
            )
            client.heartbeat()
            logger.info("Successfully connected to ChromaDB!")
            return client
        except Exception as e:
            if i < max_retries - 1:
                logger.warning(f"ChromaDB not ready yet, retrying in {retry_interval}s... ({e})")
                time.sleep(retry_interval)
            else:
                logger.error("Could not connect to ChromaDB after multiple attempts.")
                raise e

# Initialize global client
client = get_chroma_client()

def get_collection(collection_name: str):
    return client.get_or_create_collection(
        name=collection_name,
        embedding_function=default_ef
    )

def add_post_to_memory(post_id: str, content: str, metadata: dict):
    try:
        collection = get_collection("posts_history")
        collection.add(
            documents=[content],
            metadatas=[metadata],
            ids=[post_id]
        )
    except Exception as e:
        logger.error(f"Failed to add post to memory: {e}")

def search_past_posts(query: str, n_results: int = 3):
    try:
        collection = get_collection("posts_history")
        if collection.count() == 0:
            return {"documents": [[]], "metadatas": [[]]}
            
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count())
        )
        return results
    except Exception as e:
        logger.error(f"Failed to search past posts: {e}")
        return {"documents": [[]], "metadatas": [[]]}

def add_feedback_to_memory(feedback_id: str, feedback_text: str, metadata: dict):
    try:
        collection = get_collection("human_feedback")
        collection.add(
            documents=[feedback_text],
            metadatas=[metadata],
            ids=[feedback_id]
        )
    except Exception as e:
        logger.error(f"Failed to add feedback to memory: {e}")

def search_past_feedback(query: str, n_results: int = 3):
    try:
        collection = get_collection("human_feedback")
        if collection.count() == 0:
            return {"documents": [[]], "metadatas": [[]]}
            
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count())
        )
        return results
    except Exception as e:
        logger.error(f"Failed to search past feedback: {e}")
        return {"documents": [[]], "metadatas": [[]]}
