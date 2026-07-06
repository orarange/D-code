"""
code_map.py
===========
コードベース理解のための「依存マップ / 呼び出し地図」生成器。

初見のコードで一番ありがたいのは、細かい処理フローよりも
「どのファイルがどのファイルを使っているか」という全体の地図。
このモジュールはワークスペースを走査し、ファイル間の import 依存を
グラフ（ノード=ファイル、エッジ=依存）として抽出する。

- Python: 標準ライブラリ ast で import / from-import を正確に解決
- JS/TS : import ... from '...' / require('...') を抽出し相対パス解決

外部ライブラリ（npm パッケージや標準ライブラリ）は地図を汚すので除外し、
リポジトリ内部のファイル同士の依存だけを残す。
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# 走査対象の拡張子 → 言語
LANG_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

# 地図に含めないディレクトリ
DEFAULT_IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", "dist", "build",
    ".venv", "venv", ".mypy_cache", ".pytest_cache", "target",
    ".next", ".idea", ".vscode",
}

# JS/TS の相対 import を解決するときに試す拡張子
_JS_RESOLVE_EXTS = ["", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]

# import 'x' / import ... from 'x' / require('x')
_JS_IMPORT_RE = re.compile(
    r"""(?:from\s+|import\s+|require\(\s*)['"]([^'"]+)['"]"""
)


@dataclass
class Node:
    """地図上の 1 ファイル。"""
    id: str                       # ルートからの相対パス（例: engine/main_agent.py）
    name: str                     # ファイル名（例: main_agent.py）
    language: str
    lines: int = 0
    size_bytes: int = 0
    symbols: list[str] = field(default_factory=list)  # 定義された関数/クラス名
    fan_in: int = 0               # このファイルを import しているファイル数
    fan_out: int = 0             # このファイルが import しているファイル数
    role: str = "module"         # entry / hub / leaf / module / isolated

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "language": self.language,
            "lines": self.lines,
            "sizeBytes": self.size_bytes,
            "symbols": self.symbols,
            "fanIn": self.fan_in,
            "fanOut": self.fan_out,
            "role": self.role,
        }


@dataclass
class Edge:
    """依存の矢印。source が target を import している。"""
    source: str
    target: str
    kind: str = "import"

    def to_dict(self) -> dict:
        return {"source": self.source, "target": self.target, "kind": self.kind}


@dataclass
class CodeMap:
    """依存マップ全体。"""
    root: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "stats": self.stats(),
        }

    def stats(self) -> dict:
        return {
            "fileCount": len(self.nodes),
            "edgeCount": len(self.edges),
            "totalLines": sum(n.lines for n in self.nodes),
            "entryPoints": [n.id for n in self.nodes if n.role == "entry"],
            "hubs": [n.id for n in self.nodes if n.role == "hub"],
            "isolated": [n.id for n in self.nodes if n.role == "isolated"],
        }


# --------------------------------------------------------------------------- #
# 走査
# --------------------------------------------------------------------------- #

def _iter_source_files(root: Path, ignore_dirs: set[str]) -> list[Path]:
    """対象拡張子のファイルを再帰的に集める。"""
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # ignore_dirs を走査対象から除外（in-place で os.walk を刈り込む）
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith(".")]
        for fn in filenames:
            if Path(fn).suffix in LANG_BY_EXT:
                files.append(Path(dirpath) / fn)
    return files


# --------------------------------------------------------------------------- #
# Python 依存解決
# --------------------------------------------------------------------------- #

def _module_dotted(rel_path: str) -> str:
    """相対パス engine/main_agent.py → ドット表記 engine.main_agent。

    __init__.py はパッケージ自体を表すので末尾を落とす。
    """
    parts = rel_path[:-3].split("/")  # 末尾 .py を除去
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _build_py_index(py_rel_paths: list[str]) -> dict[str, str]:
    """ドット表記モジュール名 → 相対パス の索引を作る。"""
    index: dict[str, str] = {}
    for rel in py_rel_paths:
        dotted = _module_dotted(rel)
        if dotted:
            index[dotted] = rel
    return index


def _resolve_dotted(dotted: str, index: dict[str, str]) -> Optional[str]:
    """ドット表記を内部ファイルへ解決。見つからなければ末尾を削って再試行。

    例: `import a.b.c` で c が属性の場合でも a.b が解決できればそれを返す。
    """
    parts = dotted.split(".")
    while parts:
        cand = ".".join(parts)
        if cand in index:
            return index[cand]
        parts.pop()
    return None


def _py_dependencies(
    rel_path: str, source: str, index: dict[str, str]
) -> tuple[set[str], list[str]]:
    """Python ファイルの内部依存（相対パス集合）と定義シンボルを返す。"""
    deps: set[str] = set()
    symbols: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return deps, symbols

    # このファイルが属するパッケージ（相対 import の基点）
    pkg_parts = _module_dotted(rel_path).split(".")
    # モジュール名自体を落とし、パッケージ部分だけ残す
    # 例: engine.main_agent → パッケージは engine
    if not rel_path.endswith("__init__.py"):
        pkg_parts = pkg_parts[:-1]

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                target = _resolve_dotted(alias.name, index)
                if target and target != rel_path:
                    deps.add(target)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # 相対 import: level-1 個だけパッケージを遡る
                base = pkg_parts[: len(pkg_parts) - (node.level - 1)] if node.level > 1 else list(pkg_parts)
                mod_parts = base + (node.module.split(".") if node.module else [])
                dotted = ".".join(p for p in mod_parts if p)
            else:
                dotted = node.module or ""
            if dotted:
                target = _resolve_dotted(dotted, index)
                if target and target != rel_path:
                    deps.add(target)
    # トップレベルの def/class のみに絞る（walk は入れ子も拾うため）
    top_symbols = [
        n.name
        for n in ast.iter_child_nodes(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    return deps, top_symbols


# --------------------------------------------------------------------------- #
# JS / TS 依存解決
# --------------------------------------------------------------------------- #

def _resolve_js_relative(spec: str, from_file: Path, root: Path, known: set[str]) -> Optional[str]:
    """'./x' 形式の相対 import を内部ファイルの相対パスへ解決。"""
    base = (from_file.parent / spec).resolve()
    candidates = [base.with_name(base.name + ext) for ext in _JS_RESOLVE_EXTS]
    candidates += [base / f"index{ext}" for ext in _JS_RESOLVE_EXTS if ext]
    for cand in candidates:
        try:
            rel = cand.relative_to(root).as_posix()
        except ValueError:
            continue
        if rel in known:
            return rel
    return None


def _js_dependencies(
    rel_path: str, source: str, from_file: Path, root: Path, known: set[str]
) -> set[str]:
    """JS/TS ファイルの内部依存（相対パス集合）を返す。"""
    deps: set[str] = set()
    for m in _JS_IMPORT_RE.finditer(source):
        spec = m.group(1)
        if not spec.startswith("."):
            continue  # npm パッケージ等は内部地図から除外
        target = _resolve_js_relative(spec, from_file, root, known)
        if target and target != rel_path:
            deps.add(target)
    return deps


# --------------------------------------------------------------------------- #
# メイン
# --------------------------------------------------------------------------- #

def _classify_role(node: Node) -> str:
    """fan-in / fan-out からファイルの役割を分類する。"""
    if node.fan_in == 0 and node.fan_out == 0:
        return "isolated"
    if node.fan_in == 0 and node.fan_out > 0:
        return "entry"      # どこからも呼ばれず、他を呼ぶ → 入口っぽい
    if node.fan_in >= 4:
        return "hub"        # あちこちから呼ばれる → 中核
    if node.fan_out == 0:
        return "leaf"       # 何も呼ばない末端（部品）
    return "module"


def build_code_map(
    root: str | os.PathLike,
    ignore_dirs: Optional[set[str]] = None,
) -> CodeMap:
    """ワークスペースを走査して依存マップを構築する。"""
    root_path = Path(root).resolve()
    ignore = DEFAULT_IGNORE_DIRS | (ignore_dirs or set())

    files = _iter_source_files(root_path, ignore)
    rel_paths = [f.relative_to(root_path).as_posix() for f in files]
    known = set(rel_paths)
    py_rels = [r for r in rel_paths if r.endswith(".py")]
    py_index = _build_py_index(py_rels)

    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    seen_edges: set[tuple[str, str]] = set()

    for f, rel in zip(files, rel_paths):
        try:
            source = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            source = ""

        lang = LANG_BY_EXT[f.suffix]
        node = Node(
            id=rel,
            name=f.name,
            language=lang,
            lines=source.count("\n") + 1 if source else 0,
            size_bytes=len(source.encode("utf-8")),
        )

        if lang == "python":
            deps, symbols = _py_dependencies(rel, source, py_index)
            node.symbols = symbols
        else:
            deps = _js_dependencies(rel, source, f, root_path, known)

        nodes[rel] = node
        for target in deps:
            key = (rel, target)
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append(Edge(source=rel, target=target))

    # fan-in / fan-out 集計
    for e in edges:
        if e.source in nodes:
            nodes[e.source].fan_out += 1
        if e.target in nodes:
            nodes[e.target].fan_in += 1
    for node in nodes.values():
        node.role = _classify_role(node)

    # 役割 → id 順で安定ソート（ハブや入口を上に）
    order = {"entry": 0, "hub": 1, "module": 2, "leaf": 3, "isolated": 4}
    ordered = sorted(nodes.values(), key=lambda n: (order.get(n.role, 9), n.id))

    return CodeMap(root=str(root_path), nodes=ordered, edges=edges)


def _print_summary(cmap: CodeMap) -> None:
    """人間向けにマップの要約をターミナルへ出力する。"""
    s = cmap.stats()
    print(f"\n📍 Code Map: {cmap.root}")
    print(f"   {s['fileCount']} files, {s['edgeCount']} dependencies, {s['totalLines']} lines\n")

    def _row(n: Node) -> str:
        return f"   {n.role:8} in:{n.fan_in:<3} out:{n.fan_out:<3} {n.id}"

    if s["entryPoints"]:
        print("🚪 Entry points (呼ばれず・他を呼ぶ):")
        for n in cmap.nodes:
            if n.role == "entry":
                print(_row(n))
        print()
    if s["hubs"]:
        print("🎯 Hubs (あちこちから呼ばれる中核):")
        for n in cmap.nodes:
            if n.role == "hub":
                print(_row(n))
        print()
    if s["isolated"]:
        print(f"🧩 Isolated ({len(s['isolated'])} 個・依存関係なし): "
              + ", ".join(s["isolated"][:8])
              + (" ..." if len(s["isolated"]) > 8 else ""))


def main(argv: Optional[list[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    target = argv[0] if argv else "."
    as_json = "--json" in argv

    cmap = build_code_map(target)
    if as_json:
        print(json.dumps(cmap.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_summary(cmap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
