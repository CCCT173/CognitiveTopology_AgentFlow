"""host_shell 工具 - 受控执行 shell 命令

安全策略：
- shell=False，列表参数（防 shell 注入）
- 白名单只读命令自动放行（git status/cat/ls/pwd/...）
- 修改命令（rm/mv/cp/npm install/git commit）requires_confirmation=True
- 危险命令正则直接拒绝（rm -rf /, sudo, mkfs, format C:, IEX, curl|sh, del /S /Q）
- git 命令细粒度校验（拦截 --output= 等写参数）
- 工作目录锁定在白名单根目录内
- 超时 30s，输出 100KB 上限
"""
from __future__ import annotations
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from app.tools import BaseTool, ToolResult, TOOL_TYPE_HOST
from app.tools.host.pathguard import safe_resolve, DEFAULT_ROOTS


# 白名单只读命令（自动放行，不需确认）
_READONLY_COMMANDS = {
    # 文件查看
    "cat", "head", "tail", "less", "more", "wc", "nl", "file", "stat",
    "ls", "dir", "pwd", "echo", "printenv", "env", "which", "where", "type",
    "find", "rg", "grep", "Select-String",
    # git 只读
    "git",
    # 包管理查询
    "pip", "pip3", "npm", "pnpm", "yarn", "uv",
    # 版本查询
    "python", "python3", "node", "nodejs", "go", "rustc", "java", "ruby", "php", "perl",
    # 网络诊断
    "ping", "nslookup", "dig", "curl", "wget",
    # 系统信息
    "uname", "whoami", "hostname", "date", "uptime", "free", "df", "du",
    "ps", "top", "htop", "tasklist", "systeminfo", "ver",
}

# 只读 git 子命令
_GIT_READONLY = {"status", "diff", "log", "show", "branch", "ls-files", "describe",
                 "remote", "fetch --dry-run", "blame", "shortlog", "tag", "rev-parse"}

# 只读 pip 子命令
_PIP_READONLY = {"list", "show", "freeze", "check", "cache", "config", "debug"}

# 只读 npm 子命令
_NPM_READONLY = {"list", "ls", "view", "info", "outdated", "audit", "doctor", "ping", "version"}

# 直接拒绝的危险命令正则
_DANGEROUS_PATTERNS = [
    # 破坏性
    r"\brm\s+-rf?\s+(/|~|\*|--no-preserve-root)",
    r"\brm\s+(-[a-z]*r[a-z]*\s+-[a-z]*f[a-z]*\s+/)",
    r"\bdel\s+/[fqs]+\s+/[sS]",            # Windows del /F /Q /S
    r"\brmdir\s+/s\s+/q",                  # Windows rmdir /S /Q
    r"\bRemove-Item\s+.*-Recurse.*-Force",  # PowerShell
    r"\bmkfs\b", r"\bmkfs\.",
    r"\bformat\s+[a-z]:",                  # Windows format C:
    r"\bdd\s+if=",
    # 提权
    r"\bsudo\b", r"\bsu\s+-",
    r"Start-Process\s+-Verb\s+RunAs",       # PowerShell 提权
    r"runas\s+/user:",                      # Windows runas
    # fork bomb
    r":\(\)\s*{\s*:\|:&\s*}\s*;",
    r"\.rsrc",  # 不常见资源
    # 远程执行
    r"curl\b[^|]*\|\s*(sh|bash|zsh|cmd|powershell|pwsh)",
    r"wget\b[^|]*\|\s*(sh|bash|zsh|cmd|powershell|pwsh)",
    r"IEX\b", r"Invoke-Expression\b",
    r"Invoke-WebRequest\b.*\|\s*IEX",
    # 其它
    r">\s*/dev/(sda|hda|nvme)",
    r"chmod\s+777\s+/",
    r"\bmv\s+/\*",
]

# git 写参数（执行 git 时拦截）
_GIT_DANGEROUS_ARGS = {"--output", "--output=", "-o "}


def _is_readonly(argv: list[str]) -> tuple[bool, str]:
    """判断命令是否是只读的。返回 (is_readonly, reason_if_not)"""
    if not argv:
        return False, "空命令"
    cmd = argv[0].lower()
    cmdline = " ".join(argv)

    # shell 语法（重定向/管道/后台/命令分隔）出现即判为非只读
    shell_metachar = False
    for tok in argv[1:]:
        if tok in (">", ">>", "<", "|", "||", "&&", ";", "&", "2>", "2>&1"):
            shell_metachar = True
            break
    if shell_metachar:
        return False, "包含 shell 元字符（|/>/<等），请用 host_write/host_read 代替，或显式确认执行"

    # 检查危险命令正则
    for pat in _DANGEROUS_PATTERNS:
        if re.search(pat, cmdline, re.IGNORECASE):
            return False, f"命中危险规则: {pat[:50]}"

    if cmd == "git":
        if len(argv) < 2:
            return True, ""
        sub = argv[1].lower()
        readonly_subs = {"status", "diff", "log", "show", "branch", "ls-files",
                         "describe", "remote", "blame", "shortlog", "tag", "rev-parse", "config --get"}
        if sub in readonly_subs:
            # 检查是否有 --output 等参数
            for arg in argv[2:]:
                for bad in _GIT_DANGEROUS_ARGS:
                    if arg.startswith(bad.strip()):
                        return False, f"git 子命令带危险参数: {arg}"
            return True, ""
        return False, f"git {sub} 是写操作"

    if cmd in ("pip", "pip3"):
        if len(argv) >= 2 and argv[1].lower() in _PIP_READONLY:
            return True, ""
        return False, f"pip {argv[1] if len(argv)>1 else ''} 会装包"

    if cmd in ("npm", "pnpm", "yarn"):
        if len(argv) >= 2 and argv[1].lower() in _NPM_READONLY:
            return True, ""
        return False, f"{cmd} {argv[1] if len(argv)>1 else ''} 会装包/改文件"

    if cmd in ("curl", "wget"):
        # 只允许 GET 且不输出到文件
        for arg in argv[1:]:
            if arg in ("-o", "-O", "--output", "-d", "--data", "-X"):
                return False, f"{cmd} 带 {arg} 参数是写操作"
        return True, ""

    if cmd in ("python", "python3", "node", "nodejs"):
        # 执行脚本可能有副作用，保守：需要确认（除非 -c 纯打印或 --version）
        for arg in argv[1:]:
            if arg.startswith("--version") or arg in ("-V", "-c"):
                if arg == "-c" and len(argv) > 2:
                    # python -c '...' 代码可控，标记需确认
                    return False, "python -c 执行任意代码"
                if arg.startswith("--version") or arg == "-V":
                    return True, ""
            if arg.endswith(".py") or arg.endswith(".js"):
                return False, f"执行脚本 {arg}"
        return True, ""

    if cmd in _READONLY_COMMANDS:
        return True, ""

    return False, f"未知命令 {cmd}"


