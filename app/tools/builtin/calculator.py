"""calculator 工具: 安全的数学表达式计算器
参数: {"expression": str}
- 只允许数字、运算符和基础数学函数
- 使用 Python eval 但做了严格白名单
"""
from __future__ import annotations
import ast
import math
import operator as op
from typing import Any
from app.tools import BaseTool


# 允许的运算符
_OPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
    ast.FloorDiv: op.floordiv, ast.Mod: op.mod, ast.Pow: op.pow,
    ast.USub: op.neg, ast.UAdd: op.pos,
}
# 允许的函数
_FUNCS = {
    "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
    "sqrt": math.sqrt, "pow": math.pow, "log": math.log, "log10": math.log10,
    "log2": math.log2, "exp": math.exp, "ceil": math.ceil, "floor": math.floor,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "pi": math.pi, "e": math.e,
}


def _eval(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"不允许的常量: {node.value!r}")
    if isinstance(node, ast.BinOp):
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("不允许调用属性方法")
        fn = _FUNCS.get(node.func.id)
        if not fn:
            raise ValueError(f"不允许的函数: {node.func.id}")
        args = [_eval(a) for a in node.args]
        return fn(*args)
    if isinstance(node, ast.Name):
        if node.id in _FUNCS and callable(_FUNCS[node.id]) is False:
            return _FUNCS[node.id]
        if node.id in ("pi", "e"):
            return _FUNCS[node.id]
        raise ValueError(f"未定义的变量: {node.id}")
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    raise ValueError(f"不支持的语法节点: {type(node).__name__}")


class CalculatorTool(BaseTool):
    name = "calculator"
    display_name = "数学计算"
    description = (
        "安全的数学表达式计算器。支持 + - * / // % ** 运算、括号、"
        "以及常用数学函数: abs, round, min, max, sqrt, pow, log, log10, log2, exp, "
        "ceil, floor, sin, cos, tan, pi, e。"
        "需要做数学计算、单位换算、公式求值时使用,不要自己心算。"
    )
    params_schema = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "数学表达式,例如: 2*3.14*50 或 sqrt(2**2 + 3**2)"},
        },
        "required": ["expression"],
    }

    def run(self, ctx: Any, **kwargs) -> str:
        expr = kwargs.get("expression", "").strip()
        if not expr:
            return "[calculator] 错误: 表达式不能为空"
        try:
            tree = ast.parse(expr, mode="eval")
            result = _eval(tree)
            return f"[calculator] {expr} = {result}"
        except Exception as e:
            return f"[calculator] 计算错误: {e}"
