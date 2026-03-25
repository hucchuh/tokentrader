from pathlib import Path

from tokentrader.service import TokenTraderService


def test_register_login_and_quote_flow(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    service = TokenTraderService(db_path=str(db))

    user = service.register_user(email="alice@example.com", password="passw0rd!", name="Alice")
    assert user["email"] == "alice@example.com"

    auth = service.login(email="alice@example.com", password="passw0rd!")
    assert auth["token"]

    quote = service.build_quote_for_user(
        token=auth["token"],
        payload={
            "task_type": "analysis",
            "prompt_tokens": 1200,
            "max_latency_ms": 1500,
            "budget_credits": 1.0,
            "quality_tier": "balanced",
        },
    )
    assert quote["candidates"]


def test_register_duplicate_email(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "dup.db"))
    service.register_user(email="bob@example.com", password="passw0rd!", name="Bob")

    try:
        service.register_user(email="bob@example.com", password="passw0rd!", name="Bobby")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "已注册" in str(exc)
