"""ai4ra: the catch-all server for what belongs to no single upstream.

Today that is one tool, the page reader. Anything else AI4RA provides that is
not tied to ecfr.gov, grants.gov or one institution goes here too.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common import fetch as _fetch
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}

mcp = MCPServer(
    "ai4ra",
    instructions="AI4RA's general tools. fetch_document reads any public web page or PDF as text, in pages.",
)


@mcp.tool(name="fetch_document", annotations=_READ_ONLY)
async def fetch_document(url: str, offset: int = 0, max_chars: int = 12000) -> dict:
    """Read any public web page or PDF by its URL and return its text.

    Use it to look up a website the user names, a funding announcement, a policy page or a sponsor
    guide, when the user gives a link instead of pasting text. NSF and other script-rendered pages
    have no text: ask for the PDF link. Long documents come back in pages: when the result says
    truncated, call again with offset = next_offset. When replying, include the url as a markdown
    link so the person can open the original. Fetch only addresses the user gave, that a tool
    returned, or that you know exactly; never guess a path, and on a 404 do not try others.

    Args:
        url: The http(s) address of the page or PDF.
        offset: Character position to start from. Default 0.
        max_chars: Characters to return, 1000-40000. Default 12000.
    Returns: url, kind (html, pdf, text, grants.gov), title, total_chars, offset, returned_chars,
    truncated, next_offset and text; or an error.
    """
    return await _fetch.fetch_document(url, offset=offset, max_chars=max_chars)


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
