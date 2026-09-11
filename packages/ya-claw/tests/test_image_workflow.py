"""Regression coverage for service image rebuild and publication boundaries."""

from fnmatch import fnmatchcase
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def workflow():
    data = yaml.safe_load((ROOT / ".github/workflows/claw-image.yaml").read_text())
    # PyYAML's YAML 1.1 resolver reads GitHub's literal `on` key as True.
    data["on"] = data.pop(True)
    return data


@pytest.mark.parametrize(
    "path",
    [
        "packages/ya-agent-sdk/ya_agent_sdk/capabilities/foundation/request.py",
        "packages/ya-agent-sdk/ya_agent_sdk/prompts/main.md",
        "packages/ya-agent-environment/ya_agent_environment/shell.py",
        "packages/ya-agent-stream-protocol/ya_agent_stream_protocol/__init__.py",
        "packages/ya-oauth/ya_oauth/__init__.py",
        "packages/ya-oauth-provider/ya_oauth_provider/__init__.py",
        "packages/ya-ripgrep-core/src/lib.rs",
        "packages/ya-ripgrep-core/Cargo.toml",
        "packages/ya-ripgrep-core/Cargo.lock",
        "packages/ya-claw/ya_claw/execution/runtime.py",
        "packages/ya-claw/ya_claw/alembic/script.py.mako",
        "packages/ya-claw/scripts/e2e_smoke.sh",
        "packages/ya-claw/docker-entrypoint.sh",
        "packages/ya-claw/profiles.yaml",
        "packages/ya-agent-platform/pyproject.toml",
        "packages/yaacli/pyproject.toml",
        "apps/ya-claw-web/src/main.tsx",
        "Dockerfile.ya-claw",
        ".dockerignore",
        "pyproject.toml",
        "uv.lock",
        "pnpm-lock.yaml",
        "pnpm-workspace.yaml",
        ".github/workflows/claw-image.yaml",
    ],
)
def test_image_inputs_trigger_push_and_pr_builds(workflow, path: str) -> None:
    for event in ("push", "pull_request"):
        assert any(fnmatchcase(path, pattern) for pattern in workflow["on"][event]["paths"]), (event, path)


def test_all_workspace_manifests_trigger_image_builds(workflow) -> None:
    for manifest in (ROOT / "packages").glob("*/pyproject.toml"):
        path = manifest.relative_to(ROOT).as_posix()
        assert any(fnmatchcase(path, pattern) for pattern in workflow["on"]["push"]["paths"]), path


def test_push_and_pr_filters_stay_aligned(workflow) -> None:
    assert workflow["on"]["push"]["paths"] == workflow["on"]["pull_request"]["paths"]
    assert workflow["on"]["push"]["branches"] == ["main"]


@pytest.mark.parametrize("path", ["README.md", "examples/general.py", "packages/yaacli/yaacli/app.py"])
def test_unrelated_sources_do_not_trigger_service_image(workflow, path: str) -> None:
    assert not any(fnmatchcase(path, pattern) for pattern in workflow["on"]["push"]["paths"])


def test_manual_dev_build_stays_on_main_and_release_tags_are_separate(workflow) -> None:
    assert "workflow_dispatch" in workflow["on"]
    jobs = workflow["jobs"]
    assert jobs["publish-dev"]["if"] == (
        "(github.event_name == 'push' || github.event_name == 'workflow_dispatch') && github.ref == 'refs/heads/main'"
    )
    assert jobs["validate"]["if"] == "github.event_name == 'pull_request'"
    assert jobs["publish-release"]["if"] == "github.event_name == 'release'"
    assert workflow["on"]["release"]["types"] == ["published"]
    metadata = next(step for step in jobs["publish-dev"]["steps"] if step.get("id") == "meta")
    assert metadata["with"]["tags"].strip() == "type=raw,value=dev"
    build = next(step for step in jobs["validate"]["steps"] if step["name"] == "Build YA Claw image")
    assert build["with"]["push"] is False
