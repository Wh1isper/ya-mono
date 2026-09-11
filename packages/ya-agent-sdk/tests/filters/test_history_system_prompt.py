"""System prompt regression tests through the real runtime foundation pipeline."""

from collections.abc import AsyncIterator
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage
from ya_agent_sdk.agents.main import create_agent
from ya_agent_sdk.capabilities import RuntimeFoundationCapability
from ya_agent_sdk.context import ModelConfig


def _system_contents(messages: list[ModelMessage]) -> list[str]:
    return [
        part.content
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, SystemPromptPart)
    ]


def _assert_system_prompt(messages: list[ModelMessage], expected: list[str]) -> None:
    assert _system_contents(messages) == expected
    assert "Placeholder" not in str(messages)
    if expected:
        first = messages[0]
        assert isinstance(first, ModelRequest)
        assert [part.content for part in first.parts[: len(expected)]] == expected
        assert all(isinstance(part, SystemPromptPart) for part in first.parts[: len(expected)])


@pytest.mark.parametrize("inline_system_prompts", [False, True])
async def test_runtime_preserves_system_prompt_across_turns(tmp_path: Path, inline_system_prompts: bool) -> None:
    requests: list[list[ModelMessage]] = []

    def respond(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        requests.append(deepcopy(messages))
        return ModelResponse(parts=[TextPart(content="Answer")])

    async with create_agent(
        FunctionModel(respond, profile={"supports_inline_system_prompts": inline_system_prompts}),
        system_prompt="REAL SYSTEM",
        capabilities=[RuntimeFoundationCapability()],
        env_kwargs={"allowed_paths": [tmp_path], "default_path": tmp_path, "tmp_base_dir": tmp_path},
    ) as runtime:
        first = await runtime.agent.run("First turn", deps=runtime.ctx)
        first_history = deepcopy(first.all_messages())
        second = await runtime.agent.run("Second turn", deps=runtime.ctx, message_history=first.all_messages())

    assert len(requests) == 2
    for messages in [*requests, first.all_messages(), second.all_messages()]:
        _assert_system_prompt(messages, ["REAL SYSTEM"])
    assert requests[1][: len(first_history)] == first_history
    assert first.all_messages() == first_history
    assert "<runtime-context>" in str(requests[0])
    assert "<file-system>" in str(requests[0])


@pytest.mark.parametrize("system_prompt", ["REAL SYSTEM", ""])
@pytest.mark.parametrize("inline_system_prompts", [False, True])
async def test_handoff_tool_restores_configured_system_prompt(
    tmp_path: Path, system_prompt: str, inline_system_prompts: bool
) -> None:
    requests: list[list[ModelMessage]] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        requests.append(deepcopy(messages))
        if len(requests) == 1:
            assert "summarize" in [tool.name for tool in info.function_tools]
            return ModelResponse(
                parts=[ToolCallPart("summarize", {"content": "HANDOFF SUMMARY"}, tool_call_id="handoff")]
            )
        return ModelResponse(parts=[TextPart(content="Continued after handoff")])

    async with create_agent(
        FunctionModel(respond, profile={"supports_inline_system_prompts": inline_system_prompts}),
        system_prompt=system_prompt,
        capabilities=[RuntimeFoundationCapability()],
        env_kwargs={"allowed_paths": [tmp_path], "default_path": tmp_path, "tmp_base_dir": tmp_path},
    ) as runtime:
        result = await runtime.agent.run("Start work", deps=runtime.ctx)
        assert runtime.ctx.handoff_message is None

    assert result.output == "Continued after handoff"
    assert len(requests) == 2
    for messages in [*requests, result.all_messages()]:
        # Native Pydantic AI preserves an explicitly configured empty prompt as an empty part.
        _assert_system_prompt(messages, [system_prompt])
    assert "HANDOFF SUMMARY" in str(requests[1])
    assert "context-restored" in str(requests[1])
    assert not any(isinstance(message, ModelResponse) for message in requests[1])
    assert "<runtime-context>" in str(requests[1])
    assert "<file-system>" in str(requests[1])


@pytest.mark.parametrize("system_prompt", ["REAL SYSTEM", ""])
@pytest.mark.parametrize("inline_system_prompts", [False, True])
async def test_cache_friendly_compact_restores_configured_system_prompt(
    tmp_path: Path, system_prompt: str, inline_system_prompts: bool
) -> None:
    requests: list[list[ModelMessage]] = []
    summary_requests: list[list[ModelMessage]] = []

    def respond(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        requests.append(deepcopy(messages))
        return ModelResponse(parts=[TextPart(content="Continued after compact")])

    async def summarize(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        summary_requests.append(deepcopy(messages))
        assert info.model_settings is not None
        assert info.model_settings["tool_choice"] == "none"
        yield "COMPACT SUMMARY"

    history: list[ModelMessage] = [
        ModelRequest(parts=[UserPromptPart(content="Old task")]),
        ModelResponse(parts=[TextPart(content="Old answer")], usage=RequestUsage(input_tokens=9000)),
    ]
    if system_prompt:
        history[0] = ModelRequest(parts=[SystemPromptPart(system_prompt), UserPromptPart(content="Old task")])
    original_history = deepcopy(history)

    async with create_agent(
        FunctionModel(
            respond,
            stream_function=summarize,
            profile={"supports_inline_system_prompts": inline_system_prompts},
        ),
        system_prompt=system_prompt,
        capabilities=[RuntimeFoundationCapability()],
        model_cfg=ModelConfig(context_window=10000, compact_threshold=0.8),
        env_kwargs={"allowed_paths": [tmp_path], "default_path": tmp_path, "tmp_base_dir": tmp_path},
    ) as runtime:
        result = await runtime.agent.run("Continue work", deps=runtime.ctx, message_history=history)
        assert runtime.ctx._compact_depth == 0
        compact_entries = [entry for entry in runtime.ctx.build_usage_snapshot().entries if entry.agent_id == "compact"]
        assert len(compact_entries) == 1

    assert result.output == "Continued after compact"
    assert len(summary_requests) == len(requests) == 1
    for messages in [*summary_requests, *requests, result.all_messages()]:
        # Native Pydantic AI preserves an explicitly configured empty prompt as an empty part.
        _assert_system_prompt(messages, [system_prompt])
    assert "Old answer" in str(summary_requests[0])
    assert "Old answer" not in str(requests[0])
    assert "COMPACT SUMMARY" in str(requests[0])
    assert "context-restored" in str(requests[0])
    assert "<runtime-context>" in str(requests[0])
    assert "<file-system>" in str(requests[0])
    assert history == original_history


async def test_trusted_existing_system_prompts_are_not_replaced(tmp_path: Path) -> None:
    requests: list[list[ModelMessage]] = []

    def respond(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        requests.append(deepcopy(messages))
        return ModelResponse(parts=[TextPart(content="Answer")])

    history: list[ModelMessage] = [
        ModelRequest(
            parts=[
                SystemPromptPart(content="TRUSTED SYSTEM ONE"),
                SystemPromptPart(content="TRUSTED SYSTEM TWO"),
                UserPromptPart(content="Original input"),
            ]
        ),
        ModelResponse(parts=[TextPart(content="Original answer")]),
    ]
    original_history = deepcopy(history)
    async with create_agent(
        FunctionModel(respond, profile={"supports_inline_system_prompts": False}),
        system_prompt="REAL SYSTEM",
        capabilities=[RuntimeFoundationCapability()],
        env_kwargs={"allowed_paths": [tmp_path], "default_path": tmp_path, "tmp_base_dir": tmp_path},
    ) as runtime:
        result = await runtime.agent.run("Continue", deps=runtime.ctx, message_history=history)

    assert len(requests) == 1
    for messages in [requests[0], result.all_messages()]:
        _assert_system_prompt(messages, ["TRUSTED SYSTEM ONE", "TRUSTED SYSTEM TWO"])
    assert history == original_history
