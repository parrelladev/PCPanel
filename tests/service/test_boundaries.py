from __future__ import annotations

import ast
from pathlib import Path


SERVICE_ROOT = Path("app/service")
FORBIDDEN_PREFIXES = (
    "fastapi",
    "uvicorn",
    "app.api",
    "app.auth",
    "app.actions",
    "app.persistence",
    "sqlite3",
)


def test_service_modules_do_not_import_network_auth_actions_or_persistence() -> None:
    imports: list[str] = []
    for path in SERVICE_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                module = node.module.lstrip(".")
                imports.append(module)

    assert not any(
        imported == forbidden or imported.startswith(f"{forbidden}.")
        for imported in imports
        for forbidden in FORBIDDEN_PREFIXES
    )


def test_service_source_contains_no_http_auth_action_or_sqlite_runtime() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in SERVICE_ROOT.glob("*.py")
    )
    for forbidden in ("fastapi", "bearer", "pairing", "actionservice", "sqlite"):
        assert forbidden not in source
