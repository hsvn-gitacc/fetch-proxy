"""
Simple fetch proxy for Product Hunt email harvesting.

Deploy this to Railway / Render / Fly.io / any VPS, then point
ph_harvest_emails.py at it with --proxy-base.

    GET /fetch?url=<target>&token=<secret>  -> raw HTML of target page

Why: the runtime's website permission gate prompts per new domain.
Routing all fetches through ONE proxy domain means only one approval.
Unlike r.jina.ai (returns stripped markdown), this returns raw HTML
so email extraction keeps the ~37% direct-fetch yield.

Security: requires PROXY_TOKEN env var. Requests without the token
get 403. Do not expose without a token.
"""

import os
import urllib.parse

import requests
from flask import Flask, request, Response

app = Flask(__name__)

TOKEN = os.environ.get("PROXY_TOKEN", "")
TIMEOUT = int(os.environ.get("FETCH_TIMEOUT", "20"))
MAX_BYTES = int(os.environ.get("MAX_BYTES", str(2 * 1024 * 1024)))

UA = {"User-Agent": "Mozilla/5.0 (compatible; lead-check/1.0)"}

# never fetch these (avoid loops / internal)
BLOCKED_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "::1")


@app.get("/fetch")
def fetch():
    if not TOKEN or request.args.get("token") != TOKEN:
        return {"error": "forbidden"}, 403

    target = request.args.get("url", "")
    if not target.startswith(("http://", "https://")):
        return {"error": "url must start with http(s)://"}, 400

    host = urllib.parse.urlparse(target).netloc.lower().split(":")[0]
    if host in BLOCKED_HOSTS or host.endswith(".internal"):
        return {"error": "blocked host"}, 403

    try:
        r = requests.get(target, headers=UA, timeout=TIMEOUT,
                         allow_redirects=True, stream=True)
        r.raise_for_status()
        chunks, size = [], 0
        for chunk in r.iter_content(chunk_size=65536):
            size += len(chunk)
            if size > MAX_BYTES:
                break
            chunks.append(chunk)
        body = b"".join(chunks)
        ctype = r.headers.get("Content-Type", "text/html")
        return Response(body, content_type=ctype,
                        headers={"X-Proxy-Final-URL": r.url})
    except requests.Timeout:
        return {"error": "target timeout"}, 504
    except requests.RequestException as e:
        return {"error": f"fetch failed: {str(e)[:120]}"}, 502


@app.get("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
