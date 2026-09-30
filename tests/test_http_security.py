"""Loopback HTTP trust boundary and instance isolation regressions."""
import http.client
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest

from vibe_memory.http_server import VibeHTTPServer

TOKEN = "synthetic-http-test-token"


@contextmanager
def running(monkeypatch):
    monkeypatch.setenv("VIBE_HTTP_TOKEN", TOKEN)
    server = VibeHTTPServer(port=0, db_path=":memory:")
    thread = threading.Thread(target=server.httpd.serve_forever)
    thread.start()
    try:
        yield server
    finally:
        server.httpd.shutdown()
        server.httpd.server_close()
        thread.join(5)
        server.httpd.memory_instance.storage.conn.close()


def request(server, path="/stats", method="GET", body=None, **headers):
    conn = http.client.HTTPConnection("127.0.0.1", server.httpd.server_address[1], timeout=5)
    headers.setdefault("Authorization", "Bearer " + TOKEN)
    if body is not None:
        headers.setdefault("Content-Type", "application/json")
        body = json.dumps(body).encode()
    conn.request(method, path, body=body, headers=headers)
    response = conn.getresponse()
    result = response.status, json.loads(response.read()), dict(response.getheaders())
    conn.close()
    return result


@pytest.mark.parametrize("authorization", ["", "Bearer wrong", "Basic " + TOKEN])
def test_data_requires_token(monkeypatch, authorization):
    with running(monkeypatch) as server:
        assert request(server, Authorization=authorization)[0] == 401


@pytest.mark.parametrize("headers", [{"Origin": "https://evil.example"}, {"Host": "evil.example"}])
def test_browser_boundary(monkeypatch, headers):
    with running(monkeypatch) as server:
        assert request(server, **headers)[0] == 403


def test_session_ids_are_explicit_and_complete(monkeypatch):
    with running(monkeypatch) as server:
        sid = request(server, "/session/start", "POST", {})[1]["session_id"]
        assert len(sid) == 36
        assert request(server, "/session/end", "POST", {"summary": "test"})[0] == 400
        assert request(server, "/session/end", "POST", {"session_id": sid, "summary": "test"})[1]["session_id"] == sid


def test_instances_do_not_share_memory(monkeypatch):
    with running(monkeypatch) as first, running(monkeypatch) as second:
        assert request(first, "/store", "POST", {"content": "only first"})[0] == 200
        assert request(first)[1]["total_atoms"] == 1
        assert request(second)[1]["total_atoms"] == 0


def test_body_limit_and_object_shape(monkeypatch):
    with running(monkeypatch) as server:
        assert request(server, "/store", "POST", ["invalid"])[0] == 400
        # Reject from headers without uploading a body that Windows may reset on close.
        conn = http.client.HTTPConnection("127.0.0.1", server.httpd.server_address[1], timeout=5)
        conn.putrequest("POST", "/store")
        conn.putheader("Authorization", "Bearer " + TOKEN)
        conn.putheader("Content-Length", str(1024 * 1024 + 1))
        conn.endheaders()
        assert conn.getresponse().status == 413
        conn.close()


def test_startup_requires_token(monkeypatch):
    monkeypatch.delenv("VIBE_HTTP_TOKEN", raising=False)
    with pytest.raises(ValueError, match="token"):
        VibeHTTPServer(port=0, db_path=":memory:")


def test_no_remote_binding_or_wildcard_origin(monkeypatch):
    monkeypatch.setenv("VIBE_HTTP_TOKEN", TOKEN)
    for kwargs in ({"host": "0.0.0.0"}, {"allowed_origins": ("*",)}):
        with pytest.raises(ValueError):
            VibeHTTPServer(port=0, db_path=":memory:", **kwargs)


def test_allowed_origin_still_requires_auth(monkeypatch):
    with running(monkeypatch) as server:
        server.httpd.allowed_origins = ("https://app.example",)
        status, _, headers = request(server, method="OPTIONS", Origin="https://app.example", Authorization="")
        assert status == 200
        assert headers["Access-Control-Allow-Origin"] == "https://app.example"
        assert request(server, Origin="https://app.example", Authorization="")[0] == 401
        assert request(server, Origin="https://app.example")[0] == 200


def test_internal_error_is_redacted(monkeypatch):
    with running(monkeypatch) as server:
        def fail():
            raise RuntimeError("private path and credential")
        monkeypatch.setattr(server.httpd.memory_instance, "stats", fail)
        status, body, _ = request(server)
        assert status == 500
        assert body == {"error": "Internal server error"}


def test_requests_cannot_commit_another_request_transaction(monkeypatch):
    with running(monkeypatch) as server:
        mem = server.httpd.memory_instance
        conn = mem.storage.conn
        conn.execute("CREATE TABLE transaction_probe (value TEXT)")
        conn.commit()
        entered, release, second_entered = threading.Event(), threading.Event(), threading.Event()
        original = mem.store

        def controlled_store(*args, **kwargs):
            if kwargs["content"] == "first":
                conn.execute("BEGIN")
                conn.execute("INSERT INTO transaction_probe VALUES ('must roll back')")
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("test synchronization timeout")
                conn.rollback()
            else:
                second_entered.set()
            return original(*args, **kwargs)

        monkeypatch.setattr(mem, "store", controlled_store)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(request, server, "/store", "POST", {"content": "first"})
            assert entered.wait(2)
            second = pool.submit(request, server, "/store", "POST", {"content": "second"})
            try:
                assert not second_entered.wait(0.2)
            finally:
                release.set()
            assert first.result()[0] == second.result()[0] == 200
        assert conn.execute("SELECT count(*) FROM transaction_probe").fetchone()[0] == 0
        assert request(server)[1]["total_atoms"] == 2
