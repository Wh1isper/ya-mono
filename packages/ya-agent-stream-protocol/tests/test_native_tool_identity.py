"""Display identities distinguish calls without rewriting provider IDs."""

import pytest
from pydantic_ai import FunctionToolResultEvent, PartEndEvent, PartStartEvent
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from ya_agent_sdk.context import StreamEvent
from ya_agent_sdk.events import ModelRequestStartEvent
from ya_agent_stream_protocol.agui import AguiReplayBuffer
from ya_agent_stream_protocol.sdk import AguiAdapterConfig, AguiEventAdapter


@pytest.mark.parametrize("prefix", [None, "yaacli"])
def test_native_tool_ids_are_scoped_by_agent_and_occurrence(prefix) -> None:
    adapter = AguiEventAdapter(
        session_id="session",
        run_id="run",
        config=AguiAdapterConfig(run_event_prefix="test", stream_metadata_prefix=prefix),
    )
    replay = AguiReplayBuffer()

    def adapt(agent, event):
        events = adapter.adapt_stream_event(StreamEvent(agent_id=agent, agent_name=agent, event=event))
        for item in events:
            replay.append(item)
        return events

    call = ToolCallPart("lookup", '{"x":1}', tool_call_id="same-id")
    first = adapt("main", PartStartEvent(index=0, part=call))
    first_key = first[0]["toolCallKey"]
    assert first[1]["toolCallKey"] == first_key
    adapt("main", PartEndEvent(index=0, part=call))
    child = adapt("child", PartStartEvent(index=0, part=call))
    assert child[0]["toolCallKey"] != first_key

    # A deferred result in another SDK segment still completes the original call.
    adapt("main", ModelRequestStartEvent(event_id="segment-2", loop_index=0, message_count=3))
    result = ToolReturnPart("lookup", "done", tool_call_id="same-id")
    result_events = [
        adapt("main", event)[0]
        for event in [
            FunctionToolResultEvent(part=result),
            PartStartEvent(index=0, part=result),
            PartEndEvent(index=0, part=result),
        ]
    ]
    assert all(event["toolCallKey"] == first_key for event in result_events)
    assert len({event["messageId"] for event in result_events}) == 1
    child_result = adapt("child", FunctionToolResultEvent(part=result))[0]
    assert child_result["messageId"] != result_events[0]["messageId"]

    second = adapt("main", PartStartEvent(index=0, part=call))
    assert second[0]["toolCallKey"] not in {first_key, child[0]["toolCallKey"]}
    assert all(event["toolCallId"] == "same-id" for event in first + child + second + result_events)
    chunks = [event for event in replay.snapshot() if event["type"] == "TOOL_CALL_CHUNK"]
    assert len(chunks) == 3
    assert all(event["delta"] == '{"x":1}' for event in chunks)
    restored = AguiReplayBuffer()
    for event in replay.snapshot():
        restored.append(event)
    assert restored.snapshot() == replay.snapshot()
    other_run = AguiEventAdapter(
        session_id="session", run_id="other", config=AguiAdapterConfig(run_event_prefix="test")
    )
    other = other_run.adapt_stream_event(
        StreamEvent(agent_id="main", agent_name="main", event=PartStartEvent(index=0, part=call))
    )
    assert other[0]["toolCallKey"] != first_key
