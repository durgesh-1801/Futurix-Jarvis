"""
Futurix Jarvis — MCP (Model Context Protocol) Client.

Provides a foundation for MCP integration, allowing Jarvis to connect to
external MCP servers and expose their tools.  This module implements the
client-side protocol handler and a registry for MCP server configurations.

**Status:** Phase 1 scaffold — ready for future integration with the official
``mcp`` Python SDK when connecting to real MCP servers.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""
    name: str
    url: str
    description: str = ""
    auth_token: Optional[str] = None
    enabled: bool = True
    tools: list[str] = field(default_factory=list)


class MCPClient:
    """Client for connecting to MCP (Model Context Protocol) servers.

    MCP allows Jarvis to integrate with external tool servers, expanding
    its capabilities dynamically without code changes.

    Usage::

        mcp = MCPClient(config_path=Path("config/mcp_servers.json"))
        mcp.load_config()
        servers = mcp.list_servers()
        tools = mcp.get_tools("my_server")
    """

    def __init__(
        self,
        config_path: Path = Path("config/mcp_servers.json"),
        enabled: bool = False,
    ) -> None:
        self._config_path = config_path
        self._enabled = enabled
        self._servers: dict[str, MCPServerConfig] = {}
        self._connected_servers: set[str] = set()

        if self._enabled:
            self.load_config()

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def is_enabled(self) -> bool:
        """Whether MCP is enabled."""
        return self._enabled

    @property
    def server_count(self) -> int:
        """Number of configured MCP servers."""
        return len(self._servers)

    # ── Configuration ────────────────────────────────────────────────────

    def load_config(self) -> None:
        """Load MCP server configurations from the JSON config file."""
        if not self._config_path.exists():
            logger.info("No MCP config found at %s — creating template.", self._config_path)
            self._create_template_config()
            return

        try:
            data = json.loads(self._config_path.read_text(encoding="utf-8"))
            for server_data in data.get("servers", []):
                config = MCPServerConfig(
                    name=server_data["name"],
                    url=server_data.get("url", ""),
                    description=server_data.get("description", ""),
                    auth_token=server_data.get("auth_token"),
                    enabled=server_data.get("enabled", True),
                    tools=server_data.get("tools", []),
                )
                self._servers[config.name] = config

            logger.info("Loaded %d MCP server configs", len(self._servers))

        except Exception as exc:
            logger.error("Failed to load MCP config: %s", exc)

    def _create_template_config(self) -> None:
        """Create a template MCP configuration file."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        template = {
            "servers": [
                {
                    "name": "example_server",
                    "url": "http://localhost:8080",
                    "description": "Example MCP server for demonstration",
                    "enabled": False,
                    "tools": ["example_tool"],
                }
            ]
        }
        self._config_path.write_text(
            json.dumps(template, indent=2), encoding="utf-8"
        )

    # ── Server management ────────────────────────────────────────────────

    def list_servers(self) -> list[dict[str, Any]]:
        """List all configured MCP servers and their status.

        Returns:
            List of server info dicts.
        """
        return [
            {
                "name": cfg.name,
                "url": cfg.url,
                "description": cfg.description,
                "enabled": cfg.enabled,
                "connected": cfg.name in self._connected_servers,
                "tool_count": len(cfg.tools),
            }
            for cfg in self._servers.values()
        ]

    def add_server(self, config: MCPServerConfig) -> None:
        """Register a new MCP server configuration.

        Args:
            config: The server configuration to add.
        """
        self._servers[config.name] = config
        self._save_config()
        logger.info("Added MCP server: %s", config.name)

    def remove_server(self, name: str) -> bool:
        """Remove an MCP server configuration.

        Args:
            name: The server name to remove.

        Returns:
            ``True`` if the server was found and removed.
        """
        if name in self._servers:
            del self._servers[name]
            self._connected_servers.discard(name)
            self._save_config()
            logger.info("Removed MCP server: %s", name)
            return True
        return False

    # ── Connection ───────────────────────────────────────────────────────

    def connect(self, server_name: str) -> bool:
        """Connect to an MCP server (placeholder for real MCP protocol).

        Args:
            server_name: The server to connect to.

        Returns:
            ``True`` if connection was successful.
        """
        config = self._servers.get(server_name)
        if not config:
            logger.error("MCP server not found: %s", server_name)
            return False

        if not config.enabled:
            logger.warning("MCP server '%s' is disabled.", server_name)
            return False

        # TODO: Implement actual MCP protocol connection
        # For now, we just mark it as connected
        logger.info("Connecting to MCP server: %s at %s", server_name, config.url)
        self._connected_servers.add(server_name)
        return True

    def disconnect(self, server_name: str) -> None:
        """Disconnect from an MCP server.

        Args:
            server_name: The server to disconnect from.
        """
        self._connected_servers.discard(server_name)
        logger.info("Disconnected from MCP server: %s", server_name)

    # ── Tool discovery ───────────────────────────────────────────────────

    def get_tools(self, server_name: str) -> list[str]:
        """Get the list of tools provided by an MCP server.

        Args:
            server_name: The server to query.

        Returns:
            List of tool names.
        """
        config = self._servers.get(server_name)
        if not config:
            return []
        return config.tools

    def get_all_tools(self) -> list[dict[str, str]]:
        """Get tools from all connected servers.

        Returns:
            List of dicts with ``server``, ``tool_name``.
        """
        tools = []
        for name in self._connected_servers:
            config = self._servers.get(name)
            if config:
                for tool_name in config.tools:
                    tools.append({"server": name, "tool_name": tool_name})
        return tools

    # ── Persistence ──────────────────────────────────────────────────────

    def _save_config(self) -> None:
        """Persist current server configs to the JSON file."""
        data = {
            "servers": [
                {
                    "name": cfg.name,
                    "url": cfg.url,
                    "description": cfg.description,
                    "auth_token": cfg.auth_token,
                    "enabled": cfg.enabled,
                    "tools": cfg.tools,
                }
                for cfg in self._servers.values()
            ]
        }
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    # ── Status ───────────────────────────────────────────────────────────

    def get_status_summary(self) -> str:
        """Return a human-readable status summary.

        Returns:
            Formatted status string.
        """
        if not self._enabled:
            return "🔌 MCP is disabled. Enable in `.env` with `MCP_ENABLED=true`."

        total = len(self._servers)
        connected = len(self._connected_servers)
        return (
            f"🔗 **MCP Status:** {connected}/{total} servers connected\n"
            + "\n".join(
                f"  {'🟢' if s['connected'] else '⚪'} {s['name']} — {s['description']}"
                for s in self.list_servers()
            )
        )
