"""
安全表达式求值: 用于工作流 condition 节点。
- 替换裸 eval(__builtins__={})，后者仍可通过 Python 元类逃逸
- 使用 simpleeval，严格禁用属性访问/下标访问自定义类/双下划线
"""
from simpleeval import EvalWithCompoundTypes
import math


# 允许的名称（工作流上下文变量通过 names 参数传入，这里是默认安全集合）
_SAFE_NAMES = {
    "True": True, "False": False, "None": None,
    "true": True, "false": False, "null": None,
    "abs": abs, "min": min, "max": max, "len": len,
    "round": round, "sum": sum,
    "int": int, "float": float, "str": str, "bool": bool,
    "list": list, "dict": dict,
}


def _make_evaluator(names: dict) -> EvalWithCompoundTypes:
    """创建严格配置的 simpleeval 评估器：拒绝所有属性访问。"""
    # allowed_attrs={} 表示任何类型都不允许属性访问
    # simpleeval 默认会拒绝双下划线开头的属性，但要显式禁用所有 .attr
    return EvalWithCompoundTypes(
        names=names,
        functions={
            "abs": abs, "min": min, "max": max, "len": len,
            "round": round, "sum": sum, "int": int, "float": float,
            "str": str, "bool": bool, "list": list, "dict": dict,
        },
        allowed_attrs={},  # 关键：禁用所有属性访问，阻断 __class__ 等逃逸
    )


def safe_eval_bool(expression: str, names: dict | None = None) -> bool:
    """
    安全求值布尔表达式。
    :param expression: 如 "score > 0.8 and count < 100"
    :param names: 上下文中的变量名
    """
    if not expression or not expression.strip():
        return False
    merged = dict(_SAFE_NAMES)
    if names:
        merged.update(names)
    try:
        s = _make_evaluator(merged)
        result = s.eval(expression)
        return bool(result)
    except Exception:
        # 严格 fallback: 只有明确的真值字符串才算 True，其他全部 False
        v = expression.strip().lower()
        return v in ("true", "1", "yes", "y", "on")


def safe_eval_value(expression: str, names: dict | None = None):
    """返回任意类型结果（非强制 bool）。"""
    if not expression or not expression.strip():
        return None
    merged = dict(_SAFE_NAMES)
    if names:
        merged.update(names)
    try:
        s = _make_evaluator(merged)
        return s.eval(expression)
    except Exception:
        return None
