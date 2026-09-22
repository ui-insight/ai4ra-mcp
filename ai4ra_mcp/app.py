"""One process, several MCP servers, each at its own path.

    /<server>/mcp       the server's streamable-HTTP endpoint
    /<server>/skills/   its skills folder as static files (catalog.json, components/)
    /                   a JSON index of what is mounted

Run every server with `ai4ra-mcp`, a subset with `--only NAME`, or one server
over stdio with `--stdio NAME` for a local MCP client.
"""

from __future__ import annotations

import argparse
import os
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from ai4ra_mcp.common.http import request_key
from ai4ra_mcp.servers.ai4ra.server import mcp as ai4ra
from ai4ra_mcp.servers.ecfr.server import mcp as ecfr
from ai4ra_mcp.servers.fac.server import mcp as fac
from ai4ra_mcp.servers.grants.server import mcp as grants
from ai4ra_mcp.servers.nih.server import mcp as nih
from ai4ra_mcp.servers.nsf.server import mcp as nsf
from ai4ra_mcp.servers.sam.server import mcp as sam
from ai4ra_mcp.servers.uidaho.server import mcp as uidaho

SERVERS: dict[str, MCPServer] = {"ecfr": ecfr, "grants": grants, "uidaho": uidaho, "ai4ra": ai4ra,
                                 "nih": nih, "nsf": nsf, "sam": sam, "fac": fac}
SERVERS_DIR = Path(__file__).parent / "servers"


class BearerKeyMiddleware:
    """Reads `Authorization: Bearer <token>` and makes it this request's upstream key (see
    common.http.request_key). The token is held for the request only and never logged."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        token = None
        if scope["type"] == "http":
            for name, value in scope.get("headers") or []:
                if name == b"authorization":
                    v = value.decode("latin-1").strip()
                    if v[:7].lower() == "bearer " and v[7:].strip():
                        token = v[7:].strip()
                    break
        reset = request_key.set(token)
        try:
            await self.app(scope, receive, send)
        finally:
            request_key.reset(reset)


def _transport_security() -> TransportSecuritySettings:
    """Behind a reverse proxy the Host header is the public name, so DNS-rebinding
    protection is off unless AI4RA_MCP_HOSTS lists the names to allow."""
    hosts = [h.strip() for h in os.environ.get("AI4RA_MCP_HOSTS", "").split(",") if h.strip()]
    if hosts:
        return TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=["*"])
    return TransportSecuritySettings(enable_dns_rebinding_protection=False)


def build_app(only: list[str] | None = None) -> Starlette:
    names = only or list(SERVERS)
    unknown = [n for n in names if n not in SERVERS]
    if unknown:
        raise SystemExit(f"unknown server {', '.join(unknown)}; choose from {', '.join(SERVERS)}")
    security = _transport_security()
    routes, mounted = [], []
    for name in names:
        server = SERVERS[name]
        skills = SERVERS_DIR / name / "skills"
        if skills.is_dir():
            routes.append(Mount(f"/{name}/skills", app=StaticFiles(directory=str(skills)), name=f"{name}-skills"))
        routes.append(Mount(f"/{name}", app=server.streamable_http_app(json_response=True, stateless_http=True, transport_security=security)))
        mounted.append(name)

    async def index(_request):
        out = []
        for name in mounted:
            tools = await SERVERS[name].list_tools()
            prompts = await SERVERS[name].list_prompts()
            out.append({"name": name, "mcp": f"/{name}/mcp", "skills": f"/{name}/skills/catalog.json",
                        "tools": [t.name for t in tools], "prompts": [p.name for p in prompts]})
        return JSONResponse({"servers": out})

    routes.append(Route("/", index))

    @asynccontextmanager
    async def lifespan(_app):
        async with AsyncExitStack() as stack:
            for name in mounted:
                await stack.enter_async_context(SERVERS[name].session_manager.run())
            yield

    middleware = [Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], expose_headers=["Mcp-Session-Id"]),
                  Middleware(BearerKeyMiddleware)]
    return Starlette(routes=routes, lifespan=lifespan, middleware=middleware)


def main() -> None:
    parser = argparse.ArgumentParser(prog="ai4ra-mcp", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default=os.environ.get("AI4RA_MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AI4RA_MCP_PORT", "8000")))
    parser.add_argument("--only", action="append", metavar="NAME", help="mount only this server (repeatable)")
    parser.add_argument("--stdio", metavar="NAME", help="run one server over stdio instead of HTTP")
    args = parser.parse_args()
    if args.stdio:
        if args.stdio not in SERVERS:
            raise SystemExit(f"unknown server {args.stdio}; choose from {', '.join(SERVERS)}")
        SERVERS[args.stdio].run("stdio")
        return
    import uvicorn

    uvicorn.run(build_app(args.only), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
