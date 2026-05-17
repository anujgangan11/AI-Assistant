import asyncio
import json
import logging

logger = logging.getLogger(__name__)

_RH_MCP_DIR = "/users/anuj/mcpServers/RH-mcp"

_RH_SERVER = {
    "command": "/Users/anuj/.local/bin/uv",
    "args": [
        "--directory", _RH_MCP_DIR,
        "run", "python", "main.py",
        "--name", "anuj",
    ],
    "transport": "stdio",
}


async def _with_tools(coro_fn):
    """Run coro_fn(tools_dict) inside one live MCP session."""
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_mcp_adapters.tools import load_mcp_tools

    client = MultiServerMCPClient({"robinhood": _RH_SERVER})
    async with client.session("robinhood") as session:
        tool_list = await load_mcp_tools(session)
        tools = {t.name: t for t in tool_list}
        return await coro_fn(tools)


async def fetch_stock_data(ticker: str) -> dict[str, str]:
    """Fetch fundamentals, ratings, earnings, and news in one MCP session."""

    async def _fetch(tools: dict) -> dict[str, str]:
        async def _invoke(key: str, args: dict) -> tuple[str, str]:
            tool = tools.get(key)
            if tool is None:
                logger.warning("RH MCP: tool %s not found", key)
                return key, ""
            try:
                result = await tool.ainvoke(args)
                return key, result if isinstance(result, str) else json.dumps(result)
            except Exception as e:
                logger.warning("RH MCP: %s failed for %s: %s", key, ticker, e)
                return key, ""

        sym = {"request": {"symbol": ticker}}
        pairs = await asyncio.gather(
            _invoke("get_fundamentals", sym),
            _invoke("get_ratings", sym),
            _invoke("get_earnings", sym),
            _invoke("get_news", sym),
        )
        return dict(pairs)

    return await _with_tools(_fetch)


async def fetch_portfolio() -> str:
    """Fetch the user's full portfolio summary."""

    async def _fetch(tools: dict) -> str:
        tool = tools.get("get_portfolio")
        if tool is None:
            return ""
        try:
            result = await tool.ainvoke({})
            return result if isinstance(result, str) else json.dumps(result)
        except Exception as e:
            logger.warning("RH MCP: get_portfolio failed: %s", e)
            return ""

    return await _with_tools(_fetch)
