# my_calculator_tool.py
import ast
import math
import operator

from hello_agents import ToolRegistry


def my_calculate(expression: str) -> str:
    """简单的数学计算函数"""
    if not expression.strip():
        return "计算表达式不能为空"

    # 支持的基本运算
    operators = {
        ast.Add: operator.add,      # +
        ast.Sub: operator.sub,      # -
        ast.Mult: operator.mul,     # *
        ast.Div: operator.truediv,  # /
        ast.USub: operator.neg,     # 一元负号, 如 -3 (AST里-1是UnaryOp不是常量!)
        ast.UAdd: operator.pos,     # 一元正号, 如 +3
    }

    # 支持的基本函数
    functions = {
        'sqrt': math.sqrt,
        'pi': math.pi,
    }

    try:
        node = ast.parse(expression, mode='eval')
        result = _eval_node(node.body, operators, functions)
        return str(result)
    except (SyntaxError, TypeError, ValueError, ZeroDivisionError) as e:
        # 点名捕获: 不吞 Ctrl+C(SystemExit/KeyboardInterrupt), 且把真实原因返回给agent
        # (工具的错误信息会被agent看到并用于自我修正, 越具体重试成功率越高)
        return f"计算失败: {e} (请检查表达式格式)"

def _eval_node(node, operators, functions):
    """简化的表达式求值"""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        left = _eval_node(node.left, operators, functions)
        right = _eval_node(node.right, operators, functions)
        op = operators.get(type(node.op))
        if op is None:
            # 显式报不支持的运算符(如 ** %), 而不是模糊的NoneType错误
            raise TypeError(f"不支持的运算符: {type(node.op).__name__}")
        return op(left, right)
    elif isinstance(node, ast.UnaryOp):
        val = _eval_node(node.operand, operators, functions)
        op = operators.get(type(node.op))
        if op is None:
            raise TypeError(f"不支持的一元运算符: {type(node.op).__name__}")
        return op(val)
    elif isinstance(node, ast.Call):
        func_name = node.func.id
        if func_name in functions:
            args = [_eval_node(arg, operators, functions) for arg in node.args]
            return functions[func_name](*args)
    elif isinstance(node, ast.Name) and node.id in functions:
        return functions[node.id]

def create_calculator_registry():
    """创建包含计算器的工具注册表"""
    registry = ToolRegistry()

    # 注册计算器函数
    registry.register_function(
        name="my_calculator",
        description="简单的数学计算工具，支持基本运算(+,-,*,/)和sqrt函数",
        func=my_calculate
    )

    return registry