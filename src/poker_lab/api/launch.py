"""Start the local lab application: 127.0.0.1 only, random token, opens the browser.

    python -m poker_lab.api.launch [--port 8765] [--no-browser]
"""

from __future__ import annotations

import argparse
import secrets
import socket
import sys
import webbrowser

LOOPBACK = "127.0.0.1"


def pick_port(preferred: int) -> int:
    for port in [preferred, *range(preferred + 1, preferred + 20)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((LOOPBACK, port))
            except OSError:
                continue
            return int(port)
    raise SystemExit("nenhuma porta livre encontrada em 127.0.0.1")


def build_url(port: int, token: str) -> str:
    # token goes in the fragment: never sent to the server in the URL, never in server logs
    return f"http://{LOOPBACK}:{port}/#t={token}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Poker AI Tournament Lab — interface local")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
    import uvicorn

    from poker_lab.api.server import create_app

    port = pick_port(args.port)
    token = secrets.token_urlsafe(32)
    app = create_app(token, port)
    url = build_url(port, token)
    print("Poker AI Tournament Lab — interface local")
    print(f"Abra no navegador: {url}")
    print("(endereço só desta máquina; feche esta janela ou pressione Ctrl+C para encerrar)")
    sys.stdout.flush()
    if not args.no_browser:
        webbrowser.open(url)
    uvicorn.run(app, host=LOOPBACK, port=port, log_level="warning", access_log=False, server_header=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
