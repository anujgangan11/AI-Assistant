import asyncio
import json
import logging
from typing import Any

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
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_mcp_adapters.tools import load_mcp_tools

    client = MultiServerMCPClient({"robinhood": _RH_SERVER})
    async with client.session("robinhood") as session:
        tool_list = await load_mcp_tools(session)
        tools = {t.name: t for t in tool_list}
        return await coro_fn(tools)


async def fetch_stock_data(ticker: str) -> dict[str, Any]:
    """Fetch and format fundamentals, ratings, earnings, and quotes in one MCP session."""

    async def _fetch(tools: dict) -> dict[str, Any]:
        async def _invoke(key: str, args: dict):
            tool = tools.get(key)
            if tool is None:
                logger.warning("RH MCP: tool %s not found", key)
                return key, None
            try:
                result = await tool.ainvoke(args)
                parsed = json.loads(result) if isinstance(result, str) else result
                return key, parsed
            except Exception as e:
                logger.warning("RH MCP: %s failed for %s: %s", key, ticker, e)
                return key, None

        sym = {"request": {"symbol": ticker}}
        pairs = await asyncio.gather(
            _invoke("get_fundamentals", sym),
            _invoke("get_ratings", sym),
            _invoke("get_earnings", sym),
            _invoke("get_quotes", sym),
        )
        return dict(pairs)

    return await _with_tools(_fetch)


async def fetch_portfolio() -> str:
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


def _fmt(val, prefix="", suffix="", scale=1):
    if val is None:
        return "N/A"
    try:
        v = float(val) / scale
        if abs(v) >= 1e9:
            return f"{prefix}{v/1e9:.2f}B{suffix}"
        if abs(v) >= 1e6:
            return f"{prefix}{v/1e6:.2f}M{suffix}"
        return f"{prefix}{v:.2f}{suffix}"
    except (TypeError, ValueError):
        return str(val)


def format_stock_data(ticker: str, data: dict[str, Any]) -> str:
    """Convert raw Robinhood API responses into a compact, LLM-readable text block."""
    lines = [f"=== {ticker} FUNDAMENTALS ==="]

    # Quotes — current price
    quotes = data.get("get_quotes")
    if quotes and isinstance(quotes, list) and quotes[0]:
        q = quotes[0]
        price = q.get("last_trade_price") or q.get("last_extended_hours_trade_price")
        lines.append(f"Current Price: {_fmt(price, '$')}")

    # Fundamentals
    funds = data.get("get_fundamentals")
    if funds and isinstance(funds, list) and funds[0]:
        f = funds[0]
        lines += [
            f"52w Range: {_fmt(f.get('low_52_weeks'), '$')} – {_fmt(f.get('high_52_weeks'), '$')}",
            f"Market Cap: {_fmt(f.get('market_cap'))}  |  P/E: {_fmt(f.get('pe_ratio'))}  |  P/B: {_fmt(f.get('pb_ratio'))}",
            f"Dividend Yield: {_fmt(f.get('dividend_yield'), suffix='%')}",
            f"Sector: {f.get('sector','N/A')}  |  Industry: {f.get('industry','N/A')}",
            f"Employees: {f.get('num_employees','N/A')}  |  Founded: {f.get('year_founded','N/A')}",
        ]
        desc = f.get("description", "")
        if desc:
            lines.append(f"Description: {desc[:400]}{'...' if len(desc) > 400 else ''}")

    # Ratings
    ratings = data.get("get_ratings")
    if ratings and isinstance(ratings, dict):
        s = ratings.get("summary", {})
        buy, hold, sell = s.get("num_buy_ratings", 0), s.get("num_hold_ratings", 0), s.get("num_sell_ratings", 0)
        total = buy + hold + sell or 1
        lines.append(f"\n=== ANALYST RATINGS ===")
        lines.append(f"Buy: {buy} ({buy/total:.0%})  Hold: {hold} ({hold/total:.0%})  Sell: {sell} ({sell/total:.0%})")
        recent = ratings.get("ratings", [])[:3]
        for r in recent:
            lines.append(f"  • {r.get('published_at','')[:10]}  {r.get('firm_name','?')}  →  {r.get('type','?')}  (was: {r.get('previous_type','?')})")

    # Earnings
    earnings = data.get("get_earnings")
    if earnings and isinstance(earnings, list):
        lines.append(f"\n=== RECENT EARNINGS ===")
        for e in earnings[:4]:
            eps = e.get("eps", {}) or {}
            actual = eps.get("actual")
            est = eps.get("estimate")
            beat = ""
            if actual is not None and est is not None:
                try:
                    beat = " ✓ beat" if float(actual) > float(est) else " ✗ missed"
                except (ValueError, TypeError):
                    pass
            lines.append(f"  {e.get('year')} Q{e.get('quarter')}: EPS actual={_fmt(actual,'$')} est={_fmt(est,'$')}{beat}")

    return "\n".join(lines)
