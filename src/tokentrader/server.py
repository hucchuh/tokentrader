from __future__ import annotations

import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .service import TokenTraderService

WEB_ROOT = Path(__file__).resolve().parent / "web"
service = TokenTraderService(db_path=str(Path("data") / "tokentrader.db"))


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def _json_response(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) if n > 0 else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)

            if parsed.path == "/api/profile":
                token = query.get("token", [""])[0]
                user = service.get_user_by_token(token)
                if not user:
                    self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "未登录"})
                    return
                self._json_response(HTTPStatus.OK, {"ok": True, "user": user})
                return

            if parsed.path == "/api/bootstrap":
                token = query.get("token", [""])[0]
                thread_raw = query.get("thread_id", [""])[0]
                thread_id = int(thread_raw) if thread_raw.isdigit() else None
                data = service.get_dashboard(token, thread_id=thread_id)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return

            if parsed.path == "/":
                self.path = "/index.html"
            return super().do_GET()
        except ValueError as exc:
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        except PermissionError as exc:
            self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": str(exc)})
        except Exception:
            self._json_response(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "服务内部错误"})

    def do_POST(self) -> None:
        try:
            payload = self._read_json_body()

            if self.path == "/api/auth":
                auth = service.auth(
                    str(payload.get("email", "")),
                    str(payload.get("password", "")),
                    str(payload.get("name", "")),
                )
                self._json_response(HTTPStatus.OK, {"ok": True, **auth})
                return

            if self.path == "/api/register":
                user = service.register_user(
                    str(payload.get("email", "")),
                    str(payload.get("password", "")),
                    str(payload.get("name", "")),
                )
                self._json_response(HTTPStatus.CREATED, {"ok": True, "user": user})
                return

            if self.path == "/api/login":
                auth = service.login(str(payload.get("email", "")), str(payload.get("password", "")))
                self._json_response(HTTPStatus.OK, {"ok": True, **auth})
                return

            if self.path == "/api/threads":
                data = service.create_thread(str(payload.get("token", "")), payload)
                self._json_response(HTTPStatus.CREATED, {"ok": True, **data})
                return

            if self.path == "/api/posts":
                data = service.create_post(str(payload.get("token", "")), payload)
                self._json_response(HTTPStatus.CREATED, {"ok": True, **data})
                return

            if self.path == "/api/tasks":
                data = service.create_task(str(payload.get("token", "")), payload)
                self._json_response(HTTPStatus.CREATED, {"ok": True, **data})
                return

            if self.path == "/api/tasks/claim":
                data = service.claim_task(str(payload.get("token", "")), payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return

            if self.path == "/api/tasks/complete":
                data = service.complete_task(str(payload.get("token", "")), payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return

            if self.path == "/api/quote":
                data = service.build_quote_for_user(str(payload.get("token", "")), payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return

            if self.path == "/api/execute":
                data = service.execute_for_user(str(payload.get("token", "")), payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return

            self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "接口不存在"})
        except ValueError as exc:
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        except PermissionError as exc:
            self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": str(exc)})
        except Exception:
            self._json_response(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "服务内部错误"})


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"TokenTrader Web running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
