# TODO (slice 2): Implement web search tool

from langchain_core.tools import tool
from src.config import settings


@tool
async def web_search(query: str) -> str:
    """Search the web and return a summary of results."""
    from tavily import TavilyClient

    client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    result = client.search(query=query, search_depth="advanced", max_results=5)
    snippets = [r.get("content", "") for r in result.get("results", [])]
    return "\n\n".join(snippets)
