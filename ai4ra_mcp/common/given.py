"""Which arguments of a server's tools name a thing the server holds, and which tool lists the values.

A model that has read two sections can call for a third by a CRN it made up; the server answers for that
section, since nothing here can know what the model should have read (mindrouter-365 #72: 46932 invented
for classes_section, 2026-10-14). The client's rule is that an argument naming a thing outside the document
must have been given by the person or by an earlier tool result, or the call is not sent. Which arguments
those are is a fact about the server, the shape of a correct call, so each server states it beside its tools:

    given(mcp, {"classes_section": {"term": "classes_terms", "crn": "classes_search"}})

and the index at `/` carries it as `given` on the server's entry, a sibling of `tools`. The value names the
tool on the same server whose results carry the identifier (the one a person is told to read first), never
a method and never a client's field. What a client does with it is the client's; a server with no such
argument states nothing. Left out on purpose is anything a person expects a model to infer, a subject code
from "biology" or a CFR citation from the rule's name (#40).
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

_GIVEN: dict[MCPServer, dict[str, dict[str, str]]] = {}


def given(server: MCPServer, table: dict[str, dict[str, str]]) -> None:
    """States the table for one server: tool name to {argument: the tool that lists its values}."""
    _GIVEN[server] = table


def given_of(server: MCPServer) -> dict[str, dict[str, str]]:
    """The server's table, empty when it stated none."""
    return _GIVEN.get(server, {})
