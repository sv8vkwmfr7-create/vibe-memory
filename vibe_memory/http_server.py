"""
VibeMemory HTTP API Server — Universal REST interface

Language-agnostic HTTP API. Any agent, any language, any platform.

Endpoints:
  POST /store        — Write a memory atom
  POST /recall       — Retrieve memories
  POST /session/start — Start session, recall + inject
  POST /session/end   — End session, store summary
  GET  /stats         — Memory statistics
  POST /link          — Create edge between atoms
  DELETE /forget/<id> — Delete a memory atom
  POST /flush         — Process LLM edge queue

Usage:
  python -m vibe_memory.http_server --port 8420
"""

import json
import os
import uuid
import argparse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Optional


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server."""
    daemon_threads = True


class VibeHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for VibeMemory API."""

    memory_instance = None  # Set by VibeHTTPServer
    session_id = None  # Shared across handlers (class-level)

    def _send(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        mem = self.memory_instance
        try:
            if self.path == "/stats":
                stats = mem.stats()
                self._send({
                    "total_atoms": stats["total_atoms"],
                    "active_atoms": stats["active_atoms"],
                    "total_edges": stats["total_edges"],
                    "store_count": stats["store_count"],
                    "recall_count": stats["recall_count"],
                })
            elif self.path == "/health":
                self._send({"status": "ok", "version": "0.3.0"})
            else:
                self._send({"error": "Not found"}, 404)
        except Exception as e:
            self._send({"error": str(e)}, 500)

    def do_POST(self):
        mem = self.memory_instance
        try:
            body = self._read_json()
            cls = self.__class__

            if self.path == "/store":
                content = body.get("content", "")
                atom = mem.store(
                    content=content,
                    tags=body.get("tags", []),
                    summary=body.get("summary"),
                    session_id=body.get("session_id") or cls.session_id,
                    auto_build_edges=False,
                )
                self._send({"id": atom.id, "summary": atom.summary[:120], "tags": atom.tags})

            elif self.path == "/recall":
                result = mem.recall(
                    query=body.get("query", ""),
                    mode=body.get("mode", "precision"),
                    top_k=body.get("top_k", 20),
                )
                self._send({
                    "count": len(result.get("atoms", [])),
                    "mode": result.get("mode"),
                    "memories": [
                        {"id": a.id[:8], "summary": a.summary[:150], "tags": a.tags}
                        for a in result.get("atoms", [])
                    ],
                })

            elif self.path == "/session/start":
                context = body.get("context", "")
                result = mem.recall(context, mode="precision", top_k=10)
                cls.session_id = str(uuid.uuid4())
                self._send({
                    "session_id": cls.session_id[:8],
                    "memories_recalled": len(result.get("atoms", [])),
                })

            elif self.path == "/session/end":
                summary = body.get("summary", "")
                highlights = body.get("highlights", [])
                sid = cls.session_id or str(uuid.uuid4())
                stored = 0
                if summary:
                    mem.store(content=summary, session_id=sid, tags=["session-summary"], auto_build_edges=False)
                    stored += 1
                for hl in highlights:
                    mem.store(content=hl, session_id=sid, tags=["session-highlight"], auto_build_edges=False)
                    stored += 1
                self._send({"session_id": sid[:8], "stored": stored})

            elif self.path == "/link":
                from vibe_memory.models.memory_atom import EdgeLabel
                label_map = {"causal": EdgeLabel.CAUSAL, "revision": EdgeLabel.REVISION,
                             "similar": EdgeLabel.SIMILAR, "adjacent": EdgeLabel.ADJACENT}
                edge = mem.link(
                    body.get("from_id", ""), body.get("to_id", ""),
                    label=label_map.get(body.get("label", "similar"), EdgeLabel.SIMILAR),
                )
                if edge:
                    self._send({"id": edge.id[:8], "label": edge.label.value})
                else:
                    self._send({"error": "Failed to create edge"}, 400)

            elif self.path == "/flush":
                n = mem.flush_index(max_batch=body.get("max_batch"))
                self._send({"edges_created": n})

            else:
                self._send({"error": "Not found"}, 404)
        except Exception as e:
            self._send({"error": str(e)}, 500)

    def do_DELETE(self):
        mem = self.memory_instance
        try:
            if self.path.startswith("/forget/"):
                atom_id = self.path.split("/forget/")[-1]
                ok = mem.forget(atom_id)
                self._send({"deleted": ok, "atom_id": atom_id[:8]})
            else:
                self._send({"error": "Not found"}, 404)
        except Exception as e:
            self._send({"error": str(e)}, 500)

    def log_message(self, format, *args):
        pass  # Suppress default logging


class VibeHTTPServer:
    """Standalone HTTP server for VibeMemory."""

    def __init__(
        self,
        agent_id: str = "http-agent",
        db_path: str = ".vibe/memory.db",
        embedding_backend: str = "tfidf",
        port: int = 8420,
        host: str = "127.0.0.1",
    ):
        from vibe_memory import VibeMemory

        VibeHTTPHandler.memory_instance = VibeMemory(
            agent_id=agent_id, db_path=db_path, embedding_backend=embedding_backend,
        )
        self.httpd = ThreadingHTTPServer((host, port), VibeHTTPHandler)
        self.port = port
        self.host = host

    def start(self):
        print(f"VibeMemory HTTP API: http://{self.host}:{self.port}")
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            self.httpd.shutdown()


def main():
    parser = argparse.ArgumentParser(description="VibeMemory HTTP API Server")
    parser.add_argument("--port", type=int, default=8420)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--db-path", default=".vibe/memory.db")
    parser.add_argument("--agent-id", default="http-agent")
    parser.add_argument("--embedding-backend", default="tfidf")
    args = parser.parse_args()

    VibeHTTPServer(
        agent_id=args.agent_id, db_path=args.db_path,
        embedding_backend=args.embedding_backend,
        port=args.port, host=args.host,
    ).start()


if __name__ == "__main__":
    main()