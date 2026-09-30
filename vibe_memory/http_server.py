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
import hmac
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Optional


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server."""
    daemon_threads = False


class VibeHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for VibeMemory API."""

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    @property
    def memory_instance(self):
        return self.server.memory_instance

    def _send(self, data, status=200):
        if getattr(self, "dispatching", False):
            self.pending_response = (data, status)
            return
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        origin = self.headers.get("Origin")
        if origin and origin in self.server.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        if self.command == "OPTIONS" and status == 200:
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) > 1:
            raise ValueError("Invalid body framing")
        length = int(self.headers.get("Content-Length", 0))
        if length < 0:
            raise ValueError("Invalid body length")
        if length > 1024 * 1024:
            raise OverflowError("Body too large")
        if length == 0:
            return {}
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            raise ValueError("Expected JSON")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ValueError("Incomplete body")
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise ValueError("Expected JSON object")
        return body

    def _handle(self, operation=None):
        hosts = self.headers.get_all("Host", [])
        origins = self.headers.get_all("Origin", [])
        if len(hosts) != 1 or hosts[0].lower() not in self.server.allowed_hosts or len(origins) > 1 or (origins and origins[0] not in self.server.allowed_origins):
            self._send({"error": "Host or Origin denied"}, 403)
            return
        if self.command == "OPTIONS":
            self._send({}, 200)
            return
        auth = self.headers.get_all("Authorization", [])
        if not (self.command == "GET" and self.path == "/health") and (len(auth) != 1 or not hmac.compare_digest(auth[0].encode(), ("Bearer " + self.server.token).encode())):
            self._send({"error": "Unauthorized"}, 401)
            return
        try:
            if self.command == "POST":
                self.json_body = self._read_json()
            with self.server.memory_lock:
                self.dispatching = True
                try:
                    operation()
                finally:
                    self.dispatching = False
            self._send(*self.pending_response)
        except OverflowError:
            self._send({"error": "Request body exceeds 1 MiB"}, 413)
        except (ValueError, TypeError, UnicodeError):
            self._send({"error": "Invalid request"}, 400)
        except TimeoutError:
            self._send({"error": "Request timed out"}, 408)
        except Exception:
            self._send({"error": "Internal server error"}, 500)

    def do_OPTIONS(self):
        self._handle()

    def do_GET(self):
        self._handle(self._get)

    def _get(self):
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
                    "failures": stats["metrics"]["failures"],
                })
            elif self.path == "/health":
                self._send({"status": "ok", "version": "0.3.0"})
            else:
                self._send({"error": "Not found"}, 404)
        except Exception:
            raise

    def do_POST(self):
        self._handle(self._post)

    def _post(self):
        mem = self.memory_instance
        try:
            body = self.json_body

            if self.path == "/store":
                content = body.get("content", "")
                atom = mem.store(
                    content=content,
                    tags=body.get("tags", []),
                    summary=body.get("summary"),
                    session_id=body.get("session_id"),
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
                    "failures": result.get("failures", []),
                    "memories": [
                        {"id": a.id[:8], "summary": a.summary[:150], "tags": a.tags}
                        for a in result.get("atoms", [])
                    ],
                })

            elif self.path == "/session/start":
                context = body.get("context", "")
                result = mem.recall(context, mode="precision", top_k=10)
                session_id = str(uuid.uuid4())
                self._send({
                    "session_id": session_id,
                    "memories_recalled": len(result.get("atoms", [])),
                    "failures": result.get("failures", []),
                })

            elif self.path == "/session/end":
                summary = body.get("summary", "")
                highlights = body.get("highlights", [])
                sid = body.get("session_id")
                if not isinstance(sid, str) or not sid:
                    raise ValueError("Explicit session_id required")
                if not isinstance(summary, str) or not isinstance(highlights, list) or not all(isinstance(hl, str) for hl in highlights):
                    raise ValueError("Invalid session content")
                stored = 0
                if summary:
                    mem.store(content=summary, session_id=sid, tags=["session-summary"], auto_build_edges=False)
                    stored += 1
                for hl in highlights:
                    mem.store(content=hl, session_id=sid, tags=["session-highlight"], auto_build_edges=False)
                    stored += 1
                self._send({"session_id": sid, "stored": stored})

            elif self.path == "/link":
                from vibe_memory.models.memory_atom import EdgeLabel
                label_map = {"causal": EdgeLabel.CAUSAL, "revision": EdgeLabel.REVISION,
                             "similar": EdgeLabel.SIMILAR, "adjacent": EdgeLabel.ADJACENT}
                label = label_map[body.get("label", "similar")] if body.get("label", "similar") in label_map else None
                if label is None:
                    raise ValueError("Invalid edge label")
                edge = mem.link(
                    body.get("from_id", ""), body.get("to_id", ""),
                    label=label,
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
        except Exception:
            raise

    def do_DELETE(self):
        self._handle(self._delete)

    def _delete(self):
        mem = self.memory_instance
        try:
            if self.path.startswith("/forget/"):
                atom_id = self.path.split("/forget/")[-1]
                ok = mem.forget(atom_id)
                self._send({"deleted": ok, "atom_id": atom_id[:8]})
            else:
                self._send({"error": "Not found"}, 404)
        except Exception:
            raise

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
        token: Optional[str] = None,
        allowed_origins: tuple = (),
    ):
        from vibe_memory import VibeMemory

        token = token if token is not None else os.environ.get("VIBE_HTTP_TOKEN")
        if not isinstance(token, str) or not token.strip():
            raise ValueError("HTTP token required: set VIBE_HTTP_TOKEN")
        if host not in ("127.0.0.1", "localhost"):
            raise ValueError("HTTP server supports loopback only; use a secured gateway for remote access")
        if isinstance(allowed_origins, str) or any(not isinstance(origin, str) or origin in ("*", "null") or not origin.startswith(("http://", "https://")) for origin in allowed_origins):
            raise ValueError("Explicit HTTP origins required")
        self.httpd = ThreadingHTTPServer((host, port), VibeHTTPHandler)
        try:
            self.httpd.memory_instance = VibeMemory(
                agent_id=agent_id, db_path=db_path, embedding_backend=embedding_backend,
            )
        except Exception:
            self.httpd.server_close()
            raise
        self.httpd.token = token
        self.httpd.allowed_origins = tuple(allowed_origins)
        self.port = self.httpd.server_address[1]
        self.httpd.allowed_hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        # ponytail: serialize one shared SDK/connection; use isolated workers if throughput requires it.
        self.httpd.memory_lock = threading.RLock()
        self.host = host

    def start(self):
        print(f"VibeMemory HTTP API: http://{self.host}:{self.port}")
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.httpd.server_close()
            self.httpd.memory_instance.storage.conn.close()


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
