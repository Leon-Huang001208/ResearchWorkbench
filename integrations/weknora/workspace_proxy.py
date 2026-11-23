"""Adapt the existing native nginx frontend for the RWB full workspace.

Only WeKnora's native OIDC nonce cookie may cross its API proxy. RWB's
HttpOnly browser session is never forwarded, nor may an upstream set it.
"""

import re

from app.research_web.multiuser.origin import validate_origin


def configure_workspace(source: str, rwb_origin: str) -> str:
    validate_origin(rwb_origin)
    if "# RWB full workspace cookie boundary" in source:
        raise ValueError("workspace_proxy_already_configured")
    # The embedding/identity server is the existing port-80 frontend. The
    # sealed embedding relay server, if present, is deliberately left intact.
    marker = "server {\n    listen 80;"
    if source.count(marker) != 1:
        raise ValueError("weknora_frontend_server_not_found")
    start = source.index(marker)
    following = source.find("\nserver {", start + len(marker))
    end = following if following >= 0 else len(source)
    server = source[start:end]
    if "proxy_pass http://app:8080" not in server:
        raise ValueError("weknora_backend_not_found")
    server = server.replace(
        "    listen 80;",
        """    listen 80;
    location = /rwb-fingpt.mjs {
        root /usr/share/nginx/html;
        default_type application/javascript;
    }""",
        1,
    )
    frame = f"add_header Content-Security-Policy \"frame-ancestors 'self' {rwb_origin}\" always;"
    server = server.replace('add_header X-Frame-Options "SAMEORIGIN" always;', frame)
    server = server.replace(
        "proxy_set_header X-Forwarded-Proto $scheme;", "proxy_set_header X-Forwarded-Proto https;"
    )
    server = re.sub(
        r"(\s*proxy_pass http://app:8080[^;]*;)",
        r"\1\n        proxy_set_header Cookie $rwb_weknora_cookie;"
        r"\n        proxy_hide_header Set-Cookie;"
        r"\n        add_header Set-Cookie $rwb_weknora_set_cookie always;",
        server,
    )
    # api-proxy.conf also contains the proto setting: place this after its
    # include via a separate reviewed copy during installation, not duplicates.
    maps = """# RWB full workspace cookie boundary
map $cookie_weknora_oidc_nonce $rwb_weknora_cookie {
    default "weknora_oidc_nonce=$cookie_weknora_oidc_nonce";
    "" "";
}
map $upstream_http_set_cookie $rwb_weknora_set_cookie {
    default "";
    ~^weknora_oidc_nonce= $upstream_http_set_cookie;
}
"""
    return maps + source[:start] + server + source[end:]
