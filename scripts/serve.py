#!/usr/bin/env python3
"""Share exactly one self-contained magazine over the local network."""
import argparse
import json
import re
import secrets
import socket
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


def lan_address():
    try:
        result = subprocess.run(["/sbin/route", "-n", "get", "default"], capture_output=True, text=True, check=True)
        interface = re.search(r"interface:\s*(\S+)", result.stdout).group(1)
        result = subprocess.run(["/sbin/ifconfig", interface], capture_output=True, text=True, check=True)
        return re.search(r"\binet (\d+\.\d+\.\d+\.\d+)", result.stdout).group(1)
    except (OSError, subprocess.SubprocessError, AttributeError):
        address = socket.gethostbyname(socket.gethostname())
        if address.startswith("127."):
            raise RuntimeError("No LAN address found. Connect this computer to Wi-Fi first.")
        return address


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    magazine = args.file.resolve()
    if not magazine.is_file():
        parser.error("The magazine HTML file does not exist.")
    state_file = magazine.parent / "share-state.json"
    old = json.loads(state_file.read_text()) if state_file.exists() else {}
    token = old.get("token") or secrets.token_urlsafe(18)
    route = "/" + token + "/"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if urlsplit(self.path).path != route:
                self.send_error(404)
                return
            content = magazine.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    address = lan_address()
    url = f"http://{address}:{server.server_port}{route}"
    content = magazine.read_text(encoding="utf-8")
    pattern = r'(<script id="readzine-data" type="application/json">)(.*?)(</script>)'
    match = re.search(pattern, content, flags=re.S)
    if not match:
        raise RuntimeError("Cannot find the ReadZine data payload.")
    data = json.loads(match[2])
    data["mobileUrl"] = url
    encoded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    content = content[:match.start(2)] + encoded + content[match.end(2):]
    magazine.write_text(content, encoding="utf-8")
    state_file.write_text(json.dumps(dict(url=url, token=token, port=server.server_port), indent=2) + "\n")
    manifest = magazine.parent / "manifest.json"
    if manifest.exists():
        editorial = json.loads(manifest.read_text())
        editorial["mobileUrl"] = url
        manifest.write_text(json.dumps(editorial, ensure_ascii=False, indent=2) + "\n")
    print(f"ReadZine phone sharing is running: {url}", flush=True)
    print("Connect both devices to the same Wi-Fi. Refresh the cover, then choose Read on phone.", flush=True)
    print("Keep this window open. Press Ctrl+C to stop sharing.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
