from pathlib import Path

from ya_agent_sdk.agents.main import create_agent
from ya_agent_sdk.environment.local import LocalEnvironment
from ya_agent_sdk.filters.auto_load_files import process_auto_load_files


async def test_create_agent_runs_auto_load_files_after_compact(tmp_path: Path) -> None:
    env = LocalEnvironment(
        allowed_paths=[tmp_path],
        default_path=tmp_path,
        tmp_base_dir=tmp_path,
    )

    async with create_agent(
        model="test",
        env=env,
    ) as runtime:
        processors = runtime.agent.history_processors
        auto_load_indexes = [i for i, processor in enumerate(processors) if processor is process_auto_load_files]

        assert len(auto_load_indexes) == 2
        assert auto_load_indexes[-1] > auto_load_indexes[0]
