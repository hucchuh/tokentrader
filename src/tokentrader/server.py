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
        content_len = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_len) if content_len > 0 else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/profile":
            query = parse_qs(parsed.query)
            token = query.get("token", [""])[0]
            user = service.get_user_by_token(token)
            if not user:
                self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "未登录"})
                return
            self._json_response(HTTPStatus.OK, {"ok": True, "user": user})
            return

        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        try:
            payload = self._read_json_body()
            if self.path == "/api/register":
                user = service.register_user(
                    email=str(payload.get("email", "")),
                    password=str(payload.get("password", "")),
                    name=str(payload.get("name", "")),
                )
                self._json_response(HTTPStatus.CREATED, {"ok": True, "user": user})
                return

            if self.path == "/api/login":
                auth = service.login(
                    email=str(payload.get("email", "")),
                    password=str(payload.get("password", "")),
                )
                self._json_response(HTTPStatus.OK, {"ok": True, **auth})
                return

            if self.path == "/api/quote":
                token = str(payload.get("token", ""))
                quote = service.build_quote_for_user(token=token, payload=payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **quote})
                return

            if self.path == "/api/execute":
                token = str(payload.get("token", ""))
                result = service.execute_for_user(token=token, payload=payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **result})
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
