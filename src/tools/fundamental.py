import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def fetch_fundamentals(ticker: str) -> dict[str, Any]:
    """Pull key fundamental data from Yahoo Finance for a given ticker."""
    def _sync_fetch():
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info or {}
        return {
            "name": info.get("longName") or info.get("shortName", ticker),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "eps_ttm": info.get("trailingEps"),
            "revenue_ttm": info.get("totalRevenue"),
            "gross_margin": info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "net_margin": info.get("profitMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "roe": info.get("returnOnEquity"),
            "analyst_rating": info.get("recommendationKey", "N/A"),
            "target_mean_price": info.get("targetMeanPrice"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
        }

    try:
        return await asyncio.to_thread(_sync_fetch)
    except Exception as e:
        logger.warning("yfinance fetch failed for %s: %s", ticker, e)
        return {}


async def fetch_news(ticker: str, company_name: str) -> str:
    """Fetch recent news about the company via Tavily."""
    from src.config import settings
    from tavily import AsyncTavilyClient

    query = f"{company_name} ({ticker}) stock news financials earnings 2025"
    try:
        client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
        result = await client.search(query=query, search_depth="basic", max_results=4)
        snippets = [r.get("content", "") for r in result.get("results", [])]
        return "\n\n".join(snippets)
    except Exception as e:
        logger.warning("Tavily fetch failed for %s: %s", ticker, e)
        return ""


def format_fundamentals(data: dict[str, Any]) -> str:
    """Convert the fundamentals dict into a compact text block for the LLM."""
    def fmt_num(v, prefix="", suffix="", scale=1):
        if v is None:
            return "N/A"
        v = v / scale
        if v >= 1e9:
            return f"{prefix}{v/1e9:.2f}B{suffix}"
        if v >= 1e6:
            return f"{prefix}{v/1e6:.2f}M{suffix}"
        return f"{prefix}{v:.2f}{suffix}"

    def pct(v):
        return f"{v*100:.1f}%" if v is not None else "N/A"

    lines = [
        f"Company: {data.get('name', 'N/A')} | Sector: {data.get('sector', 'N/A')} | Industry: {data.get('industry', 'N/A')}",
        f"Price: {fmt_num(data.get('current_price'), prefix='$')} | 52w: {fmt_num(data.get('52w_low'), prefix='$')} – {fmt_num(data.get('52w_high'), prefix='$')}",
        f"Market Cap: {fmt_num(data.get('market_cap'))} | Revenue (TTM): {fmt_num(data.get('revenue_ttm'))}",
        f"P/E (TTM): {fmt_num(data.get('pe_ratio'))} | Forward P/E: {fmt_num(data.get('forward_pe'))} | EPS (TTM): {fmt_num(data.get('eps_ttm'), prefix='$')}",
        f"Gross Margin: {pct(data.get('gross_margin'))} | Op Margin: {pct(data.get('operating_margin'))} | Net Margin: {pct(data.get('net_margin'))}",
        f"D/E: {fmt_num(data.get('debt_to_equity'))} | Current Ratio: {fmt_num(data.get('current_ratio'))} | ROE: {pct(data.get('roe'))}",
        f"Analyst Rating: {data.get('analyst_rating', 'N/A')} | Target Price: {fmt_num(data.get('target_mean_price'), prefix='$')}",
    ]
    return "\n".join(lines)
