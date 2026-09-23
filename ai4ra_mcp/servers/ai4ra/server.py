"""ai4ra: research-administration skills, with no tools of their own.

The skills here (an RFA sheet, a narrative, a work plan, a budget outline and the NSF budget form,
a PI memo, the cost-allowability checks and budget-justification prompts copied from
AI4RA/prompt-library) are institution-agnostic text. They use the document tools of whatever client
runs them and, where they read the web, the general server's tools. A client that lists this server
gets its catalog and its prompts; there is nothing to call.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.skills import register_prompts

mcp = MCPServer(
    "ai4ra",
    instructions="Research-administration skills (proposal sheets, budgets, cost checks). No tools: each skill is a prompt that works with the client's own document tools.",
)

SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