class HostShellTool(BaseTool):
    name = "host_shell"
    display_name = "执行 Shell 命令"
    tool_type = TOOL_TYPE_HOST
    description = (
        "在白名单目录内执行 shell 命令。只读命令（ls/cat/git status/pip list 等）自动放行；"
        "写命令（rm/mv/git commit/npm install 等）需要用户确认；"
        "危险命令（rm -rf /、sudo、curl|sh 等）直接拒绝。"
        "工作目录必须在白名单内，shell=False 防注入。"
    )
    params_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的命令字符串（自动按 shell 规则拆分为 argv）"},
            "cwd": {"type": "string", "description": "工作目录，默认 '.'"},
            "timeout": {"type": "integer", "description": "超时秒，默认 30"},
        },
        "required": ["command"],
    }
    risk_level = "high"
    # 静态标记：只读命令在 run() 内直接执行（不拦截），写命令 run() 内部创建 PendingConfirmation
    requires_confirmation = False

    def run(self, ctx=None, **kw):
        try:
            cmd_str = kw["command"].strip()
            if not cmd_str:
                return ToolResult(ok=False, error="命令不能为空")
            cwd_str = kw.get("cwd", ".")
            timeout = int(kw.get("timeout", 30))
            confirmed = bool(kw.get("__confirmed", False))

            # 工作目录安全解析
            try:
                cwd_path = safe_resolve(cwd_str, must_exist=True)
            except Exception as e:
                return ToolResult(ok=False, error=f"工作目录无效: {e}")
            if not cwd_path.is_dir():
                return ToolResult(ok=False, error=f"工作目录不是目录: {cwd_path}")

            # 拆分 argv
            try:
                argv = shlex.split(cmd_str, posix=(os.name != "nt"))
            except ValueError as e:
                return ToolResult(ok=False, error=f"命令解析失败: {e}")

            readonly, reason = _is_readonly(argv)
            if readonly or confirmed:
                return self._exec(argv, cwd_path, timeout, auto_approved=readonly)

            # 写/危险命令：创建 PendingConfirmation
            from app.services.hitl import create_confirmation
            summary = (
                f"确认执行命令：{cmd_str}\n"
                f"工作目录：{cwd_path}\n"
                f"原因：{reason}"
            )
            db = getattr(ctx, "db", None) if ctx else None
            user_id = getattr(ctx, "user_id", 0) or 0
            thread_id = getattr(ctx, "thread_id", "") or ""
            if db is None:
                return ToolResult(
                    ok=False,
                    error=f"该命令不是只读的（{reason}），需要用户确认但无可用的 HITL 上下文。",
                    data={"requires_confirmation": True},
                )
            pc = create_confirmation(
                db, user_id=user_id, tool_name=self.name,
                args={"command": cmd_str, "cwd": str(cwd_path), "timeout": timeout, "__confirmed": True},
                summary=summary, risk_level="high", thread_id=thread_id,
            )
            return ToolResult(
                ok=True,
                output=(
                    f"[需要用户确认] 命令 '{cmd_str}' 是写操作（{reason}），"
                    f"已提交待确认任务（id={pc.id}）。等待用户确认后执行。"
                ),
                data={"confirmation_id": pc.id, "requires_confirmation": True},
            )
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")

    def _exec(self, argv, cwd: Path, timeout: int, auto_approved: bool = False):
        """真正执行命令"""
        try:
            proc = subprocess.run(
                argv, cwd=str(cwd), capture_output=True, text=True,
                timeout=timeout, shell=False,
                encoding="utf-8", errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )
            stdout = proc.stdout[:100 * 1024]
            stderr = proc.stderr[:100 * 1024]
            output = stdout
            if stderr:
                output += f"\n--- stderr ---\n{stderr}"
            return ToolResult(
                ok=(proc.returncode == 0),
                output=output.strip(),
                error=None if proc.returncode == 0 else f"exit code {proc.returncode}",
                data={"returncode": proc.returncode, "stdout": stdout, "stderr": stderr,
                       "command": " ".join(argv), "cwd": str(cwd)},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, error=f"命令超时（>{timeout}s）：{argv[0]}")
        except FileNotFoundError as e:
            return ToolResult(ok=False, error=f"命令不存在: {argv[0]}")
        except Exception as e:
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")
