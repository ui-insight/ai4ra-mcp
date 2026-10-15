"""github: the two skills for a GitHub repository, over GitHub's own MCP server.

No tools of its own beyond github_guide: code-change and actions-check name the tools of GitHub's remote MCP server
in their requires (get_me, get_file_contents, create_branch, push_files, create_pull_request, actions_list, actions_get,
get_job_logs and the rest), which this process does not serve. A browser client reaches that server through a proxy
on its own host. This server exists so the skills stand beside GitHub's tools and not under general: its index entry
carries institution "GitHub", the same value a client gives GitHub's own server, so the two fold together (#42 holds
the other shape, a keyed server over the REST API with tools of its own).
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.skills import register_prompts

mcp = MCPServer(
    "github",
    instructions="Skills for a GitHub repository through GitHub's own MCP server: code-change (a described change as a pull request on an agent branch, never the default branch, never merged) and actions-check (one look at the Actions runs and the first real error of each failure). github_guide lists them and returns one by name; the tools they call are GitHub's.",
)

SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
