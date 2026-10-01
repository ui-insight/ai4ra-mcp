"""ai4ra: research-administration guides and prompts, with one tool, ai4ra_guide, that serves them.

The guides here (an RFA record, a narrative, a work plan, a budget outline, the NSF budget form) say what a
correct result is and name no client; the compliance-concerns guide is a vocabulary for grouping statements, with
no citations; the cost-allowability checks and budget-justification prompts are copied from AI4RA/prompt-library. Any client places the result with its own tools; the udm server's guide is fetched
the same way. A client that lists this server gets its catalog, its prompts and the guide tool.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.skills import register_prompts

mcp = MCPServer(
    "ai4ra",
    instructions="Research-administration skills and guides (an RFA record, a narrative, a work plan, a budget outline, the NSF budget form, the compliance-concerns vocabulary, cost checks). ai4ra_guide lists the guides and returns one by name; fetch the guide that covers the job before doing it.",
)

SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
