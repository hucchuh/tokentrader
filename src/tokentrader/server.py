from __future__ import annotations

import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .service import TokenTraderService

WEB_ROOT = Path(__file__).resolve().parent / "web"
service = TokenTraderService(db_path=str(Path("data") / "tokentrader.db"), seed_demo=True)


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def _auth_header_value(self) -> str:
        bearer = self.headers.get("Authorization", "")
        if bearer.startswith("Bearer "):
            return bearer.split(" ", maxsplit=1)[1].strip()
        return self.headers.get("X-API-Key", "").strip()

    def _auth_from_query(self, query: dict[str, list[str]]) -> str:
        token = query.get("token", [""])[0].strip()
        return token or self._auth_header_value()

    def _auth_from_payload(self, payload: dict) -> str:
        token = str(payload.get("token", "")).strip()
        return token or self._auth_header_value()

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
            parts = [part for part in parsed.path.strip("/").split("/") if part]
            if parsed.path == "/api/profile":
                token = self._auth_from_query(query)
                user = service.get_user_by_token(token)
                if not user:
                    self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "Not logged in."})
                    return
                self._json_response(HTTPStatus.OK, {"ok": True, "user": user})
                return
            if parsed.path == "/api/bootstrap":
                token = self._auth_from_query(query)
                task_raw = query.get("task_id", [""])[0]
                task_id = int(task_raw) if task_raw.isdigit() else None
                data = service.get_dashboard(token, task_id=task_id)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if parsed.path == "/api/wallet/me":
                token = self._auth_from_query(query)
                data = service.get_wallet(token)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if parsed.path == "/api/wallet/me/ledger":
                token = self._auth_from_query(query)
                limit_raw = query.get("limit", ["20"])[0]
                limit = int(limit_raw) if limit_raw.isdigit() else 20
                data = service.get_wallet_ledger(token, limit=limit)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if parsed.path == "/api/settings":
                token = self._auth_from_query(query)
                data = service.get_settings(token)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if parsed.path == "/api/tasks/open":
                token = self._auth_from_query(query)
                mode = query.get("mode", [""])[0].strip() or None
                data = service.list_open_tasks(token, mode=mode)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if parsed.path == "/api/exchange-rates/latest":
                token = self._auth_from_query(query)
                data = service.get_latest_exchange_rates(token)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if parsed.path == "/api/api-keys":
                token = self._auth_from_query(query)
                data = service.list_api_keys(token)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if len(parts) == 4 and parts[:2] == ["api", "tasks"] and parts[3] == "pricing":
                token = self._auth_from_query(query)
                task_id = int(parts[2])
                data = service.get_task_pricing(token, task_id)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if len(parts) == 4 and parts[:2] == ["api", "tasks"] and parts[3] == "submissions":
                token = self._auth_from_query(query)
                task_id = int(parts[2])
                data = service.list_task_submissions(token, task_id)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if parsed.path == "/":
                self.path = "/index.html"
            if parsed.path == "/app":
                self.path = "/app.html"
            return super().do_GET()
        except ValueError as exc:
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        except PermissionError as exc:
            self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": str(exc)})
        except Exception:
            self._json_response(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "Internal server error."})

    def do_POST(self) -> None:
        try:
            payload = self._read_json_body()
            auth_value = self._auth_from_payload(payload)
            parts = [part for part in self.path.strip("/").split("/") if part]
            if self.path == "/api/auth":
                auth = service.auth(
                    str(payload.get("email", "")),
                    str(payload.get("password", "")),
                    str(payload.get("name", "")),
                )
                self._json_response(HTTPStatus.OK, {"ok": True, **auth})
                return
            if self.path == "/api/profile":
                data = service.update_profile(auth_value, payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if self.path == "/api/settings":
                data = service.update_settings(auth_value, payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if self.path == "/api/tasks":
                data = service.create_task(auth_value, payload)
                self._json_response(HTTPStatus.CREATED, {"ok": True, **data})
                return
            if self.path == "/api/tasks/bids":
                data = service.submit_bid(auth_value, payload)
                self._json_response(HTTPStatus.CREATED, {"ok": True, **data})
                return
            if self.path == "/api/tasks/claim":
                data = service.claim_task(auth_value, payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if self.path == "/api/tasks/award":
                data = service.award_bid(auth_value, payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if self.path == "/api/tasks/verify":
                data = service.approve_secondary_verification(auth_value, payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if self.path == "/api/tasks/rework":
                data = service.request_rework(auth_value, payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if self.path == "/api/tasks/complete":
                data = service.complete_task(auth_value, payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if self.path == "/api/tasks/review":
                data = service.review_task(auth_value, payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if self.path == "/api/pricing/preview":
                data = service.preview_pricing(auth_value, payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if self.path == "/api/api-keys":
                data = service.create_api_key(auth_value, payload)
                self._json_response(HTTPStatus.CREATED, {"ok": True, **data})
                return
            if len(parts) == 4 and parts[:2] == ["api", "tasks"] and parts[3] == "submissions":
                payload["task_id"] = int(parts[2])
                data = service.submit_task_submission(auth_value, payload)
                self._json_response(HTTPStatus.CREATED, {"ok": True, **data})
                return
            if self.path == "/api/quote":
                data = service.build_quote_for_user(auth_value, payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            if self.path == "/api/execute":
                data = service.execute_for_user(auth_value, payload)
                self._json_response(HTTPStatus.OK, {"ok": True, **data})
                return
            self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Endpoint not found."})
        except ValueError as exc:
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        except PermissionError as exc:
            self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": str(exc)})
        except Exception:
            self._json_response(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "Internal server error."})


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"TokenTrader Web running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
