"""Whether a method the runtime's dex shows as hollow has AOSP's own trivial body.

The scanner calls a runtime method hollow when its dex body is only ``return-void`` or a constant
return (``scanner._is_hollow_method``). AOSP writes many methods that way: ``InputStream.close()`` is
empty, ``Drawable.getIntrinsicWidth()`` returns -1, ``WindowInsets.Type.ime()`` returns a
compile-time constant, and a base class's no-op is overridden where it matters. A call that reaches
one behaves as on Android.

``BodyShapes`` reads the method in the source the provider is built from (AOSP's, or Westlake's own
copy of the class where Westlake ships one) and answers, per method:

- ``aosp-trivial``: AOSP's body is empty or returns a literal or a named constant (statements under
  a constant debug flag aside, which javac drops), and Westlake's copy, if it ships one, returns the
  same: the runtime's body is AOSP's;
- ``hollowed``: AOSP's body does more (a call, a field read, a throw, several statements), or
  Westlake's copy returns something else: the runtime's body is not AOSP's;
- ``unknown``: no source file, class or single matching declaration was found, or a launcher patch
  rewrites the file.

The upstream jars (OpenJDK, ICU4J, Bouncy Castle, ...) are compiled from their sources unchanged, so
their constant bodies are their own; Westlake's adapter jars are where placeholders are written, so a
constant body there is hollow (``by_artifact``, as ``nativeupcall`` decides).
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .nativeupcall import UPSTREAM_JARS, _westlake_owned

SKIP_TOPS = ("chromium", "oh", "bionic", "boringssl", "build-", "r8")
# The source trees the platform's boot classpath is built from; a library tree (protobuf, guava...)
# holding a class does not put it on a device.
PLATFORM_SOURCES = ("/frameworks-base/", "/libcore/", "/modules-", "/icu/", "/apache-xml/", "/conscrypt/",
                    "/bouncycastle/", "/okhttp/", "/frameworks-opt-", "/providers-mediaprovider/",
                    "/services-telecomm/", "/platform-compat/")
SKIP_DIRS = {".git", "tests", "test", "testing"}
PRIMITIVES = {"V": "void", "Z": "boolean", "B": "byte", "C": "char", "S": "short", "I": "int", "J": "long",
              "F": "float", "D": "double"}

_LEXEMES = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'', re.S)
_LITERAL = re.compile(r"\x01(\d+)\x01")
_BRACES = re.compile(r"[{}]")
_ENDS = re.compile(r"[;{]")
# An if whose condition opens with a constant (DEBUG, !LOCAL_LOGV, false, Build.VERSION.SDK_INT >= 21):
# javac drops what a false constant guards, and d8 folds SDK_INT checks against its minimum API.
_FLAG_IF = re.compile(r"\bif\s*\(\s*!?\s*(?:true\b|false\b|(?:[\w$]+\.)*(?:[A-Z][A-Z0-9_]*|SDK_INT)\b)")
_FIELD = re.compile(r"^\s*((?:\b(?:public|protected|private|static|final|volatile|transient)\b\s*)*)"
                    r"[\w$.<>\[\],?\s]+?\s([\w$]+)\s*=\s*(.+)$", re.S)
_CONSTANT_TOKEN = re.compile(
    r"\s+|\x01\d+\x01|true\b|false\b|null\b|NaN\b"
    r"|(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|\d[\d_]*\.?[\d_]*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?)[lLfFdD]?"
    r"|\(\s*(?:int|long|short|byte|char|float|double|boolean)\s*\)"
    r"|(?:[\w$]+\.)*R\.[a-z]+\.[\w$]+\b(?!\s*\()"
    r"|(?:[\w$]+\.)*[A-Z][A-Z0-9_]*\b(?!\s*\()"
    r"|(?:[\w$]+\.)*[\w$]+\.class\b"
    r"|[-+*/%&|^~!<>=?:()]")
_FIELD_DECLARATION = re.compile(r"[\w$.<>\[\],?\s]+?\s([\w$]+)\s*(?:\[\s*\])*\s*$", re.S)
_METHOD_HEADER = re.compile(r"([A-Za-z_$][\w$]*)\s*\(((?:[^()]|\([^()]*\))*)\)\s*(?:throws\s+[\w$.,\s<>]+)?\s*$", re.S)
_CLASS_HEADER = re.compile(r"\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)")
_ANNOTATION = re.compile(r"@(?!interface\b)[\w$.]+\s*")


def _strip(text: str) -> tuple[str, list[str]]:
    """The text without comments, each string or char literal replaced by a placeholder."""
    literals: list[str] = []

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.startswith("/"):
            return " "
        literals.append(token)
        return f"\x01{len(literals) - 1}\x01"

    return _LEXEMES.sub(replace, text), literals


def _brace_pairs(text: str) -> dict[int, int]:
    pairs, stack = {}, []
    for match in _BRACES.finditer(text):
        if match.group() == "{":
            stack.append(match.start())
        elif stack:
            pairs[stack.pop()] = match.start()
    return pairs


def _without_annotations(header: str) -> str:
    """The header without its annotations and their arguments (which may hold '=', '{' and calls)."""
    out, i, n = [], 0, len(header)
    while i < n:
        annotation = _ANNOTATION.match(header, i)
        if not annotation:
            out.append(header[i])
            i += 1
            continue
        i = annotation.end()
        if i < n and header[i] == "(":
            depth = 0
            while i < n:
                depth += (header[i] == "(") - (header[i] == ")")
                i += 1
                if depth == 0:
                    break
    return "".join(out)


def _type_params(text: str) -> set[str]:
    """The names a leading <...> declares: <K, V extends Comparable<V>> gives {K, V}."""
    if not text.startswith("<"):
        return set()
    depth, current, names = 0, "", set()
    for c in text:
        depth += (c == "<") - (c == ">")
        if (c == "," and depth == 1) or depth == 0:
            found = re.match(r"\s*([A-Za-z_$][\w$]*)", current.lstrip("<"))
            if found:
                names.add(found.group(1))
            current = ""
            if depth == 0:
                return names
        else:
            current += c
    return names


def members(text: str, pairs: dict[int, int], start: int, end: int) -> list[dict[str, Any]]:
    """The declarations at the top level of text[start:end], a class body: methods and classes."""
    found: list[dict[str, Any]] = []
    head = pos = start
    while True:
        match = _ENDS.search(text, pos, end)
        if not match:
            return found
        at = match.start()
        raw = text[head:at]
        if match.group() == "{" and raw.count("(") > raw.count(")"):
            pos = pairs.get(at, end) + 1  # an annotation's array argument, or a call's lambda
            continue
        header = _without_annotations(raw)
        initializer = "=" in header.split("(")[0]
        if match.group() == ";":
            method = _METHOD_HEADER.search(header)
            field = _FIELD.match(header) if initializer else None
            if method and not initializer:
                found.append({"kind": "method", "name": method.group(1), "params": method.group(2), "body": None})
            elif field:
                found.append({"kind": "field", "name": field.group(2), "init": field.group(3).strip(),
                              "final": "final" in field.group(1).split()})
            elif not initializer and _FIELD_DECLARATION.match(header) and not header.strip().startswith(
                    ("import ", "package ", "return ", "throw ")):
                found.append({"kind": "field", "name": _FIELD_DECLARATION.match(header).group(1), "init": None,
                              "final": "final" in header.split()})
            head = pos = at + 1
            continue
        close = pairs.get(at, end)
        if initializer:
            pos = close + 1  # a field's initializer: an anonymous class or an array; its ';' ends it
            continue
        method = _METHOD_HEADER.search(header)
        declared = _CLASS_HEADER.search(header)
        if declared and (not method or method.group(1) == declared.group(1)):
            found.append({"kind": "class", "name": declared.group(1), "body": (at + 1, close),
                          "interface": declared.group(0).startswith("interface"),
                          "type_params": _type_params(header[declared.end():].lstrip())})
        elif method:
            ahead = re.search(r"(?:^|\s)<", header[:method.start(1)])
            found.append({"kind": "method", "name": method.group(1), "params": method.group(2),
                          "body": (at + 1, close),
                          "type_params": _type_params(header[ahead.end() - 1:]) if ahead else set()})
        head = pos = close + 1


def descriptor_params(signature: str) -> list[tuple[str, int]]:
    inner = signature[1:signature.index(")")]
    params, i, dims = [], 0, 0
    while i < len(inner):
        c = inner[i]
        if c == "[":
            dims += 1
            i += 1
            continue
        if c == "L":
            j = inner.index(";", i)
            name = re.split(r"[/$]", inner[i + 1:j])[-1]
            i = j + 1
        else:
            name = PRIMITIVES[c]
            i += 1
        params.append((name, dims))
        dims = 0
    return params


def source_params(params: str) -> list[tuple[str, int]] | None:
    params = re.sub(r"@[\w$.]+(?:\s*\((?:[^()]|\([^()]*\))*\))?", " ", params)
    parts, depth, current = [], 0, ""
    for c in params:
        depth += (c == "<") - (c == ">")
        if c == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += c
    if current.strip():
        parts.append(current)
    out = []
    for part in parts:
        part = re.sub(r"\bfinal\b", " ", part).replace("...", "[] ").strip()
        part = re.sub(r"<.*>", "", part, flags=re.S)
        found = re.match(r"(.+?)\s*([\w$]+)\s*((?:\[\s*\])*)$", part, re.S)
        if not found or not found.group(1).replace("[", "").replace("]", "").split():
            return None
        type_ = found.group(1)
        dims = type_.count("[") + found.group(3).count("[")
        out.append((type_.replace("[", " ").replace("]", " ").split()[-1].split(".")[-1], dims))
    return out


def params_match(source: list[tuple[str, int]] | None, descriptor: list[tuple[str, int]],
                 type_variables: set[str] = frozenset()) -> bool:
    if source is None or len(source) != len(descriptor):
        return False
    for (name, dims), (want, want_dims) in zip(source, descriptor):
        type_variable = name in type_variables or re.fullmatch(r"[A-Z][A-Z0-9]?", name) is not None
        if type_variable:
            if want in PRIMITIVES.values() and want_dims == dims:
                return False
            if dims > want_dims:
                return False
        elif name != want or dims != want_dims:
            return False
    return True


def _constant(expression: str) -> bool:
    pos = 0
    while pos < len(expression):
        found = _CONSTANT_TOKEN.match(expression, pos)
        if not found or found.end() == pos:
            return False
        pos = found.end()
    return True


def _drop_flag_guards(body: str) -> tuple[str, bool]:
    """The body without the statements a constant-led if guards, and whether it had any. An if with
    an else is left in place: which branch survives depends on the constant's value."""
    out, pos, guarded = [], 0, False
    while True:
        found = _FLAG_IF.search(body, pos)
        if not found:
            out.append(body[pos:])
            return "".join(out), guarded
        guarded = True
        i, depth = body.index("(", found.start()), 0
        while i < len(body):
            depth += (body[i] == "(") - (body[i] == ")")
            i += 1
            if depth == 0:
                break
        rest = body[i:].lstrip()
        statement_start = len(body) - len(rest)
        if rest.startswith("{"):
            depth, j = 0, statement_start
            while j < len(body):
                depth += (body[j] == "{") - (body[j] == "}")
                j += 1
                if depth == 0:
                    break
        else:
            depth, j = 0, statement_start
            while j < len(body) and not (body[j] == ";" and depth == 0):
                depth += (body[j] in "({") - (body[j] in ")}")
                j += 1
            j += 1
        if re.match(r"\s*else\b", body[j:]):
            out.append(body[pos:j])
        else:
            out.append(body[pos:found.start()] + " ")
        pos = j


