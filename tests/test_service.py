from pathlib import Path

from tokentrader.service import TokenTraderService


def test_auth_auto_registers_and_bootstrap_returns_user_state(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "test.db"))

    auth = service.auth("alice@example.com", "passw0rd!", "Alice")

    assert auth["created"] is True
    assert auth["user"]["email"] == "alice@example.com"
    assert auth["user"]["mana_balance"] == 240

    dashboard = service.get_dashboard(auth["token"])

    assert dashboard["user"]["name"] == "Alice"
    assert dashboard["stats"]["issued_mana"] == 240
    assert dashboard["threads"] == []
    assert dashboard["tasks"] == []


def test_task_flow_moves_mana_and_posts_delivery_into_thread(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "flow.db"))

    creator = service.auth("alice@example.com", "passw0rd!", "Alice")
    worker = service.auth("bob@example.com", "passw0rd!", "Bob")

    task_data = service.create_task(
        creator["token"],
        {
            "title": "Create customer synthesis",
            "brief": "Review uploaded interviews and return a concise synthesis with action items.",
            "reward_mana": 60,
            "prompt_tokens": 1600,
            "max_latency_ms": 1600,
            "budget_credits": 1.2,
            "quality_tier": "balanced",
            "task_type": "analysis",
            "create_thread": True,
        },
    )

    task_id = task_data["task"]["id"]
    thread_id = task_data["task"]["thread_id"]

    creator_dashboard = service.get_dashboard(creator["token"], thread_id=thread_id)
    assert creator_dashboard["user"]["mana_balance"] == 180
    assert creator_dashboard["tasks"][0]["status"] == "open"

    claimed = service.claim_task(worker["token"], {"task_id": task_id})
    assert claimed["task"]["status"] == "in_progress"
    assert claimed["task"]["assignee"]["name"] == "Bob"

    completed = service.complete_task(
        worker["token"],
        {
            "task_id": task_id,
            "deliverable": "Uploaded the synthesis deck and returned three product action items.",
            "external_ref": "https://example.com/result",
        },
    )

    assert completed["task"]["status"] == "done"
    assert completed["task"]["deliverable"].startswith("Uploaded the synthesis")

    worker_dashboard = service.get_dashboard(worker["token"], thread_id=thread_id)
    assert worker_dashboard["user"]["mana_balance"] == 300
    assert worker_dashboard["selected_thread"]["posts"][-1]["body"].startswith("Uploaded the synthesis")


def test_register_duplicate_email(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "dup.db"))
    service.register_user("bob@example.com", "passw0rd!", "Bob")
    try:
        service.register_user("bob@example.com", "passw0rd!", "Bobby")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "已注册" in str(exc)
