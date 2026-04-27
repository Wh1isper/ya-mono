"""Tests for stream_agent resume-on-error behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from ya_agent_sdk.agents.main import create_agent, stream_agent
from ya_agent_sdk.environment.local import LocalEnvironment
from ya_agent_sdk.events import AgentExecutionFailedEvent, AgentExecutionResumeEvent, AgentExecutionStartEvent


def _make_runtime(tmp_path: Path, model: FunctionModel):
    env = LocalEnvironment(
        allowed_paths=[tmp_path],
        default_path=tmp_path,
        tmp_base_dir=tmp_path,
    )
    return create_agent(model=model, env=env)


async def test_stream_agent_resumes_after_stream_error(tmp_path: Path) -> None:
    calls: list[list[ModelMessage]] = []

    async def stream_function(messages: list[ModelMessage], _agent_info: AgentInfo):
        calls.append(list(messages))
        if len(calls) == 1:
            yield "partial answer"
            raise RuntimeError("simulated sse disconnect")
        yield " resumed answer"

    runtime = _make_runtime(tmp_path, FunctionModel(stream_function=stream_function))
    events: list[Any] = []

    async with stream_agent(
        runtime,
        "start task",
        resume_on_error=True,
        resume_max_attempts=2,
        resume_prompt="continue from checkpoint",
    ) as streamer:
        async for event in streamer:
            events.append(event.event)

        streamer.raise_if_exception()

    assert len(calls) == 2
    resume_messages = calls[1]
    assert len(resume_messages) == 1
    resume_request = resume_messages[0]
    assert isinstance(resume_request, ModelRequest)
    assert any(isinstance(part, UserPromptPart) and part.content == "start task" for part in resume_request.parts)
    assert any(
        isinstance(part, UserPromptPart) and part.content == "continue from checkpoint" for part in resume_request.parts
    )
    assert not any(isinstance(message, ModelResponse) for message in resume_messages)
    assert streamer.run is not None
    assert streamer.run.result is not None
    assert streamer.run.result.output == " resumed answer"
    assert any(isinstance(event, AgentExecutionFailedEvent) and event.recoverable for event in events)
    assert any(isinstance(event, AgentExecutionResumeEvent) for event in events)
    start_events = [event for event in events if isinstance(event, AgentExecutionStartEvent)]
    assert [event.attempt_index for event in start_events] == [0, 1]
    assert start_events[1].is_resume_attempt is True


async def test_stream_agent_raises_after_resume_attempts_exhausted(tmp_path: Path) -> None:
    async def stream_function(_messages: list[ModelMessage], _agent_info: AgentInfo):
        yield "partial"
        raise RuntimeError("still disconnected")

    runtime = _make_runtime(tmp_path, FunctionModel(stream_function=stream_function))
    events: list[Any] = []

    with pytest.raises(RuntimeError, match="still disconnected"):
        async with stream_agent(
            runtime,
            "start task",
            resume_on_error=True,
            resume_max_attempts=2,
        ) as streamer:
            async for event in streamer:
                events.append(event.event)

    failed_events = [event for event in events if isinstance(event, AgentExecutionFailedEvent)]
    assert len(failed_events) == 2
    assert failed_events[0].recoverable is True
    assert failed_events[1].recoverable is False


async def test_stream_agent_closes_unreturned_tool_calls_before_resume(tmp_path: Path) -> None:
    calls: list[list[ModelMessage]] = []
    history = [
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="shell_exec",
                    args={"command": "pytest"},
                    tool_call_id="call-1",
                )
            ]
        )
    ]

    async def stream_function(messages: list[ModelMessage], _agent_info: AgentInfo):
        calls.append(list(messages))
        if len(calls) == 1:
            raise RuntimeError("simulated tool stream disconnect")
        yield "resumed after tool closure"

    runtime = _make_runtime(tmp_path, FunctionModel(stream_function=stream_function))

    async with stream_agent(
        runtime,
        "continue task",
        message_history=history,
        resume_on_error=True,
        resume_max_attempts=2,
    ) as streamer:
        async for _event in streamer:
            pass
        streamer.raise_if_exception()

    assert len(calls) == 2
    resume_messages = calls[1]
    assert len(resume_messages) >= 2
    tool_closure = next(
        message
        for message in resume_messages
        if isinstance(message, ModelRequest) and any(isinstance(part, ToolReturnPart) for part in message.parts)
    )
    tool_returns = [part for part in tool_closure.parts if isinstance(part, ToolReturnPart)]
    assert len(tool_returns) == 1
    assert tool_returns[0].tool_name == "shell_exec"
    assert tool_returns[0].tool_call_id.startswith("ya-")
    assert tool_returns[0].outcome == "failed"
    assert "new user prompt requested before tool results" in str(tool_returns[0].content)
    resume_request = resume_messages[-1]
    assert isinstance(resume_request, ModelRequest)
    assert any(isinstance(part, UserPromptPart) for part in resume_request.parts)


async def test_stream_agent_treats_retry_prompt_as_tool_call_completion(tmp_path: Path) -> None:
    calls: list[list[ModelMessage]] = []
    history = [
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="shell_exec",
                    args={"command": "pytest"},
                    tool_call_id="call-1",
                )
            ]
        ),
        ModelRequest(
            parts=[
                RetryPromptPart(
                    tool_name="shell_exec",
                    tool_call_id="call-1",
                    content="retry with corrected arguments",
                )
            ]
        ),
    ]

    async def stream_function(messages: list[ModelMessage], _agent_info: AgentInfo):
        calls.append(list(messages))
        if len(calls) == 1:
            raise RuntimeError("simulated retry stream disconnect")
        yield "resumed after retry prompt"

    runtime = _make_runtime(tmp_path, FunctionModel(stream_function=stream_function))

    async with stream_agent(
        runtime,
        "continue task",
        message_history=history,
        resume_on_error=True,
        resume_max_attempts=2,
    ) as streamer:
        async for _event in streamer:
            pass
        streamer.raise_if_exception()

    assert len(calls) == 2
    resume_messages = calls[1]
    synthetic_tool_returns = [
        part
        for message in resume_messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]
    assert synthetic_tool_returns == []
    assert any(
        isinstance(message, ModelRequest) and any(isinstance(part, RetryPromptPart) for part in message.parts)
        for message in resume_messages
    )


async def test_stream_agent_emits_failed_event_for_runtime_setup_error(tmp_path: Path) -> None:
    async def user_prompt_factory(_runtime):
        raise RuntimeError("prompt factory failed")

    runtime = _make_runtime(tmp_path, FunctionModel(stream_function=lambda _messages, _agent_info: iter(())))
    events: list[Any] = []

    with pytest.raises(RuntimeError, match="prompt factory failed"):
        async with stream_agent(
            runtime,
            user_prompt_factory=user_prompt_factory,
        ) as streamer:
            async for event in streamer:
                events.append(event.event)

    failed_events = [event for event in events if isinstance(event, AgentExecutionFailedEvent)]
    assert len(failed_events) == 1
    assert failed_events[0].error == "prompt factory failed"
    assert failed_events[0].error_type == "RuntimeError"
    assert failed_events[0].recoverable is False


async def test_stream_agent_reports_cumulative_duration_across_resume_attempts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    clock = {"now": 100.0}
    monkeypatch.setattr("ya_agent_sdk.agents.main.time.perf_counter", lambda: clock["now"])

    async def stream_function(_messages: list[ModelMessage], _agent_info: AgentInfo):
        nonlocal calls
        calls += 1
        if calls == 1:
            clock["now"] += 10.0
            raise RuntimeError("temporary disconnect")
        clock["now"] += 20.0
        yield "resumed"

    runtime = _make_runtime(tmp_path, FunctionModel(stream_function=stream_function))
    events: list[Any] = []

    async with stream_agent(
        runtime,
        "start task",
        resume_on_error=True,
        resume_max_attempts=2,
    ) as streamer:
        async for event in streamer:
            events.append(event.event)
        streamer.raise_if_exception()

    failed_event = next(event for event in events if isinstance(event, AgentExecutionFailedEvent))
    complete_event = next(event for event in events if event.__class__.__name__ == "AgentExecutionCompleteEvent")
    assert failed_event.total_duration_seconds == 10.0
    assert complete_event.total_duration_seconds == 30.0
