from pathlib import Path

from tokentrader.service import TokenTraderService


def test_auth_creates_profile_and_starter_mana(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "auth.db"))

    auth = service.auth("alice@example.com", "passw0rd!", "Alice")
    dashboard = service.get_dashboard(auth["token"])

    assert auth["created"] is True
    assert dashboard["user"]["mana_balance"] == 240
    assert dashboard["profile"]["headline"] == "General AI freelancer"
    assert dashboard["stats"]["open_tasks"] == 0


def test_profile_update_persists_skills_and_focus_area(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "profile.db"))
    auth = service.auth("alice@example.com", "passw0rd!", "Alice")

    result = service.update_profile(
        auth["token"],
        {
            "headline": "Biotech research writer",
            "bio": "I turn messy source material into board-ready research notes and executive memos.",
            "focus_area": "Research",
            "skills": "biotech, memos, due diligence",
        },
    )

    assert result["profile"]["focus_area"] == "Research"
    assert result["profile"]["skills"] == ["biotech", "memos", "due diligence"]


def test_private_scope_is_hidden_until_a_bid_is_awarded(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "privacy.db"))
    creator = service.auth("client@example.com", "passw0rd!", "Client")
    bidder = service.auth("seller@example.com", "passw0rd!", "Seller")

    created = service.create_task(
        creator["token"],
        {
            "title": "Prepare a board memo",
            "category": "Research",
            "public_brief": "Need a bid for a board memo based on a confidential diligence package.",
            "private_brief": "The target company, stakeholders, and red flags are confidential until award.",
            "reward_mana": 60,
            "prompt_tokens": 1600,
            "max_latency_ms": 1700,
            "budget_credits": 1.2,
            "quality_tier": "balanced",
            "task_type": "analysis",
        },
    )

    task_id = created["task"]["id"]
    before_award = service.get_dashboard(bidder["token"], task_id=task_id)["selected_task"]
    assert before_award["private_brief"] is None
    assert "Sealed" in before_award["private_scope_status"]

    service.submit_bid(
        bidder["token"],
        {
            "task_id": task_id,
            "pitch": "I have shipped diligence memos for venture and public market teams before.",
            "quote_mana": 58,
            "eta_days": 2,
        },
    )
    creator_view = service.get_dashboard(creator["token"], task_id=task_id)["selected_task"]
    bid_id = creator_view["bids"][0]["id"]
    service.award_bid(creator["token"], {"task_id": task_id, "bid_id": bid_id})

    after_award = service.get_dashboard(bidder["token"], task_id=task_id)["selected_task"]
    assert "confidential" in after_award["private_brief"]


def test_bid_award_complete_and_review_update_reputation(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "flow.db"))
    creator = service.auth("client@example.com", "passw0rd!", "Client")
    bidder = service.auth("seller@example.com", "passw0rd!", "Seller")

    created = service.create_task(
        creator["token"],
        {
            "title": "Build a finance model",
            "category": "Finance",
            "public_brief": "Looking for a freelancer to build a clean operating model for a marketplace startup.",
            "private_brief": "Private scope includes actual revenue data, payroll assumptions, and cap table notes.",
            "reward_mana": 70,
            "prompt_tokens": 1800,
            "max_latency_ms": 1800,
            "budget_credits": 1.4,
            "quality_tier": "premium",
            "task_type": "spreadsheet",
        },
    )
    task_id = created["task"]["id"]
    service.submit_bid(
        bidder["token"],
        {
            "task_id": task_id,
            "pitch": "I build operator-friendly models with assumptions tabs, scenarios, and board-ready outputs.",
            "quote_mana": 70,
            "eta_days": 3,
        },
    )

    task_for_creator = service.get_dashboard(creator["token"], task_id=task_id)["selected_task"]
    service.award_bid(creator["token"], {"task_id": task_id, "bid_id": task_for_creator["bids"][0]["id"]})
    completed = service.complete_task(
        bidder["token"],
        {
            "task_id": task_id,
            "deliverable": "Delivered a three-statement model, scenario view, and one-page assumption summary.",
            "external_ref": "https://example.com/model",
        },
    )

    assert completed["task"]["status"] == "done"

    reviewed = service.review_task(
        creator["token"],
        {
            "task_id": task_id,
            "overall_score": 4.9,
            "quality_score": 5.0,
            "speed_score": 4.7,
            "communication_score": 4.8,
            "comment": "Strong freelancer with clean assumptions, fast iterations, and a board-ready finish.",
        },
    )

    assert reviewed["task"]["review"]["overall_score"] == 4.9
    seller_dashboard = service.get_dashboard(bidder["token"])
    assert seller_dashboard["user"]["mana_balance"] == 310
    assert seller_dashboard["profile"]["verification_level"] == "Rated"
