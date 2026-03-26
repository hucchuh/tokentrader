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


def test_task_creation_persists_pricing_and_escrow(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "pricing.db"))
    creator = service.auth("creator@example.com", "passw0rd!", "Creator")

    preview = service.preview_pricing(
        creator["token"],
        {
            "task_type": "analysis",
            "prompt_tokens": 1500,
            "max_latency_ms": 1700,
            "budget_credits": 1.2,
            "quality_tier": "balanced",
        },
    )
    created = service.create_task(
        creator["token"],
        {
            "title": "Analyze interview notes",
            "category": "Research",
            "public_brief": "Need someone to synthesize interview notes into product recommendations.",
            "private_brief": "Private scope includes raw notes, named customers, and roadmap tradeoffs.",
            "reward_mana": 60,
            "prompt_tokens": 1500,
            "max_latency_ms": 1700,
            "budget_credits": 1.2,
            "quality_tier": "balanced",
            "task_type": "analysis",
        },
    )

    task_id = created["task"]["id"]
    pricing = service.get_task_pricing(creator["token"], task_id)
    wallet = service.get_wallet(creator["token"])
    dashboard = service.get_dashboard(creator["token"], task_id=task_id)

    assert preview["pricing_preview"]["minimum_publish_mana"] <= 60
    assert pricing["pricing"]["minimum_publish_mana"] == created["pricing"]["minimum_publish_mana"]
    assert pricing["pricing"]["recommended_mana_min"] >= pricing["pricing"]["minimum_publish_mana"]
    assert wallet["wallet"]["available_mana"] == 180
    assert wallet["wallet"]["held_mana"] == 60
    assert dashboard["selected_task"]["escrow"]["status"] == "held"
    assert dashboard["selected_task"]["pricing"]["exchange_rate_snapshot_id"] is not None


def test_api_keys_can_access_wallet_and_exchange_rates(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "apikeys.db"))
    user = service.auth("agent@example.com", "passw0rd!", "Agent")

    created = service.create_api_key(user["token"], {"name": "agent-bot"})
    listed = service.list_api_keys(user["token"])
    wallet = service.get_wallet(created["secret"])
    rates = service.get_latest_exchange_rates(created["secret"])

    assert listed["api_keys"][0]["name"] == "agent-bot"
    assert wallet["wallet"]["available_mana"] == 240
    assert rates["snapshot"]["id"] is not None
    assert any(item["provider"] == "provider_a" for item in rates["items"])


def test_submission_history_and_escrow_release_are_persisted(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "submissions.db"))
    creator = service.auth("client@example.com", "passw0rd!", "Client")
    bidder = service.auth("seller@example.com", "passw0rd!", "Seller")

    created = service.create_task(
        creator["token"],
        {
            "title": "Write a partner memo",
            "category": "Research",
            "public_brief": "Need a concise partner memo that summarizes market signals and next actions.",
            "private_brief": "Private scope includes customer names, deal notes, and internal opinions.",
            "reward_mana": 65,
            "prompt_tokens": 1400,
            "max_latency_ms": 1700,
            "budget_credits": 1.2,
            "quality_tier": "balanced",
            "task_type": "analysis",
        },
    )
    task_id = created["task"]["id"]
    service.submit_bid(
        bidder["token"],
        {
            "task_id": task_id,
            "pitch": "I can turn messy market notes into a clean partner-facing memo with clear actions.",
            "quote_mana": 65,
            "eta_days": 2,
        },
    )
    task_for_creator = service.get_dashboard(creator["token"], task_id=task_id)["selected_task"]
    service.award_bid(creator["token"], {"task_id": task_id, "bid_id": task_for_creator["bids"][0]["id"]})

    service.submit_task_submission(
        bidder["token"],
        {
            "task_id": task_id,
            "deliverable": "Draft memo covering signals, risks, and three next-step recommendations.",
            "submission_note": "Draft one for review.",
        },
    )
    before_complete = service.list_task_submissions(creator["token"], task_id)
    completed = service.complete_task(
        bidder["token"],
        {
            "task_id": task_id,
            "deliverable": "Final memo covering signals, risks, next steps, and a tighter executive summary.",
            "external_ref": "https://example.com/final-memo",
        },
    )
    after_complete = service.list_task_submissions(creator["token"], task_id)
    creator_wallet = service.get_wallet(creator["token"])

    assert len(before_complete["submissions"]) == 1
    assert before_complete["submissions"][0]["submission_note"] == "Draft one for review."
    assert len(after_complete["submissions"]) == 2
    assert completed["submission"]["version"] == 2
    assert creator_wallet["wallet"]["held_mana"] == 0
