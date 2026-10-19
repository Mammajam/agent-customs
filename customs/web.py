"""Public dashboard: evaluation numbers and a "try a package" box.

Standard library only, so it runs anywhere the checkpoint runs. Served with:

    python3 -m customs.web            # http://127.0.0.1:8000

GET  /        dashboard with the latest evaluation numbers and the try box
POST /check   run the checkpoint on the submitted command and show the verdict
"""

from __future__ import annotations

import html
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from customs.checkpoint import check_command, overall
from customs.verdict import Verdict

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "results.json"
MAX_COMMAND_CHARS = 500

STYLE = """
:root { color-scheme: light dark; --fg:#1d1d1f; --bg:#fff; --muted:#6e6e73; --card:#f5f5f7;
  --block:#c62828; --inspect:#b26a00; --clear:#2e7d32; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --fg:#f5f5f7; --bg:#1d1d1f;
  --muted:#a1a1a6; --card:#2c2c2e; } }
:root[data-theme="dark"] { --fg:#f5f5f7; --bg:#1d1d1f; --muted:#a1a1a6; --card:#2c2c2e; }
body { margin:0; padding:16px; font:16px/1.5 system-ui,sans-serif; background:var(--bg); color:var(--fg); }
main { max-width:720px; margin:0 auto; }
h1 { font-size:1.6rem; margin:.5rem 0; }
.card { background:var(--card); border-radius:12px; padding:16px; margin:12px 0; }
.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; }
.stat b { display:block; font-size:1.6rem; }
.muted { color:var(--muted); font-size:.9rem; }
input[type=text] { width:100%; box-sizing:border-box; padding:10px; font:inherit; border-radius:8px;
  border:1px solid var(--muted); background:var(--bg); color:var(--fg); }
button { margin-top:8px; padding:10px 16px; font:inherit; border:0; border-radius:8px; background:#0071e3; color:#fff; }
.v-BLOCK { color:var(--block); font-weight:700; } .v-INSPECT { color:var(--inspect); font-weight:700; }
.v-CLEAR { color:var(--clear); font-weight:700; }
code { word-break:break-all; }
"""


def _load_results() -> dict | None:
    try:
        return json.loads(RESULTS.read_text())["summary"]
    except (OSError, ValueError, KeyError):
        return None


def _pct(value) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def render_stats(summary: dict | None) -> str:
    if summary is None:
        return '<p class="muted">No evaluation run yet. Run evaluation/run_eval.py.</p>'
    return f"""
<div class="stats">
  <div class="card stat">Catch rate<b>{_pct(summary['catch_rate'])}</b>
    <span class="muted">{summary['caught']} of {summary['attacks']} fabricated names</span></div>
  <div class="card stat">False-block rate<b>{_pct(summary['false_block_rate'])}</b>
    <span class="muted">{summary['false_blocks']} of {summary['clean']} established packages</span></div>
  <div class="card stat">Median latency<b>{summary['latency_ms_median']:.0f} ms</b>
    <span class="muted">p95 {summary['latency_ms_p95']:.0f} ms</span></div>
</div>
<p class="muted">Run {html.escape(summary['run_at'])} over {summary['cases']} labelled commands.</p>"""


def render_verdict(command: str) -> str:
    decisions = check_command(command)
    if not decisions:
        return '<div class="card">No install, clone or skill fetch found in that command.</div>'
    verdict = overall(decisions)
    rows = []
    for d in decisions:
        reasons = "".join(f"<li>{html.escape(r)}</li>" for r in d.reasons)
        hint = f"<p>Did you mean <code>{html.escape(d.suggestion)}</code>?</p>" if d.suggestion else ""
        rows.append(
            f'<p><span class="v-{d.verdict.value.upper()}">{d.verdict.value.upper()}</span> '
            f'{html.escape(d.declaration.ecosystem.value)} <code>{html.escape(d.declaration.name)}</code></p>'
            f"<ul>{reasons}</ul>{hint}"
        )
    return (f'<div class="card"><p>Overall: <span class="v-{verdict.value.upper()}">'
            f'{verdict.value.upper()}</span></p>{"".join(rows)}</div>')


def page(command: str = "", result_html: str = "") -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Customs dashboard</title><style>{STYLE}</style></head>
<body><main>
<h1>Customs</h1>
<p class="muted">Checks package installs before a coding agent runs them.</p>
<h2>Evaluation</h2>
{render_stats(_load_results())}
<h2>Try a package</h2>
<form method="post" action="/check" class="card">
  <label for="command">Install command</label>
  <input type="text" id="command" name="command" maxlength="{MAX_COMMAND_CHARS}"
         value="{html.escape(command)}" placeholder="pip install requests" autocomplete="off">
  <button type="submit">Check</button>
</form>
{result_html}
</main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (stdlib naming)
        if self.path != "/":
            self._send(404, page())
            return
        self._send(200, page())

    def do_POST(self):  # noqa: N802
        if self.path != "/check":
            self._send(404, page())
            return
        length = min(int(self.headers.get("Content-Length", 0) or 0), 4096)
        form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        command = form.get("command", [""])[0].strip()[:MAX_COMMAND_CHARS]
        result = render_verdict(command) if command else ""
        self._send(200, page(command, result))

    def _send(self, status: int, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):  # keep the console quiet
        return


def main(argv: list[str] | None = None) -> int:
    host, port = "127.0.0.1", 8000
    server = HTTPServer((host, port), Handler)
    print(f"Customs dashboard on http://{host}:{port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