def body_shape(body: str, literals: list[str], constants: dict[str, str] | None = None) -> tuple[str, str]:
    """What a source body compiles to, as far as it can tell:

    - ('trivial', what it returns): empty, or a constant return, once statements under a constant
      condition are set aside;
    - ('folds', ''): it does more, but under a constant condition (a guard, an early return), so
      the compiled body may still be trivial;
    - ('work', ''): it does more, unconditionally.

    `constants` maps the class's static final fields to their initializers, so a return of one is a
    constant return.
    """
    dropped, guarded = _drop_flag_guards(body)
    text = re.sub(r"\s+", " ", re.sub(r"\bassert\b[^;]*;", " ", dropped))  # d8 compiles assertions out
    text = re.sub(r"(?:^|(?<=[;{}]))\s*;", "", text).strip()  # empty statements
    if text in {"", "return;"}:
        return "trivial", ""
    found = re.fullmatch(r"return (.+?) ?;", text)
    if found:
        expression = found.group(1).strip()
        if constants and expression in constants and _constant(constants[expression]):
            expression = constants[expression]
        if _constant(expression):
            value = _LITERAL.sub(lambda m: literals[int(m.group(1))], expression)
            return "trivial", re.sub(r"\s+", "", value)
    return ("folds", "") if guarded else ("work", "")


