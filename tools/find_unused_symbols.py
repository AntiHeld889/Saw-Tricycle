#!/usr/bin/env python3
"""Report module-level names that are defined but never referenced."""
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence


@dataclass(frozen=True)
class Definition:
    name: str
    filename: Path
    lineno: int
    kind: str


IGNORED_NAMES = {"__all__"}


class _ReferenceCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()

    # We only care about load contexts; store contexts correspond to definitions
    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802 - ast API
        if isinstance(node.ctx, ast.Load):
            self.names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802 - ast API
        # Attributes such as module.constants should still mark the attribute name as used.
        self.names.add(node.attr)
        self.generic_visit(node)


def _iter_module_level_defs(tree: ast.AST, filename: Path) -> Iterator[Definition]:
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield Definition(node.name, filename, node.lineno, "function")
        elif isinstance(node, ast.ClassDef):
            yield Definition(node.name, filename, node.lineno, "class")
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets: Iterable[ast.expr]
            if isinstance(node, ast.Assign):
                targets = node.targets
            else:  # AnnAssign
                targets = (node.target,)
            for target in targets:
                if isinstance(target, ast.Name):
                    yield Definition(target.id, filename, target.lineno, "variable")
                elif isinstance(target, ast.Tuple):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            yield Definition(elt.id, filename, elt.lineno, "variable")


def _analyze_file(path: Path) -> tuple[list[Definition], set[str]]:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"{path}: konnte Datei nicht lesen ({exc})") from exc
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise SystemExit(f"{path}: Syntaxfehler – {exc}") from exc

    definitions = list(_iter_module_level_defs(tree, path))
    collector = _ReferenceCollector()
    collector.visit(tree)
    return definitions, collector.names


def _gather_files(paths: Sequence[Path]) -> list[Path]:
    collected: list[Path] = []
    for path in paths:
        if path.is_dir():
            for candidate in sorted(path.rglob("*.py")):
                # Skip hidden directories such as .venv
                if any(part.startswith(".") for part in candidate.parts):
                    continue
                collected.append(candidate)
        else:
            collected.append(path)
    return collected


def find_unused_symbols(paths: Sequence[Path]) -> list[Definition]:
    files = _gather_files(paths)

    definitions: list[Definition] = []
    used_names: set[str] = set()
    for file_path in files:
        defs, used = _analyze_file(file_path)
        definitions.extend(defs)
        used_names.update(used)

    unused: list[Definition] = []
    for definition in definitions:
        if definition.name in IGNORED_NAMES:
            continue
        if definition.name.startswith("__") and definition.name.endswith("__"):
            continue
        if definition.name not in used_names:
            unused.append(definition)
    return unused


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Analysiert Python-Dateien und meldet Modul-Symbole, die nirgendwo "
            "im Code referenziert werden."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path(".")],
        help="Dateien oder Verzeichnisse, die durchsucht werden sollen.",
    )
    args = parser.parse_args()

    unused = find_unused_symbols(args.paths)
    if not unused:
        print("Keine ungenutzten Modul-Symbole gefunden.")
        return 0

    print("Folgende Modul-Symbole scheinen ungenutzt zu sein:")
    for definition in unused:
        rel_path = definition.filename.resolve().relative_to(Path.cwd())
        print(
            f"- {rel_path}:{definition.lineno} – {definition.kind} '{definition.name}'"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
