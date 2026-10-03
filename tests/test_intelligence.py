from pathlib import Path

from vertex_harness.intelligence import IndexStore, QueryService, build_index


def write_python_project(root: Path) -> None:
    package = root / "src" / "demo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "from .service import Service\n", encoding="utf-8"
    )
    (package / "util.py").write_text(
        "def format_name(value):\n    return value.strip()\n", encoding="utf-8"
    )
    (package / "service.py").write_text(
        "from demo.util import format_name\n\n"
        "class Service:\n"
        "    def run(self, value):\n"
        "        return format_name(value)\n\n"
        "async def load_service():\n"
        "    return Service()\n",
        encoding="utf-8",
    )
    (root / "app.py").write_text(
        "from demo.service import Service\n\nservice = Service()\n", encoding="utf-8"
    )
    (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")


def test_index_extracts_python_symbols_imports_and_issues(tmp_path):
    write_python_project(tmp_path)

    index = build_index(tmp_path)

    service = index.source("src/demo/service.py")
    assert service is not None
    assert service.module == "demo.service"
    assert [(symbol.qualified_name, symbol.kind) for symbol in service.symbols] == [
        ("Service", "class"),
        ("Service.run", "method"),
        ("load_service", "async_function"),
    ]
    assert service.imports[0].module == "demo.util"
    assert service.imports[0].resolved_path == "src/demo/util.py"
    assert index.issues[0].path == "broken.py"


def test_query_reports_search_dependencies_and_transitive_impact(tmp_path):
    write_python_project(tmp_path)
    IndexStore(tmp_path).rebuild()
    service = QueryService()

    search = service.execute(tmp_path, "search", "run")
    assert search["stale"] is False
    assert search["results"][0]["qualified_name"] == "Service.run"

    dependencies = service.execute(tmp_path, "dependencies", "src/demo/service.py")
    assert dependencies["results"][0]["resolved_path"] == "src/demo/util.py"

    impact = service.execute(tmp_path, "impact", "src/demo/util.py")
    assert impact["results"] == [
        {"path": "src/demo/service.py", "distance": 1},
        {"path": "app.py", "distance": 2},
        {"path": "src/demo/__init__.py", "distance": 2},
    ]


def test_query_marks_index_stale_after_source_changes(tmp_path):
    write_python_project(tmp_path)
    store = IndexStore(tmp_path)
    original = store.rebuild()
    (tmp_path / "app.py").write_text("value = 2\n", encoding="utf-8")

    payload = QueryService().execute(tmp_path, "defines", "src/demo/util.py")

    assert payload["source_hash"] == original.source_hash
    assert payload["stale"] is True
    assert store.load() == original
