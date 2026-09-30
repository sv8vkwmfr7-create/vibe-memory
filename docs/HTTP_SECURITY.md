# HTTP security and migration

This server is a local integration endpoint, not a public production gateway.

## Connect

Set `VIBE_HTTP_TOKEN` privately in the launching process to a strong random secret, then run `vibe-http --port 8420`. Missing/blank tokens fail startup. Do not put the token in command-line arguments, source control, Wiki, browser URLs or logs. Python callers may supply `token=` directly from their secret store.

Data requests require `Authorization: Bearer <token>`. `GET /health` is unauthenticated and returns only readiness/version, still subject to Host/Origin validation. A token grants access to the server's configured agent, not a separate per-user identity. Do not share it between mutually untrusted users.

Only `127.0.0.1`/`localhost` bindings are accepted. Host must match one of those names and the actual listening port. Browser origins are denied by default. Python embedding can opt into exact origins with `allowed_origins=("https://your-app.example",)`. No wildcard/null origin is accepted. A permitted origin is not authentication: actual data requests still require the token; permitted preflight OPTIONS does not.

POST bodies must be JSON objects with `Content-Type: application/json`. Maximum declared body size is 1 MiB; chunked/duplicate length framing is refused. Socket I/O timeout is 10 seconds. Oversized uploads may be disconnected before clients finish writing, especially on Windows; the service does not consume unlimited bodies to guarantee delivery of an error response. Internal exception details are not sent to clients.

## Session migration

1. POST `/session/start` with `{"context":"..."}`; save the full returned UUID.
2. POST `/store` with `{"content":"...","session_id":"<full UUID>"}`.
3. POST `/session/end` with `{"session_id":"<full UUID>","summary":"...","highlights":[]}`.

There is no shared "current session." Session end requires an explicit nonempty ID, returned without truncation. Session IDs group data; they are not authorization credentials. Existing anonymous clients and clients relying on implicit sessions must migrate.

## Concurrency and limits

Each server owns a separate SDK and a lock covering an entire SDK operation, including its connection/cache/transaction changes. Network body reads and response writes are outside that lock. This deliberately serializes SDK work in one service; it is not a throughput optimization, does not coordinate other processes or raw SDK/storage callers, and does not provide multi-request transaction atomicity. Session end can partially persist if a later store fails.

Shutdown waits for active handler threads before the standalone server closes its SDK connection. Embedded callers using `httpd.serve_forever` own shutdown, server_close and SDK connection cleanup.

No TLS, per-user authorization, rate limiting or bounded thread pool is provided. Keep it local; any remote exposure requires a separately secured gateway and operational review. Automated tests use synthetic tokens and in-memory databases, not a real browser attack or production load test.
