"""Stage tracer: runs user code and records every visible step.

The tracer is library-agnostic. It walks the user's statements and, for method
chains such as

    df[df.age > 30].groupby("city")["salary"].mean()

evaluates each link of the chain exactly once, recording the intermediate
values. Links whose value is not displayable (a GroupBy, an accessor such as
`.str`, an indexer such as `.loc`) are merged into the next displayable link,
so the stages above are: filter -> groupby/select/mean.

Statements that are not a simple `name = <expression>` (column assignment,
`inplace=True`, loops...) are executed normally and recorded as *mutation*
stages by diffing every DataFrame/Series variable before and after.

Each stage remembers which earlier stage (or input) produced its starting
value, through *tokens*, so frame generators can keep row identity across
statements.
"""
from __future__ import annotations

import ast
import contextlib
import io
import operator
import sys
import traceback
import types
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

USER_FILE = "<your code>"

Token = tuple[str, Any]  # ("input", name) | ("stage", index)


class UserCodeError(Exception):
    def __init__(self, etype: str, message: str, line: int | None):
        super().__init__(message)
        self.etype = etype
        self.message = message
        self.line = line

    def as_dict(self) -> dict:
        return {"type": self.etype, "message": self.message, "line": self.line}


@dataclass
class Step:
    kind: str  # call | attr | getitem | func | binop | mutation
    name: str  # method / attribute / function / operator name
    node: ast.AST
    value: Any = None
    args: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)
    key: Any = None
    receiver: Any = None


@dataclass
class Stage:
    index: int
    kind: str  # chain | mutation
    before: Any  # snapshot of the displayable value the stage starts from (or None)
    before_token: Token | None
    after: Any  # snapshot of the value the stage produces
    steps: list[Step]
    code: dict | None
    var: str | None
    inputs: list[tuple[Any, Token | None, str]] = field(default_factory=list)  # extra table inputs
    before_name: str | None = None
    refs: set[str] = field(default_factory=set)  # names/strings mentioned by the stage's code

    @property
    def ops(self) -> list[str]:
        return [s.name for s in self.steps]

    @property
    def main(self) -> Step:
        """The step that defines the stage (last call, else last step)."""
        for s in reversed(self.steps):
            if s.kind in ("call", "func", "binop", "mutation"):
                return s
        return self.steps[-1]


# --------------------------------------------------------------------------- helpers

_SCALARS = (bool, int, float, complex, str, bytes, np.generic, pd.Timestamp, pd.Timedelta, pd.Period)


def is_table(v: Any) -> bool:
    return isinstance(v, (pd.DataFrame, pd.Series))


def is_scalarish(v: Any) -> bool:
    if v is None or isinstance(v, _SCALARS) or v is pd.NA or v is pd.NaT:
        return True
    if isinstance(v, (np.dtype, pd.api.extensions.ExtensionDtype)):
        return True
    if isinstance(v, (tuple, list)) and len(v) <= 50:
        return all(is_scalarish(x) for x in v)
    return False


def displayable(v: Any) -> bool:
    if is_table(v) or isinstance(v, pd.Index):
        return True
    if isinstance(v, np.ndarray):
        return v.ndim in (1, 2)
    return is_scalarish(v)


def snapshot(v: Any) -> Any:
    if isinstance(v, (pd.DataFrame, pd.Series, pd.Index, np.ndarray)):
        return v.copy()
    if isinstance(v, list):
        return list(v)
    return v


def same_content(a: Any, b: Any) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, pd.DataFrame):
        return (
            a.shape == b.shape
            and a.columns.equals(b.columns)
            and a.index.equals(b.index)
            and list(a.dtypes) == list(b.dtypes)
            and a.equals(b)
        )
    if isinstance(a, pd.Series):
        return a.name == b.name and a.dtype == b.dtype and a.index.equals(b.index) and a.equals(b)
    return False


