"""ai4ra: research-administration skills and guides, with one tool, ai4ra_guide, that serves them.

The skills here (an RFA sheet, a narrative, a work plan, a budget outline and the NSF budget form,
a PI memo, udm-sheet, the cost-allowability checks and budget-justification prompts copied from
AI4RA/prompt-library) are institution-agnostic text. They use the document tools of whatever client
runs them and, where they read the web or the UDM, the general and udm servers' tools. A client that lists this server
gets its catalog and its prompts; there is nothing to call.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.skills import register_prompts

mcp = MCPServer(
    "ai4ra",
    instructions="Research-administration skills and guides (an RFA record, a narrative, a work plan, a budget outline, the NSF budget form, a UDM sheet, cost checks). ai4ra_guide lists the guides and returns one by name; fetch the guide that covers the job before doing it.",
)

SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
