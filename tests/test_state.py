import json

import pytest

from vertex_harness.domain import AcceptanceCriterion, Project, Task, TaskStatus
from vertex_harness.state import (
    ProjectStore,
    RevisionConflictError,
    StateAlreadyExistsError,
    StateFormatError,
    StateLockedError,
    StateNotFoundError,
)


def project() -> Project:
    first = Task(
        id="T-1",
        title="Create state",
        outcome="Project state survives another process",
        acceptance_criteria=(AcceptanceCriterion("AC-1", "State can be loaded"),),
    )
    second = Task(
        id="T-2",
        title="Use state",
        outcome="A dependent task can continue",
        acceptance_criteria=(AcceptanceCriterion("AC-2", "Dependency is retained"),),
        dependencies=("T-1",),
    )
    return Project("Build durable coordination", (first, second))


def test_initialize_and_load_round_trip(tmp_path):
    store = ProjectStore(tmp_path)
    initial = store.initialize(project())

    assert initial.revision == 0
    assert store.load() == initial
    assert store.path.stat().st_mode & 0o777 == 0o644

    raw = json.loads(store.path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 1
    assert raw["project"]["tasks"][1]["dependencies"] == ["T-1"]


def test_initialize_never_overwrites_existing_state(tmp_path):
    store = ProjectStore(tmp_path)
    original = store.initialize(project())

    with pytest.raises(StateAlreadyExistsError):
        store.initialize(Project("A different objective"))

    assert store.load() == original


def test_load_reports_missing_and_malformed_state(tmp_path):
    store = ProjectStore(tmp_path)
    with pytest.raises(StateNotFoundError):
        store.load()

    store.directory.mkdir()
    store.path.write_text("not json", encoding="utf-8")
    with pytest.raises(StateFormatError, match="valid JSON"):
        store.load()


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda data: data.update(schema_version=99), "unsupported schema"),
        (lambda data: data.update(revision=-1), "non-negative"),
        (lambda data: data["project"].update(extra=True), "unexpected extra"),
        (
            lambda data: data["project"]["tasks"][0].update(status="invented"),
            "unknown status",
        ),
    ],
)
def test_load_rejects_incompatible_or_invalid_data(tmp_path, change, message):
    store = ProjectStore(tmp_path)
    store.initialize(project())
    data = json.loads(store.path.read_text(encoding="utf-8"))
    change(data)
    store.path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(StateFormatError, match=message):
        store.load()


def test_update_is_atomic_and_increments_revision(tmp_path):
    store = ProjectStore(tmp_path)
    store.initialize(project())

    updated = store.update(lambda value: value.start_task("T-1"), expected_revision=0)

    assert updated.revision == 1
    assert updated.project.task("T-1").status is TaskStatus.ACTIVE
    assert store.load() == updated
    assert list(store.directory.glob(".project-*.tmp")) == []
    assert not store.lock_path.exists()


def test_update_rejects_stale_revision(tmp_path):
    store = ProjectStore(tmp_path)
    store.initialize(project())
    store.update(lambda value: value.start_task("T-1"), expected_revision=0)

    with pytest.raises(RevisionConflictError) as error:
        store.update(lambda value: value, expected_revision=0)

    assert error.value.expected == 0
    assert error.value.actual == 1


def test_update_fails_fast_when_another_writer_holds_the_lock(tmp_path):
    store = ProjectStore(tmp_path)
    original = store.initialize(project())
    store.lock_path.write_text("other writer\n", encoding="utf-8")

    with pytest.raises(StateLockedError):
        store.update(lambda value: value.start_task("T-1"))

    assert store.load() == original


def test_failed_transform_preserves_state_and_releases_lock(tmp_path):
    store = ProjectStore(tmp_path)
    original = store.initialize(project())

    def fail(_project):
        raise RuntimeError("transformation failed")

    with pytest.raises(RuntimeError, match="transformation failed"):
        store.update(fail)

    assert store.load() == original
    assert not store.lock_path.exists()


def test_transform_must_return_a_project(tmp_path):
    store = ProjectStore(tmp_path)
    original = store.initialize(project())

    with pytest.raises(TypeError, match="must return a Project"):
        store.update(lambda _project: None)  # type: ignore[arg-type,return-value]

    assert store.load() == original
