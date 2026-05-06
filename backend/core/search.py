import os
from langchain_community.tools.tavily_search import TavilySearchResults
from dotenv import load_dotenv

load_dotenv()

def get_search_tool():
    """
    Returns a LangChain Tool for Tavily Web Search.
    Make sure TAVILY_API_KEY is set in the environment.
    """
    # Ensure the API key is present
    if not os.getenv("TAVILY_API_KEY"):
        raise ValueError("TAVILY_API_KEY is not set in the environment variables.")
        
    search = TavilySearchResults(max_results=3)
    return search

def direct_search(query: str, max_results: int = 3):
    """
    A direct Python function to call Tavily without LangChain wrapper,
    useful if we want fine-grained control over the search results.
    """
    from tavily import TavilyClient
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    response = client.search(query=query, max_results=max_results, search_depth="advanced")
    return response
