"""
Shared test fixtures + Production-Is-The-Only-Truth pytest isolation.

Contract: docs/PRODUCTION_IS_THE_ONLY_TRUTH.md

Two hard rules enforced here:

  1. Before *any* test runs, KYC_DATA is pinned to a per-session temp dir
     (`os.environ["KYC_DATA"]`) AND `services.config.DATA` / `PROJECTS` are
     patched to point there. Tests cannot accidentally write to the
     canonical `data/` directory.

  2. At session start we snapshot the mtimes of canonical
     `data/intakes/`, `data/projects/`, `data/founding_pilot/`, and
     `data/ledger/`. At session end we assert nothing in those paths
     changed. A test that mutates the real disk loudly fails the session.

This exists because pytest pollution of canonical `data/` was the root cause
of the 2026-06-04 "40 intakes / 605 projects" forensic incident.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

# ── Production-Is-The-Only-Truth: pin KYC_DATA before *anything* imports services.config
_REPO_ROOT = Path(__file__).resolve().parents[1]
_CANONICAL_DATA = (_REPO_ROOT / "data").resolve()
_TEST_SESSION_DATA_ROOT = Path(
    tempfile.mkdtemp(prefix="kyc-pytest-session-")
).resolve()
os.environ["KYC_DATA"] = str(_TEST_SESSION_DATA_ROOT)
os.environ.setdefault("ENVIRONMENT", "test")
for _sub in ("intakes", "projects", "memory", "founding_pilot", "ledger", "logs"):
    (_TEST_SESSION_DATA_ROOT / _sub).mkdir(parents=True, exist_ok=True)

# Mirror repo-shipped READ-ONLY seed JSON into the session tmp. Tests load
# this via services.config.DATA / "..." so it must be present at the patched
# root. We never copy runtime-accumulation files (`*.jsonl`, `*.log`) — those
# are state, not seed, and starting clean each session is correct.
_SEED_SUBDIRS = ("knowledge_cockpit",)


def _mirror_seed_subdir(name: str) -> None:
    src = _CANONICAL_DATA / name
    if not src.is_dir():
        return
    dst = _TEST_SESSION_DATA_ROOT / name
    dst.mkdir(parents=True, exist_ok=True)
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in (".jsonl", ".log"):
            continue  # runtime accumulation, never seed
        rel = p.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)


for _sub in _SEED_SUBDIRS:
    _mirror_seed_subdir(_sub)

import pytest
from fastapi.testclient import TestClient

from server import app  # noqa: E402  (must follow env-var pinning above)
from services import config as _services_config  # noqa: E402

# Force the live module-level constants onto our session tmp dir.
_services_config.DATA = _TEST_SESSION_DATA_ROOT
_services_config.PROJECTS = _TEST_SESSION_DATA_ROOT / "projects"
_services_config.LOGS = _TEST_SESSION_DATA_ROOT / "logs"

TEST_OPS_PASSWORD = "test-ops-password-for-pytest"


# ── Canonical-data tripwire ─────────────────────────────────────────────────
_CANONICAL_GUARD_PATHS = ("intakes", "projects", "founding_pilot", "ledger")


def _snapshot_canonical_data() -> dict:
    snap: dict = {}
    for sub in _CANONICAL_GUARD_PATHS:
        root = _CANONICAL_DATA / sub
        if not root.exists():
            snap[sub] = None
            continue
        per_file: dict = {}
        for p in root.rglob("*"):
            try:
                st = p.stat()
            except OSError:
                continue
            per_file[str(p.relative_to(_CANONICAL_DATA))] = (st.st_size, st.st_mtime_ns)
        snap[sub] = per_file
    return snap


_CANONICAL_SNAPSHOT_BEFORE = _snapshot_canonical_data()


def pytest_sessionfinish(session, exitstatus):
    """Assert no test wrote to the canonical data/ directory during the run."""
    after = _snapshot_canonical_data()
    diffs: list[str] = []
    for sub in _CANONICAL_GUARD_PATHS:
        before = _CANONICAL_SNAPSHOT_BEFORE.get(sub) or {}
        nowmap = after.get(sub) or {}
        added = sorted(set(nowmap) - set(before))
        removed = sorted(set(before) - set(nowmap))
        mutated = sorted(
            k for k in (set(before) & set(nowmap)) if before[k] != nowmap[k]
        )
        for k in added:
            diffs.append(f"ADDED   data/{k}")
        for k in removed:
            diffs.append(f"REMOVED data/{k}")
        for k in mutated:
            diffs.append(f"MUTATED data/{k}")
    if diffs:
        msg = (
            "\n\n"
            "============================================================\n"
            "  CANONICAL DATA TRIPWIRE — TEST POLLUTED data/ DIRECTORY\n"
            "  Contract: docs/PRODUCTION_IS_THE_ONLY_TRUTH.md\n"
            "  Pytest is hard-isolated to KYC_DATA=" + str(_TEST_SESSION_DATA_ROOT) + "\n"
            "  The following canonical-data paths were touched anyway:\n"
        )
        for d in diffs[:50]:
            msg += "    - " + d + "\n"
        if len(diffs) > 50:
            msg += f"    ... and {len(diffs) - 50} more\n"
        msg += "============================================================\n"
        # Pytest doesn't read sessionfinish exit code from the return value
        # (it's an int from main loop), so we raise to make this loud.
        sys.stderr.write(msg)
        # Force a non-zero exit if the suite would otherwise pass.
        if exitstatus == 0:
            session.exitstatus = 1


@pytest.fixture(autouse=True)
def ops_password_env(monkeypatch):
    monkeypatch.setenv("OPS_PASSWORD", TEST_OPS_PASSWORD)
    monkeypatch.setenv("OPS_SECRET", "test-ops-secret-for-pytest")
    monkeypatch.delenv("ENVIRONMENT", raising=False)


@pytest.fixture(autouse=True)
def _isolated_kyc_data(monkeypatch):
    """
    Re-assert per-test that services.config.DATA / PROJECTS point at the
    session tmp dir. Some tests monkeypatch DATA themselves; this fixture
    runs AFTER such patches reset (function-scope teardown) and snaps the
    canonical pin back into place for the next test.

    The env var KYC_DATA is also pinned in case anything reads it lazily.
    """
    monkeypatch.setenv("KYC_DATA", str(_TEST_SESSION_DATA_ROOT))
    monkeypatch.setattr(_services_config, "DATA", _TEST_SESSION_DATA_ROOT, raising=False)
    monkeypatch.setattr(
        _services_config, "PROJECTS", _TEST_SESSION_DATA_ROOT / "projects", raising=False
    )
    yield


@pytest.fixture
def durable_intake_root(monkeypatch, tmp_path):
    """
    Isolated writable KYC_DATA for founding-pilot intake tests.
    Does not weaken production gates — tests must opt in explicitly.
    """
    root = tmp_path.resolve()
    (root / "intakes").mkdir(parents=True, exist_ok=True)
    (root / "projects").mkdir(parents=True, exist_ok=True)
    (root / "memory").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("KYC_DATA", str(root))
    monkeypatch.setenv("KYC_FOUNDING_PILOT_MODE", "true")
    monkeypatch.setattr("services.config.DATA", root)
    monkeypatch.setattr("services.config.PROJECTS", root / "projects")
    from services.durable_storage import (
        founding_pilot_upload_allowed,
        is_durable_storage_configured,
    )

    assert is_durable_storage_configured() is True
    assert founding_pilot_upload_allowed() is True
    from services.intake.durable_root import initialize_mount_probe

    initialize_mount_probe()
    return root


@pytest.fixture
def fb_data(durable_intake_root):
    """Alias — canonical durable intake root for founding-pilot tests."""
    return durable_intake_root


@pytest.fixture
def fb_env(durable_intake_root, monkeypatch):
    """Durable intake root + founding-pilot learning hook path."""
    mem = durable_intake_root / "memory"
    monkeypatch.setattr(
        "services.intake.learning_hooks._LEARNING",
        mem / "learning_state.json",
    )
    return durable_intake_root


@pytest.fixture
def prod_env(monkeypatch):
    """Production ENVIRONMENT — use with explicit KYC_DATA or expect 503."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("KYC_FOUNDING_PILOT_MODE", "true")


