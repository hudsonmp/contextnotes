"""Lightweight HTTP server that receives gaze samples from WebGazer.js and writes to Supabase.

Run standalone:
    python -m capture.gaze.relay_server --port 8765 --session-id <uuid>

The WebGazer page POSTs batches of gaze samples to /gaze.
This server writes them to the gaze_stream table.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from trace.models import GazeSample
from trace.store import TraceStore


class GazeHandler(BaseHTTPRequestHandler):
    store: TraceStore = None

    def do_POST(self):
        if self.path != "/gaze":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body)

        samples = []
        for s in data.get("samples", []):
            samples.append(GazeSample(
                timestamp=datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00")),
                session_id=s["session_id"],
                gaze_x=s.get("gaze_x"),
                gaze_y=s.get("gaze_y"),
                gaze_confidence=s.get("gaze_confidence"),
                scroll_y=s.get("scroll_y"),
                scroll_progress=s.get("scroll_progress"),
            ))

        if samples and self.store:
            self.store.insert_gaze_batch(samples)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"received": len(samples)}).encode())

    def do_OPTIONS(self):
        """CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        # Suppress default logging noise
        pass


def main():
    parser = argparse.ArgumentParser(description="Gaze relay server")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--session-id", help="Session ID (for validation)")
    args = parser.parse_args()

    GazeHandler.store = TraceStore()

    server = HTTPServer(("127.0.0.1", args.port), GazeHandler)
    print(f"Gaze relay listening on http://127.0.0.1:{args.port}/gaze")
    print(f"Open WebGazer page with: ?endpoint=http://127.0.0.1:{args.port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGaze relay stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
