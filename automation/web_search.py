"""
Futurix Jarvis — Web Search Tools.

LangChain tools that open the default browser to perform searches on
Google and YouTube.
"""

from __future__ import annotations

import logging
import urllib.parse
import webbrowser

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def search_google(query: str) -> str:
    """Search Google for a query in the default web browser.

    Args:
        query: The search terms to look up on Google.
    """
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}"
        webbrowser.open(url)
        logger.info("Google search: %s", query)
        return f"🔍 Opened Google search for: **{query}**"
    except Exception as exc:
        return f"❌ Failed to search Google: {exc}"


@tool
def search_youtube(query: str) -> str:
    """Search YouTube for a query in the default web browser.

    Args:
        query: The search terms to look up on YouTube.
    """
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        webbrowser.open(url)
        logger.info("YouTube search: %s", query)
        return f"🎥 Opened YouTube search for: **{query}**"
    except Exception as exc:
        return f"❌ Failed to search YouTube: {exc}"


@tool
def open_url(url: str) -> str:
    """Open a URL in the default web browser.

    Args:
        url: The full URL to open (must start with http:// or https://).
    """
    try:
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        webbrowser.open(url)
        logger.info("Opened URL: %s", url)
        return f"🌐 Opened: **{url}**"
    except Exception as exc:
        return f"❌ Failed to open URL: {exc}"


def get_web_search_tools() -> list:
    """Return all web-search tools for agent registration."""
    return [search_google, search_youtube, open_url]
