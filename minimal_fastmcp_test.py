#!/usr/bin/env python3
"""Minimal FastMCP test."""

from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("test")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

print(f"Tools registered: {len(mcp._tools)}")
for tool in mcp._tools:
    print(f"  - {tool.name}")

if __name__ == "__main__":
    mcp.run()