"""Tests for MemoryManager and memory integration in AgentContext."""

from ya_agent_sdk.context.memory import MemoryManager


def test_memory_manager_set_and_get():
    """Test basic set and get operations."""
    manager = MemoryManager()
    manager.set("lang", "Chinese")
    assert manager.get("lang") == "Chinese"
    assert manager.get("missing") is None


def test_memory_manager_update_existing():
    """Test that set overwrites existing value."""
    manager = MemoryManager()
    manager.set("lang", "Chinese")
    manager.set("lang", "English")
    assert manager.get("lang") == "English"


def test_memory_manager_delete():
    """Test delete operation."""
    manager = MemoryManager()
    manager.set("lang", "Chinese")
    assert manager.delete("lang") is True
    assert manager.get("lang") is None
    assert manager.delete("lang") is False


def test_memory_manager_list_all():
    """Test list_all returns sorted entries."""
    manager = MemoryManager()
    manager.set("z-key", "last")
    manager.set("a-key", "first")
    manager.set("m-key", "middle")
    entries = manager.list_all()
    assert entries == [("a-key", "first"), ("m-key", "middle"), ("z-key", "last")]


def test_memory_manager_list_all_empty():
    """Test list_all with no entries."""
    manager = MemoryManager()
    assert manager.list_all() == []


def test_memory_manager_export_and_restore():
    """Test export and restore round-trip."""
    manager = MemoryManager()
    manager.set("lang", "Chinese")
    manager.set("os", "macOS")

    exported = manager.export_memory()
    assert exported == {"lang": "Chinese", "os": "macOS"}

    restored = MemoryManager.from_exported(exported)
    assert restored.get("lang") == "Chinese"
    assert restored.get("os") == "macOS"


def test_memory_manager_from_exported_empty():
    """Test restore from empty data."""
    restored = MemoryManager.from_exported({})
    assert restored.list_all() == []


def test_memory_in_resumable_state():
    """Test that memory is included in ResumableState export/restore."""
    from ya_agent_sdk.context import ResumableState

    state = ResumableState(memory={"lang": "Chinese", "os": "macOS"})
    assert state.memory == {"lang": "Chinese", "os": "macOS"}

    # Verify it can be serialized to JSON and back
    json_str = state.model_dump_json()
    restored_state = ResumableState.model_validate_json(json_str)
    assert restored_state.memory == {"lang": "Chinese", "os": "macOS"}


async def test_memory_in_export_state():
    """Test that AgentContext.export_state includes memory."""
    from ya_agent_sdk.context import AgentContext

    async with AgentContext() as ctx:
        ctx.memory_manager.set("lang", "Chinese")
        ctx.memory_manager.set("os", "macOS")

        state = ctx.export_state()
        assert state.memory == {"lang": "Chinese", "os": "macOS"}


async def test_memory_restore_via_with_state():
    """Test full round-trip: export -> restore via with_state."""
    from ya_agent_sdk.context import AgentContext

    # Create and populate
    async with AgentContext() as ctx1:
        ctx1.memory_manager.set("lang", "Chinese")
        state = ctx1.export_state()

    # Restore into new context
    async with AgentContext().with_state(state) as ctx2:
        assert ctx2.memory_manager.get("lang") == "Chinese"


async def test_memory_in_context_instructions():
    """Test that memory entries appear in runtime instructions XML."""
    from ya_agent_sdk.context import AgentContext

    async with AgentContext() as ctx:
        ctx.memory_manager.set("lang", "Chinese")
        ctx.memory_manager.set("os", "macOS")

        instructions = await ctx.get_context_instructions(is_user_prompt=True)
        assert "<memory>" in instructions
        assert 'key="lang"' in instructions
        assert "Chinese" in instructions
        assert 'key="os"' in instructions
        assert "macOS" in instructions


async def test_memory_not_in_instructions_when_empty():
    """Test that empty memory does not produce memory element."""
    from ya_agent_sdk.context import AgentContext

    async with AgentContext() as ctx:
        instructions = await ctx.get_context_instructions(is_user_prompt=True)
        assert "<memory>" not in instructions


async def test_memory_not_in_instructions_for_tool_response():
    """Test that memory is excluded from tool response instructions."""
    from ya_agent_sdk.context import AgentContext

    async with AgentContext() as ctx:
        ctx.memory_manager.set("lang", "Chinese")

        instructions = await ctx.get_context_instructions(is_user_prompt=False)
        assert "<memory>" not in instructions
