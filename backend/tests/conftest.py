from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def sample_agents(fixtures_dir: Path) -> list[dict]:
    return json.loads((fixtures_dir / "sample_agents.json").read_text())


@pytest.fixture(scope="session")
def sample_matches(fixtures_dir: Path) -> list[dict]:
    return json.loads((fixtures_dir / "sample_matches.json").read_text())


@pytest.fixture(scope="session")
def sample_events(fixtures_dir: Path) -> list[dict]:
    return json.loads((fixtures_dir / "sample_events.json").read_text())


@pytest.fixture(scope="session")
def simulation_module(project_root: Path):
    simulation_path = project_root / "backend" / "arena-engine" / "simulation.py"
    spec = importlib.util.spec_from_file_location("arena_simulation", simulation_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load arena simulation module")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