_BINOPS = {
    ast.Add: ("+", operator.add),
    ast.Sub: ("-", operator.sub),
    ast.Mult: ("*", operator.mul),
    ast.Div: ("/", operator.truediv),
    ast.FloorDiv: ("//", operator.floordiv),
    ast.Mod: ("%", operator.mod),
    ast.Pow: ("**", operator.pow),
    ast.BitAnd: ("&", operator.and_),
    ast.BitOr: ("|", operator.or_),
    ast.BitXor: ("^", operator.xor),
}
_CMPOPS = {
    ast.Gt: (">", operator.gt),
    ast.GtE: (">=", operator.ge),
    ast.Lt: ("<", operator.lt),
    ast.LtE: ("<=", operator.le),
    ast.Eq: ("==", operator.eq),
    ast.NotEq: ("!=", operator.ne),
}


def _refs(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.add(n.value)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, ast.Name):
            out.add(n.id)
    return out


def _step_refs(step: Step) -> set[str]:
    """Names mentioned by this step itself (not by its receiver)."""
    n = step.node
    if step.kind == "call" and isinstance(n, ast.Call):
        out = set()
        for a in n.args:
            out |= _refs(a)
        for k in n.keywords:
            out |= _refs(k.value)
        return out
    if step.kind == "getitem" and isinstance(n, ast.Subscript):
        return _refs(n.slice)
    if step.kind == "attr" and isinstance(n, ast.Attribute):
        return {n.attr}
    return _refs(n)


# --------------------------------------------------------------------------- tracer

