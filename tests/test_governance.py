from datetime import datetime, timezone

from dome_core.governance import (
    GovernanceEvent,
    hash_input_bytes,
    hash_input_dict,
    hash_input_text,
)


def test_governance_event_minimal():
    event = GovernanceEvent(
        agent_id="test-agent",
        action_type="test",
        timestamp=datetime.now(tz=timezone.utc),
        input_hash="abc123",
        input_type="text",
        output_summary="summary",
        rules_applied=["R-01"],
        rules_triggered=[],
        human_in_loop="not_required",
    )
    assert event.confidence is None
    assert event.user_id is None
    assert event.workflow_run_id is None
    assert event.metadata == {}


def test_governance_event_full():
    event = GovernanceEvent(
        agent_id="pa",
        action_type="analysis",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        input_hash="hash",
        input_type="process_description",
        output_summary="done",
        rules_applied=["R-01", "R-02"],
        rules_triggered=["R-01"],
        confidence=0.85,
        human_in_loop="recommended",
        user_id="user-123",
        workflow_run_id="wf-456",
        metadata={"model": "claude-sonnet-4-6"},
    )
    d = event.model_dump(mode="json")
    assert d["confidence"] == 0.85
    assert d["workflow_run_id"] == "wf-456"


def test_hash_input_text():
    h = hash_input_text("hello")
    assert len(h) == 64
    assert h == hash_input_text("hello")
    assert h != hash_input_text("world")


def test_hash_input_bytes():
    h = hash_input_bytes(b"hello")
    assert len(h) == 64


def test_hash_input_dict():
    h = hash_input_dict({"a": 1, "b": 2})
    assert h.startswith("sha256:")
    assert h == hash_input_dict({"b": 2, "a": 1})
