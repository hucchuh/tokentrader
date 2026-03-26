from pathlib import Path

from tokentrader.service import TokenTraderService


def test_auth_creates_profile_and_starter_mana(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "auth.db"))

    auth = service.auth("alice@example.com", "passw0rd!", "Alice")
    dashboard = service.get_dashboard(auth["token"])

    assert auth["created"] is True
    assert dashboard["user"]["mana_balance"] == 240
    assert dashboard["profile"]["headline"] == "Independent claw operator"
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


def test_expert_scope_unlocks_only_after_secondary_verification(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "privacy.db"))
    creator = service.auth("client@example.com", "passw0rd!", "Client")
    bidder = service.auth("seller@example.com", "passw0rd!", "Seller")

    created = service.create_task(
        creator["token"],
        {
            "engagement_mode": "expert_polish",
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

    awaiting_verification = service.get_dashboard(bidder["token"], task_id=task_id)["selected_task"]
    assert awaiting_verification["status"] == "verifying"
    assert awaiting_verification["private_brief"] is None

    service.approve_secondary_verification(creator["token"], {"task_id": task_id})
    after_verify = service.get_dashboard(bidder["token"], task_id=task_id)["selected_task"]
    assert "confidential" in after_verify["private_brief"]


def test_quick_task_can_be_claimed_without_secondary_verification(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "quick.db"))
    creator = service.auth("client@example.com", "passw0rd!", "Client")
    claimer = service.auth("seller@example.com", "passw0rd!", "Seller")

    created = service.create_task(
        creator["token"],
        {
            "engagement_mode": "quick_api",
            "title": "Classify tickets by tag",
            "category": "Operations",
            "public_brief": "Need a claw to classify support tickets and return a compact summary for ops.",
            "private_brief": "Private scope includes ticket IDs, webhook targets, and the label taxonomy for the callback payload.",
            "reward_mana": 48,
            "prompt_tokens": 1200,
            "max_latency_ms": 1400,
            "budget_credits": 0.9,
            "quality_tier": "balanced",
            "task_type": "analysis",
        },
    )

    claimed = service.claim_task(claimer["token"], {"task_id": created["task"]["id"]})

    assert claimed["task"]["status"] == "awarded"
    assert claimed["task"]["secondary_verification_status"] == "not_required"
    assert claimed["task"]["assignee"]["id"] == claimer["user"]["id"]


def test_bid_award_complete_and_review_update_reputation(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "flow.db"))
    creator = service.auth("client@example.com", "passw0rd!", "Client")
    bidder = service.auth("seller@example.com", "passw0rd!", "Seller")

    created = service.create_task(
        creator["token"],
        {
            "engagement_mode": "expert_polish",
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
    service.approve_secondary_verification(creator["token"], {"task_id": task_id})
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
    assert created["task"]["engagement_mode"] == "quick_api"
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


def test_settings_persist_intake_mode_and_callback(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "settings.db"))
    user = service.auth("operator@example.com", "passw0rd!", "Operator")

    updated = service.update_settings(
        user["token"],
        {
            "intake_mode": "expert_only",
            "auto_claim_quick": False,
            "notify_on_rework": True,
            "callback_url": "https://example.com/hooks/claw",
        },
    )
    dashboard = service.get_dashboard(user["token"])

    assert updated["settings"]["intake_mode"] == "expert_only"
    assert updated["settings"]["quick_api_enabled"] is False
    assert updated["settings"]["expert_polish_enabled"] is True
    assert dashboard["settings"]["callback_url"] == "https://example.com/hooks/claw"
    assert set(dashboard["capability_scores"]) == {
        "logic",
        "diligence",
        "timeliness",
        "communication",
        "specialization",
        "reliability",
    }


def test_submission_history_and_escrow_release_are_persisted(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "submissions.db"))
    creator = service.auth("client@example.com", "passw0rd!", "Client")
    bidder = service.auth("seller@example.com", "passw0rd!", "Seller")

    created = service.create_task(
        creator["token"],
        {
            "engagement_mode": "expert_polish",
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
    service.approve_secondary_verification(creator["token"], {"task_id": task_id})

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


def test_request_rework_moves_task_back_to_assignee_queue(tmp_path: Path) -> None:
    service = TokenTraderService(db_path=str(tmp_path / "rework.db"))
    creator = service.auth("client@example.com", "passw0rd!", "Client")
    claw = service.auth("claw@example.com", "passw0rd!", "Claw")

    created = service.create_task(
        creator["token"],
        {
            "engagement_mode": "quick_api",
            "title": "Triage feedback backlog",
            "category": "Operations",
            "public_brief": "Need the backlog grouped into themes with suggested priorities for the ops lead.",
            "private_brief": "Private scope includes raw feedback, client names, and the callback endpoint.",
            "reward_mana": 52,
            "prompt_tokens": 1200,
            "max_latency_ms": 1300,
            "budget_credits": 0.9,
            "quality_tier": "balanced",
            "task_type": "analysis",
        },
    )
    task_id = created["task"]["id"]

    service.claim_task(claw["token"], {"task_id": task_id})
    service.submit_task_submission(
        claw["token"],
        {
            "task_id": task_id,
            "deliverable": "Draft grouped feedback into onboarding, pricing, and reliability themes for review.",
            "submission_note": "First pass.",
        },
    )

    returned = service.request_rework(
        creator["token"],
        {
            "task_id": task_id,
            "rework_note": "Please tighten the grouping logic and separate bugs from feature requests.",
        },
    )
    after_return = service.get_dashboard(claw["token"], task_id=task_id)["selected_task"]

    assert returned["task"]["status"] == "needs_rework"
    assert after_return["rework_note"].startswith("Please tighten")
    assert after_return["can_complete"] is True

    service.submit_task_submission(
        claw["token"],
        {
            "task_id": task_id,
            "deliverable": "Reworked draft separates bugs, feature requests, and onboarding friction with priorities.",
            "submission_note": "Second pass.",
        },
    )
    completed = service.complete_task(
        claw["token"],
        {
            "task_id": task_id,
            "deliverable": "Final backlog summary with separate bug buckets, feature requests, and recommended priorities.",
            "external_ref": "https://example.com/backlog-summary",
        },
    )

    assert completed["task"]["status"] == "done"
    assert completed["task"]["rework_note"] is None
