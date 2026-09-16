"""文件读写工具：供 Engineer 调用落盘, UserProxy 执行验证。"""
import os

# 只允许写到项目安全目录，防止 LLM 乱写盘（../、C:\ 等一律拒绝）
ALLOWED_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))


def _safe_path(filename: str) -> str:
    """把文件名限制在 ALLOWED_DIR 内，返回绝对路径。"""
    os.makedirs(ALLOWED_DIR, exist_ok=True)
    # 只取 basename，丢掉任何目录穿越
    safe_name = os.path.basename(filename.strip())
    if not safe_name or safe_name in (".", ".."):
        raise ValueError(f"非法文件名: {filename!r}")
    full = os.path.abspath(os.path.join(ALLOWED_DIR, safe_name))
    if not full.startswith(ALLOWED_DIR):
        raise ValueError(f"越权路径被拒绝: {filename!r}")
    return full


def write_file(filename: str, content: str) -> str:
    """把完整代码写入文件并返回确认信息。

    Args:
        filename: 文件名，如 app.py(只取 basename, 固定写到 output/ 目录)。
        content: 要写入的完整文件内容。

    Returns:
        成功信息，含绝对路径和字节数；失败时返回错误描述。
    """
    try:
        full_path = _safe_path(filename)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        size = os.path.getsize(full_path)
        return f"文件已保存: {full_path}({size} 字节)。请 UserProxy 运行验证。"
    except Exception as e:
        return f"写文件失败: {e}"


def read_file(filename: str) -> str:
    """读回文件内容，用于验证是否落盘成功。"""
    try:
        full_path = _safe_path(filename)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"读文件失败: {e}"


def verify_python_syntax(filename: str) -> str:
    """用 py_compile 做语法检查，不真正启动 streamlit(避免阻塞)。"""
    import py_compile

    try:
        full_path = _safe_path(filename)
        py_compile.compile(full_path, doraise=True)
        return f"语法检查通过: {full_path}"
    except Exception as e:
        return f"语法检查失败: {e}"
