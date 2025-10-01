#!/usr/bin/env python3
"""Minimal FastMCP test server."""

from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("test")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

print("FastMCP server starting with tools...")
if __name__ == "__main__":
    mcp.run()