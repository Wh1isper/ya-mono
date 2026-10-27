from __future__ import annotations

from ya_agent_stream_protocol.agui import AguiReplayBuffer


def test_shared_replay_preserves_complete_text_and_tool_payloads() -> None:
    replay = AguiReplayBuffer()
    text = "text-" * 100_000
    tool_result = "result-" * 100_000

    replay.append({"type": "TEXT_MESSAGE_CHUNK", "messageId": "message-1", "delta": text})
    replay.append({
        "type": "TOOL_CALL_RESULT",
        "toolCallId": "tool-1",
        "messageId": "tool-1:result",
        "content": tool_result,
    })

    snapshot = replay.snapshot()
    assert snapshot[0]["delta"] == text
    assert snapshot[1]["content"] == tool_result


def test_replay_coalesces_fragments_and_shares_immutable_snapshots() -> None:
    replay = AguiReplayBuffer()
    for kind, key in [
        ("TEXT_MESSAGE_CHUNK", "messageId"),
        ("REASONING_MESSAGE_CHUNK", "messageId"),
        ("TOOL_CALL_CHUNK", "toolCallId"),
    ]:
        for i in range(20000):
            replay.append({"type": kind, key: "id", "delta": str(i % 10)})
    assert all(len(fragments) <= 15 for fragments in replay._chunk_fragments.values())
    first = replay.snapshot()
    second = replay.snapshot()
    assert all(event["delta"] == "0123456789" * 2000 for event in first)
    assert all(a["delta"] is b["delta"] for a, b in zip(first, second, strict=True))
    assert all(len(fragments) == 1 for fragments in replay._chunk_fragments.values())
    replay.append({"type": "TEXT_MESSAGE_CHUNK", "messageId": "id", "delta": "new"})
    assert replay.snapshot()[0]["delta"] == first[0]["delta"] + "new"
    assert first == second
