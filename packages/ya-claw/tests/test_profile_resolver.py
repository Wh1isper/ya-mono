from __future__ import annotations

from pathlib import Path

import pytest
import ya_claw.execution.profile as profile_module
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from ya_claw.config import ClawSettings
from ya_claw.db.engine import create_engine, create_session_factory
from ya_claw.execution.profile import ProfileResolver
from ya_claw.orm.base import Base
from ya_claw.orm.tables import ProfileRecord


@pytest.fixture
async def db_engine(tmp_path: Path) -> AsyncEngine:
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'profile.sqlite3').resolve()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncSession:
    session_factory = create_session_factory(db_engine)
    async with session_factory() as session:
        yield session


async def test_profile_resolver_seeds_profiles_from_yaml(tmp_path: Path, db_engine: AsyncEngine) -> None:
    seed_file = tmp_path / "profiles.yaml"
    seed_file.write_text(
        """
profiles:
  - name: default
    model: gateway@openai-responses:gpt-5.4
    model_settings_preset: openai_responses_high
    model_config_preset: gpt5_270k
    toolsets: [filesystem, shell]
    include_builtin_subagents: true
    unified_subagents: true
    workspace_backend_hint: docker
""".strip(),
        encoding="utf-8",
    )
    settings = ClawSettings(
        api_token="test-token",  # noqa: S106
        data_dir=tmp_path / "runtime-data",
        workspace_root=tmp_path / "workspace",
        profile_seed_file=seed_file,
    )
    session_factory = create_session_factory(db_engine)
    resolver = ProfileResolver(settings=settings, session_factory=session_factory)

    seeded_names = await resolver.seed_profiles()
    resolved_profile = await resolver.resolve("default")

    assert seeded_names == ["default"]
    assert resolved_profile.model == "gateway@openai-responses:gpt-5.4"
    assert resolved_profile.include_builtin_subagents is True
    assert resolved_profile.unified_subagents is True
    assert resolved_profile.workspace_backend_hint == "docker"

    async with session_factory() as db_session:
        record = await db_session.get(ProfileRecord, "default")
        assert isinstance(record, ProfileRecord)
        assert record.source_checksum is not None
        assert record.include_builtin_subagents is True
        assert record.unified_subagents is True


async def test_bootstrap_profile_loads_default_yaacli_subagents(
    tmp_path: Path,
    db_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    yaacli_dir = tmp_path / ".yaacli"
    subagents_dir = yaacli_dir / "subagents"
    subagents_dir.mkdir(parents=True, exist_ok=True)
    (subagents_dir / "explorer.md").write_text(
        """
---
name: explorer
description: Explore the codebase
tools:
  - view
  - grep
model: inherit
---
You explore the codebase.
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(profile_module, "_DEFAULT_YAACLI_CONFIG_DIR", yaacli_dir)

    settings = ClawSettings(
        api_token="test-token",  # noqa: S106
        data_dir=tmp_path / "runtime-data",
        workspace_root=tmp_path / "workspace",
        execution_model="test",
    )
    session_factory = create_session_factory(db_engine)
    resolver = ProfileResolver(settings=settings, session_factory=session_factory)

    resolved_profile = await resolver.resolve(None)

    assert resolved_profile.toolsets == ["core"]
    assert resolved_profile.workspace_backend_hint is None
    assert resolved_profile.unified_subagents is True
    assert [config.name for config in resolved_profile.subagent_configs] == ["explorer"]