def _index(root: Path, skip_tops: tuple[str, ...] = ()) -> dict[str, list[str]]:
    index: dict[str, list[str]] = defaultdict(list)
    if not root.is_dir():
        return index
    for top in sorted(os.listdir(root)):
        if (skip_tops and top.startswith(skip_tops)) or not (root / top).is_dir():
            continue
        for dirpath, dirs, files in os.walk(root / top):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in files:
                if name.endswith((".java", ".aidl")):
                    index[name].append(os.path.join(dirpath, name))
    return index


class BodyShapes:
    """Classifies hollow runtime methods against the source the provider is built from."""

    def __init__(self, aosp_root: Path | None, westlake_root: Path | None = None,
                 patched: list[str] | None = None, parents: Any = None) -> None:
        self.aosp_root = aosp_root
        self.parents = parents
        self.westlake_root = westlake_root
        self.patched = tuple("/" + p.lstrip("/") for p in patched or [])
        self._indexes: dict[str, dict[str, list[str]]] = {}
        self._files: dict[str, tuple[str, list[str], dict[int, int]]] = {}
        self._members: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
        self._cache: dict[tuple[str, str, str], str] = {}

    def _index_of(self, which: str) -> dict[str, list[str]]:
        if which not in self._indexes:
            if which == "aosp":
                self._indexes[which] = _index(self.aosp_root, SKIP_TOPS) if self.aosp_root else {}
            else:
                self._indexes[which] = _index(self.westlake_root / "framework") if self.westlake_root else {}
        return self._indexes[which]

    def _members_of(self, path: str, start: int | None = None, end: int | None = None) -> list[dict[str, Any]]:
        if path not in self._files:
            text, literals = _strip(Path(path).read_text(encoding="utf-8", errors="replace"))
            self._files[path] = (text, literals, _brace_pairs(text))
        text, _, pairs = self._files[path]
        key = (path, start or 0, len(text) if end is None else end)
        if key not in self._members:
            self._members[key] = members(text, pairs, key[1], key[2])
        return self._members[key]

    def declarations(self, which: str, owner: str, name: str,
                     signature: str) -> tuple[list[str], list[tuple[str, str]]] | None:
        """The files holding the class, and the shapes of its declarations of the method with this
        descriptor; None when no file declares the class."""
        outer, *nested = owner.strip("L;").split("$")
        if any(part[:1].isdigit() for part in nested):
            return None  # an anonymous or local class
        simple = outer.rsplit("/", 1)[-1]
        files = [p for p in self._index_of(which).get(simple + ".java", []) if p.endswith("/" + outer + ".java")]
        want = descriptor_params(signature)
        shapes: list[tuple[str, str]] = []
        found_class = False
        for path in files:
            span: tuple[int, int] | None = None
            type_variables: set[str] = set()
            for class_name in [simple, *nested]:
                inner = [m for m in self._members_of(path, *(span or (None, None)))
                         if m["kind"] == "class" and m["name"] == class_name]
                if not inner:
                    span = None
                    break
                span = inner[0]["body"]
                type_variables |= inner[0]["type_params"]
            if span is None:
                continue
            found_class = True
            text, literals, _ = self._files[path]
            body_members = self._members_of(path, *span)
            # A final field with a constant initializer is a constant variable: javac inlines it.
            constants = {m["name"]: m["init"] for m in body_members
                         if m["kind"] == "field" and (m["final"] or inner[0]["interface"])}
            for member in body_members:
                if (member["kind"] == "method" and member["name"] == name and member["body"] is not None
                        and params_match(source_params(member["params"]), want,
                                         type_variables | member["type_params"])):
                    shapes.append(body_shape(text[member["body"][0]:member["body"][1]], literals, constants))
        return (files, shapes) if found_class else None

    def shape(self, owner: str, name: str, signature: str) -> str:
        key = (owner, name, signature)
        if key not in self._cache:
            self._cache[key] = self._shape(owner, name, signature)
        return self._cache[key]

    def _shape(self, owner: str, name: str, signature: str) -> str:
        aosp = self.declarations("aosp", owner, name, signature)
        if aosp is None:
            return "unknown"
        files, shapes = aosp
        if self.patched and any(path.endswith(self.patched) for path in files):
            return "unknown"
        if len(set(shapes)) != 1 or shapes[0][0] == "folds":
            return "unknown"
        aosp_shape = shapes[0]
        overlay = self.declarations("westlake", owner, name, signature) if self.westlake_root else None
        if overlay is not None:
            overlay_shapes = set(overlay[1])
            if len(overlay_shapes) != 1:
                return "unknown"
            westlake_shape = overlay_shapes.pop()
            if westlake_shape[0] != "trivial":
                return "unknown"  # the dex says constant: the copy's work may sit behind a flag
            return "aosp-trivial" if westlake_shape == aosp_shape else "hollowed"
        return "aosp-trivial" if aosp_shape[0] == "trivial" else "hollowed"

    def declares(self, owner: str, name: str, signature: str | None, field: bool = False) -> bool | None:
        """Whether Android's sources declare the member on the class or on a class or interface it
        inherits from (`parents`: owner -> its superclass and interfaces, from the runtime index):
        False for one Android does not have (an API a later release added, an overload it never
        had), None when a class on the way has no source to read."""
        if self.aosp_root is None:
            return None
        seen: set[str] = set()
        queue = [owner]
        while queue and len(seen) < 64:
            current = queue.pop(0)
            if current in seen or current == "Ljava/lang/Object;":
                continue
            seen.add(current)
            found = self._declares_here(current, name, signature, field)
            if found:
                return True
            if found is None:
                return None
            queue += [parent for parent in (self.parents(current) if self.parents else []) if parent]
        return False

    def _declares_here(self, owner: str, name: str, signature: str | None, field: bool) -> bool | None:
        outer, *nested = owner.strip("L;").split("$")
        if any(part[:1].isdigit() for part in nested):
            return None
        simple = outer.rsplit("/", 1)[-1]
        files = [p for p in self._index_of("aosp").get(simple + ".java", [])
                 if p.endswith("/" + outer + ".java") and any(r in p for r in PLATFORM_SOURCES)]
        want = descriptor_params(signature) if signature and not field else None
        declared_class = False
        for path in files:
            span: tuple[int, int] | None = None
            type_variables: set[str] = set()
            for class_name in [simple, *nested]:
                inner = [m for m in self._members_of(path, *(span or (None, None)))
                         if m["kind"] == "class" and m["name"] == class_name]
                if not inner:
                    span = None
                    break
                span = inner[0]["body"]
                type_variables |= inner[0]["type_params"]
            if span is None:
                continue
            declared_class = True
            target = ([simple, *nested][-1] if name == "<init>" else name)
            for member in self._members_of(path, *span):
                if field:
                    if member["kind"] == "field" and member["name"] == name:
                        return True
                    continue
                if member["kind"] != "method" or member["name"] != target:
                    continue
                if want is None or params_match(source_params(member["params"]), want,
                                                type_variables | member.get("type_params", set())):
                    return True
        return False if declared_class else None

    def on_android(self, owner: str) -> bool | None:
        """Whether the platform's sources declare the class: False for one Android does not ship
        either (java.lang.Module, a class a release removed), None without sources."""
        if self.aosp_root is None:
            return None
        outer, *nested = owner.strip("L;").split("$")
        if any(part[:1].isdigit() for part in nested):
            return None  # an anonymous class: javac numbers them, a source does not name them
        simple = outer.rsplit("/", 1)[-1]
        index = self._index_of("aosp")
        if any(p.endswith("/" + outer + ".aidl") and any(r in p for r in PLATFORM_SOURCES)
               for p in index.get(simple + ".aidl", [])):
            return True
        for path in index.get(simple + ".java", []):
            if not path.endswith("/" + outer + ".java") or not any(r in path for r in PLATFORM_SOURCES):
                continue
            span: tuple[int, int] | None = None
            for class_name in [simple, *nested]:
                inner = [m for m in self._members_of(path, *(span or (None, None)))
                         if m["kind"] == "class" and m["name"] == class_name]
                if not inner:
                    span = None
                    break
                span = inner[0]["body"]
            if span is not None:
                return True
        return False

    def by_artifact(self, artifact: str | None, owner: str, name: str, signature: str) -> str:
        """The shape, decided first by the jar the runtime's class comes from."""
        if artifact in UPSTREAM_JARS:
            return "aosp-trivial"
        if _westlake_owned(artifact):
            return "hollowed"
        return self.shape(owner, name, signature)


def patched_files(manifest_root: Path | None) -> list[str]:
    """The frameworks-base files a launcher patch rewrites, as paths under the AOSP imports."""
    if manifest_root is None:
        return []
    out = []
    for patch in sorted((manifest_root / "patches").glob("**/frameworks-base*.patch")):
        for line in patch.read_text(errors="replace").splitlines():
            if line.startswith("+++ b/"):
                out.append("frameworks-base/" + line[6:].split("\t")[0].strip())
    return out
