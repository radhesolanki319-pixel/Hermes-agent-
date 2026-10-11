"""Comprehensive end-to-end test suite for hermes_core primitives."""

import os
import tempfile
import pytest

from hermes_core.persistence import SessionDB
from hermes_core.turn import TurnBudget, TurnContext, TurnEngine
from hermes_core.interrupt import ApprovalGate, InterruptBus
from hermes_core.compressor import ContextCompressor


def test_session_db_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        with SessionDB(db_path) as db:
            sid = db.create_session(source="test", title="Unit Test Session", system_prompt="System Prompt")
            assert sid is not None

            # Add messages
            db.add_message(sid, role="user", content="Deploy the update")
            db.add_message(sid, role="assistant", content="Deploying now")

            # Check messages
            msgs = db.get_messages(sid)
            assert len(msgs) == 2
            assert msgs[0]["content"] == "Deploy the update"

            # FTS search
            results = db.search_messages("update")
            assert len(results) >= 1
            assert results[0]["session_id"] == sid

            # Branch session
            bid = db.branch_session(sid, new_title="Branch 1")
            b_msgs = db.get_messages(bid)
            assert len(b_msgs) == 2

            # Checkpoint
            busy, log, ckpt = db.checkpoint("PASSIVE")
            assert busy == 0


def test_turn_engine_flow():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "turn.db")
        with SessionDB(db_path) as db:
            sid = db.create_session(source="turn_test")

            call_count = 0
            def mock_client(messages, tools=None):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return {
                        "content": "Checking status",
                        "tool_calls": [{"name": "get_status", "args": {"service": "db"}}]
                    }
                return {
                    "content": "All systems operational.",
                    "tool_calls": []
                }

            def mock_tool(name, args):
                return '{"status": "ok"}'

            engine = TurnEngine(session_db=db, model_client=mock_client, tool_executor=mock_tool)
            res = engine.execute_turn(sid, "System check please")

            assert res["final_response"] == "All systems operational."
            assert res["api_calls"] == 2
            assert res["tool_calls"] == 1


def test_interrupt_bus_and_approval():
    bus = InterruptBus()
    sid = "sess_interrupt"

    # Idle dispatch
    r1 = bus.dispatch_inbound_message(sid, "Hello")
    assert r1["admitted"] is True

    # Active turn registration
    ctx = TurnContext(session_id=sid)
    bus.register_active_turn(sid, ctx)

    # Inbound message gets queued
    r2 = bus.dispatch_inbound_message(sid, "Second message")
    assert r2["status"] == "queued"

    # Stop command bypasses queue
    r3 = bus.dispatch_inbound_message(sid, "/stop")
    assert r3["status"] == "interrupted"
    assert ctx.interrupted is True

    # Gate approval
    gate = bus.create_approval_gate("auth999", "Restart server")
    r4 = bus.dispatch_inbound_message(sid, "/approve auth999")
    assert r4["status"] == "approved"
    assert gate.wait() is True


def test_context_compressor():
    comp = ContextCompressor(max_tool_output_chars=50)
    msgs = [
        {"role": "user", "content": "Start"},
        {"role": "assistant", "content": "Running"},
        {"role": "tool", "content": "X" * 200},
        {"role": "assistant", "content": "Done"},
        {"role": "user", "content": "Next"},
        {"role": "assistant", "content": "Final"},
    ]

    pruned = comp.prune_tool_results(msgs, keep_recent_turns=1)
    assert len(pruned[2]["content"]) < 200
    assert "Output truncated" in pruned[2]["content"]