@pytest.fixture(autouse=True)
def _clear_knowledge_cockpit_caches():
    """Prevent lru_cache from retaining concepts loaded under a patched DATA root."""
    yield
    try:
        from services.knowledge_cockpit import concept_graph, encyclopedia

        encyclopedia._load_concepts_payload.cache_clear()
        encyclopedia.load_authoritative_sources.cache_clear()
        encyclopedia.load_control_matrix.cache_clear()
        encyclopedia.load_control_xref.cache_clear()
        concept_graph._edges.cache_clear()
    except Exception:
        pass


@pytest.fixture
def anon_client():
    """Unauthenticated client (public routes + 403/302 checks)."""
    return TestClient(app)


@pytest.fixture
def client():
    """Authenticated operator session."""
    c = TestClient(app)
    r = c.post("/api/ops/login", json={"password": TEST_OPS_PASSWORD})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def ops_client(client):
    return client


def login_ops(c: TestClient) -> None:
    r = c.post("/api/ops/login", json={"password": TEST_OPS_PASSWORD})
    assert r.status_code == 200


@pytest.fixture
def reddit_env(monkeypatch, tmp_path):
    """Isolated DATA tree for Reddit acquisition connector tests."""
    intel = tmp_path / "intelligence"
    intel.mkdir(parents=True)
    leads = tmp_path / "leads"
    leads.mkdir(parents=True)
    (leads / "leads.jsonl").write_text("", encoding="utf-8")
    projects = tmp_path / "projects"
    projects.mkdir(parents=True)
    mem = tmp_path / "memory"
    mem.mkdir()

    monkeypatch.setattr("services.config.DATA", tmp_path)
    monkeypatch.setattr("services.config.PROJECTS", projects)
    monkeypatch.setattr("services.acquisition.intelligence_paths.ACQ_ROOT", tmp_path)
    monkeypatch.setattr("services.acquisition.intelligence_paths.INTEL_DIR", intel)
    monkeypatch.setattr("services.acquisition.intelligence_paths.LEADS_DIR", leads)
    monkeypatch.setattr("services.acquisition.storage.DEFAULT_LEADS_DIR", leads)
    monkeypatch.setattr("services.acquisition.storage.leads_dir", lambda base_dir=None: leads)
    monkeypatch.setattr("services.acquisition.orchestration.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.telemetry.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.learning.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.memory.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.memory.telemetry.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.entity_graph.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.entity_graph.MEMORY_DIR", mem)
    from services.acquisition.intelligence_paths import ensure_intel_dirs

    ensure_intel_dirs()
    return tmp_path
