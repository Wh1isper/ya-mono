"""Tests for TUIEnvironment."""

from __future__ import annotations

from pathlib import Path

import pytest
from yaacli.environment import TUIEnvironment


class TestTUIEnvironment:
    """Tests for TUIEnvironment."""

    @pytest.mark.asyncio
    async def test_enter_exit(self, tmp_path: Path) -> None:
        """TUIEnvironment should enter and exit cleanly."""
        async with TUIEnvironment(default_path=tmp_path) as env:
            assert env.file_operator is not None
            assert env.shell is not None
            assert env.resources is not None

    @pytest.mark.asyncio
    async def test_background_shell_via_shell_abc(self, tmp_path: Path) -> None:
        """Shell ABC should support background process management."""
        async with TUIEnvironment(default_path=tmp_path) as env:
            # Start a background process via Shell ABC
            process_id = await env.shell.start("echo hello")

            # Should be tracked
            assert process_id in env.shell.active_background_processes

            # Wait and drain output
            stdout, stderr, is_running, exit_code = await env.shell.wait_process(process_id, timeout=5.0)
            assert exit_code == 0
            assert "hello" in stdout

    @pytest.mark.asyncio
    async def test_background_processes_killed_on_exit(self, tmp_path: Path) -> None:
        """Background shell processes should be killed when exiting context."""
        shell_ref = None

        async with TUIEnvironment(default_path=tmp_path) as env:
            await env.shell.start("sleep 10")
            shell_ref = env.shell

            # Process should be running
            assert env.shell.has_active_background_processes is True

        # After exit, shell.close() should have killed all processes
        assert shell_ref is not None
        assert shell_ref.has_active_background_processes is False

    @pytest.mark.asyncio
    async def test_inherits_local_environment_features(self, tmp_path: Path) -> None:
        """Should inherit file_operator and shell from LocalEnvironment."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        async with TUIEnvironment(default_path=tmp_path) as env:
            # File operator should work
            content = await env.file_operator.read_file("test.txt")
            assert content == "hello"

            # Shell should work
            exit_code, stdout, _ = await env.shell.execute("echo test")
            assert exit_code == 0
            assert "test" in stdout

    @pytest.mark.asyncio
    async def test_tmp_dir_created(self, tmp_path: Path) -> None:
        """Session tmp_dir should be created."""
        async with TUIEnvironment(default_path=tmp_path, enable_tmp_dir=True) as env:
            assert env.tmp_dir is not None
            assert env.tmp_dir.exists()

    @pytest.mark.asyncio
    async def test_tmp_dir_disabled(self, tmp_path: Path) -> None:
        """tmp_dir should be None when disabled."""
        async with TUIEnvironment(default_path=tmp_path, enable_tmp_dir=False) as env:
            assert env.tmp_dir is None