class Tracer:
    def __init__(self, code: str, ns: dict[str, Any], input_names: list[str]):
        self.code = code
        self.ns = ns
        self.lines = code.splitlines() or [""]
        self.input_names = input_names
        self.stages: list[Stage] = []
        self._tokens: dict[int, Token] = {}
        self._keep: list[Any] = []  # keep traced objects alive so id() stays unique
        self.stdout = io.StringIO()

    # -- tokens
    def token_of(self, v: Any) -> Token | None:
        return self._tokens.get(id(v))

    def bind(self, v: Any, token: Token) -> None:
        self._tokens[id(v)] = token
        self._keep.append(v)

    # -- code ranges
    def _char_col(self, line: int, byte_col: int) -> int:
        text = self.lines[line - 1] if 0 < line <= len(self.lines) else ""
        return len(text.encode("utf-8")[:byte_col].decode("utf-8", errors="ignore"))

    def range_between(self, start: tuple[int, int], node: ast.AST) -> dict:
        sl, sc = start
        el, ec = node.end_lineno, node.end_col_offset  # type: ignore[attr-defined]
        return {
            "startLine": sl,
            "startCol": self._char_col(sl, sc) + 1,
            "endLine": el,
            "endCol": self._char_col(el, ec) + 1,
        }

    def range_of(self, node: ast.AST) -> dict:
        return self.range_between((node.lineno, node.col_offset), node)  # type: ignore[attr-defined]

    @staticmethod
    def end_of(node: ast.AST) -> tuple[int, int]:
        return (node.end_lineno, node.end_col_offset)  # type: ignore[attr-defined]

    # -- evaluation
    def eval(self, node: ast.AST) -> Any:
        expr = ast.Expression(body=node)
        return eval(compile(expr, USER_FILE, "eval"), self.ns)

    def eval_key(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Slice):
            return slice(
                self.eval(node.lower) if node.lower else None,
                self.eval(node.upper) if node.upper else None,
                self.eval(node.step) if node.step else None,
            )
        if isinstance(node, ast.Tuple) and any(isinstance(e, ast.Slice) for e in node.elts):
            return tuple(self.eval_key(e) for e in node.elts)
        return self.eval(node)

    def eval_args(self, call: ast.Call) -> tuple[list, dict]:
        args: list = []
        for a in call.args:
            if isinstance(a, ast.Starred):
                args.extend(self.eval(a.value))
            else:
                args.append(self.eval(a))
        kwargs: dict = {}
        for k in call.keywords:
            if k.arg is None:
                kwargs.update(self.eval(k.value))
            else:
                kwargs[k.arg] = self.eval(k.value)
        return args, kwargs

    # -- error handling
    def _user_line(self, exc: BaseException, fallback: int | None) -> int | None:
        line = None
        for fr in traceback.extract_tb(exc.__traceback__):
            if fr.filename == USER_FILE:
                line = fr.lineno
        return line or fallback

    def fail(self, exc: BaseException, node: ast.AST | None) -> UserCodeError:
        if isinstance(exc, UserCodeError):
            return exc
        fallback = getattr(node, "lineno", None)
        msg = str(exc) if str(exc) else exc.__class__.__name__
        return UserCodeError(exc.__class__.__name__, msg, self._user_line(exc, fallback))

    # -- main loop
    def run(self) -> None:
        try:
            tree = ast.parse(self.code, filename=USER_FILE)
        except SyntaxError as e:
            raise UserCodeError("SyntaxError", e.msg or "invalid syntax", e.lineno) from None
        for name in self.input_names:
            self.bind(self.ns[name], ("input", name))
        with contextlib.redirect_stdout(self.stdout):
            for stmt in tree.body:
                try:
                    self.statement(stmt)
                except UserCodeError:
                    raise
                except Exception as e:  # noqa: BLE001 - user code may raise anything
                    raise self.fail(e, stmt) from None

    def statement(self, stmt: ast.stmt) -> None:
        if (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
        ):
            name = stmt.targets[0].id
            value = self.chain(stmt.value, var=name)
            self.ns[name] = value
            return
        if isinstance(stmt, ast.Expr) and not self._may_mutate(stmt.value):
            # A bare expression (e.g. `print(df)`): just run it.
            exec(compile(ast.Module(body=[stmt], type_ignores=[]), USER_FILE, "exec"), self.ns)
            return
        self.mutation(stmt)

    @staticmethod
    def _may_mutate(node: ast.AST) -> bool:
        for n in ast.walk(node):
            if isinstance(n, ast.keyword) and n.arg == "inplace":
                return True
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in (
                "insert", "pop", "update", "set_axis", "rename_axis", "__setitem__",
            ):
                return True
        return False

    # -- chains
    def chain(self, node: ast.AST, var: str | None) -> Any:
        spine: list[ast.AST] = []
        n = node
        while True:
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                spine.append(n)
                n = n.func.value
            elif isinstance(n, (ast.Attribute, ast.Subscript)):
                spine.append(n)
                n = n.value
            else:
                break
        root = n
        spine.reverse()

        if isinstance(root, (ast.BinOp, ast.Compare, ast.UnaryOp)):
            value = self.operator(root, var)
        elif isinstance(root, ast.Call):
            value = self.function_call(root, var)
        else:
            try:
                value = self.eval(root)
            except Exception as e:  # noqa: BLE001
                raise self.fail(e, root) from None

        last_disp = value if displayable(value) else None
        last_node: ast.AST | None = root if last_disp is not None else None
        pending: list[Step] = []
        for link_node in spine:
            recv = value
            try:
                if isinstance(link_node, ast.Call):
                    fn = link_node.func
                    assert isinstance(fn, ast.Attribute)
                    args, kwargs = self.eval_args(link_node)
                    value = getattr(recv, fn.attr)(*args, **kwargs)
                    kind = "func" if isinstance(recv, types.ModuleType) else "call"
                    step = Step(kind, fn.attr, link_node, value, args, kwargs, receiver=recv)
                elif isinstance(link_node, ast.Attribute):
                    value = getattr(recv, link_node.attr)
                    step = Step("attr", link_node.attr, link_node, value, receiver=recv)
                else:
                    assert isinstance(link_node, ast.Subscript)
                    key = self.eval_key(link_node.slice)
                    value = recv[key]
                    step = Step("getitem", "getitem", link_node, value, key=key, receiver=recv)
            except Exception as e:  # noqa: BLE001
                raise self.fail(e, link_node) from None
            pending.append(step)
            if displayable(value) and not callable(value):
                start = self.end_of(last_node) if last_node is not None else (
                    link_node.lineno, link_node.col_offset  # type: ignore[attr-defined]
                )
                extra = self._table_args(step)
                before = last_disp
                btoken = None
                bname = ast.unparse(last_node) if last_node is not None else None
                if before is None and len(extra) == 1:
                    # `pd.melt(df, ...)`: the single table argument is what the stage transforms
                    before, btoken, bname = extra[0]
                    extra = []
                self.emit(
                    kind="chain",
                    before=before,
                    after=value,
                    steps=pending,
                    code=self.range_between(start, link_node),
                    var=var,
                    inputs=extra,
                    before_name=bname,
                    before_token=btoken,
                )
                last_disp, last_node, pending = value, link_node, []
        return value

    def _table_args(self, step: Step) -> list[tuple[Any, Token | None, str]]:
        """DataFrame/Series arguments of a call (e.g. the `right` of a merge)."""
        out: list[tuple[Any, Token | None, str]] = []
        if step.kind not in ("call", "func") or not isinstance(step.node, ast.Call):
            return out
        nodes = list(step.node.args)
        values = list(step.args)
        for arg_node, v in zip(nodes, values):
            if is_table(v):
                out.append((snapshot(v), self.token_of(v), ast.unparse(arg_node)))
            elif isinstance(v, (list, tuple)) and v and all(is_table(x) for x in v):
                elts = arg_node.elts if isinstance(arg_node, (ast.List, ast.Tuple)) else []
                for i, x in enumerate(v):
                    label = ast.unparse(elts[i]) if i < len(elts) else f"{ast.unparse(arg_node)}[{i}]"
                    out.append((snapshot(x), self.token_of(x), label))
        for k, v in step.kwargs.items():
            if is_table(v) and k in ("right", "other", "left"):
                out.append((snapshot(v), self.token_of(v), k))
        return out

    def function_call(self, node: ast.Call, var: str | None) -> Any:
        """A call whose callee is not a method of a traced value: `len(df)`, `pd.merge(a, b)`."""
        try:
            func = self.eval(node.func)
            args, kwargs = self.eval_args(node)
            value = func(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            raise self.fail(e, node) from None
        fname = node.func.attr if isinstance(node.func, ast.Attribute) else (
            node.func.id if isinstance(node.func, ast.Name) else "call"
        )
        step = Step("func", fname, node, value, args, kwargs)
        if displayable(value):
            tables = self._table_args(step)
            before, btoken, bname = (tables[0] if tables and len(tables) == 1 else (None, None, None))
            self.emit(
                kind="chain",
                before=before,
                after=value,
                steps=[step],
                code=self.range_of(node),
                var=var,
                inputs=tables if before is None else [],
                before_name=bname,
                before_token=btoken,
            )
        return value

    def operator(self, node: ast.AST, var: str | None) -> Any:
        """Element-wise operators (`df.a * 2`, `df.a > 3`). The first table operand
        is traced as a chain; the operator itself becomes one stage."""
        try:
            if isinstance(node, ast.UnaryOp):
                operand = self.chain(node.operand, var)
                ops = {ast.USub: ("-", operator.neg), ast.UAdd: ("+", operator.pos),
                       ast.Invert: ("~", operator.invert), ast.Not: ("not", operator.not_)}
                sym, fn = ops[type(node.op)]
                value = fn(operand)
                primary, primary_node = operand, node.operand
            else:
                if isinstance(node, ast.BinOp):
                    left_node, right_node = node.left, node.right
                    sym, fn = _BINOPS.get(type(node.op), ("?", None))  # type: ignore[assignment]
                elif isinstance(node, ast.Compare) and len(node.ops) == 1:
                    left_node, right_node = node.left, node.comparators[0]
                    sym, fn = _CMPOPS.get(type(node.ops[0]), ("?", None))  # type: ignore[assignment]
                else:
                    return self.eval(node)
                if fn is None:
                    return self.eval(node)
                left = self.chain(left_node, var)
                if is_table(left):
                    right = self.eval(right_node)
                    primary, primary_node = left, left_node
                else:
                    right = self.chain(right_node, var)
                    primary, primary_node = right, right_node
                value = fn(left, right)
        except UserCodeError:
            raise
        except Exception as e:  # noqa: BLE001
            raise self.fail(e, node) from None
        step = Step("binop", sym, node, value)
        if displayable(value) and is_table(primary):
            self.emit(
                kind="chain",
                before=primary,
                after=value,
                steps=[step],
                code=self.range_of(node),
                var=var,
                before_name=ast.unparse(primary_node),
            )
        return value

    # -- mutations
    def _tables_in_ns(self) -> dict[str, Any]:
        return {
            k: v for k, v in self.ns.items()
            if is_table(v) and not k.startswith("_")
        }

    def mutation(self, stmt: ast.stmt) -> None:
        before = self._tables_in_ns()
        snaps = {k: snapshot(v) for k, v in before.items()}
        ids = {k: id(v) for k, v in before.items()}
        tokens = {k: self.token_of(v) for k, v in before.items()}
        exec(compile(ast.Module(body=[stmt], type_ignores=[]), USER_FILE, "exec"), self.ns)
        for name, v in self._tables_in_ns().items():
            if name in snaps and id(v) == ids[name] and same_content(snaps[name], v):
                continue
            if name in snaps:
                prev, token = snaps[name], tokens[name]
            else:
                prev, token = None, None
            self.emit(
                kind="mutation",
                before=prev,
                after=v,
                steps=[self._mutation_step(stmt, v)],
                code=self.range_of(stmt),
                var=name,
                before_name=name,
                before_token=token,
                live=v,
            )

    def _mutation_step(self, stmt: ast.stmt, value: Any) -> Step:
        def literal(node: ast.AST) -> Any:
            try:
                return ast.literal_eval(node)
            except Exception:  # noqa: BLE001
                return None

        if isinstance(stmt, (ast.Assign, ast.AugAssign)):
            target = stmt.targets[0] if isinstance(stmt, ast.Assign) else stmt.target
            if isinstance(target, ast.Subscript):
                inner = target.value
                if isinstance(inner, ast.Attribute) and inner.attr in ("loc", "iloc", "at", "iat"):
                    return Step("mutation", f"setitem_{inner.attr}", stmt, value)
                return Step("mutation", "setitem", stmt, value, key=literal(target.slice))
            if isinstance(target, ast.Attribute):
                return Step("mutation", f"setattr_{target.attr}", stmt, value)
        if isinstance(stmt, ast.Delete):
            return Step("mutation", "delitem", stmt, value)
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            fn = stmt.value.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "call")
            kwargs = {k.arg: literal(k.value) for k in stmt.value.keywords if k.arg}
            args = [literal(a) for a in stmt.value.args]
            return Step("mutation", name, stmt, value, args=args, kwargs=kwargs)
        return Step("mutation", "statement", stmt, value)

    # -- recording
    def emit(
        self,
        *,
        kind: str,
        before: Any,
        after: Any,
        steps: list[Step],
        code: dict | None,
        var: str | None,
        inputs: list | None = None,
        before_name: str | None = None,
        before_token: Token | None = None,
        live: Any = None,
    ) -> None:
        index = len(self.stages) + 1
        btoken = before_token if before_token is not None else (
            self.token_of(before) if before is not None else None
        )
        refs: set[str] = set()
        for s in steps:
            refs |= _step_refs(s)
        stage = Stage(
            index=index,
            kind=kind,
            before=snapshot(before) if before is not None and displayable(before) else None,
            before_token=btoken,
            after=snapshot(after),
            steps=steps,
            code=code,
            var=var,
            inputs=inputs or [],
            before_name=before_name,
            refs=refs,
        )
        self.stages.append(stage)
        self.bind(live if live is not None else after, ("stage", index))


def run_traced(code: str, inputs: dict[str, Any]) -> tuple[Tracer, dict[str, Any]]:
    ns: dict[str, Any] = {"pd": pd, "np": np, "__name__": "__main__"}
    for name, value in inputs.items():
        ns[name] = value
    tracer = Tracer(code, ns, list(inputs.keys()))
    tracer.run()
    return tracer, ns


__all__ = ["Tracer", "Stage", "Step", "UserCodeError", "run_traced", "is_table", "displayable", "snapshot"]

if __name__ == "__main__":  # pragma: no cover
    sys.exit(0)
