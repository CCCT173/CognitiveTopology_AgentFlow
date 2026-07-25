"""L0 Host 路径安全校验（pathguard）

- 白名单根目录解析（realpath + symlink 展开）
- Windows: 8.3 短名检测、ADS (Alternate Data Stream) 剥离、\\\\?\\ 前缀剥离、junction 检测
- Unix: symlink 解析后校验
- 敏感文件拒读/拒写：.env*, .ssh/, *.pem, *.key, id_rsa*
- Windows 保留文件名：CON/PRN/AUX/NUL/COM1-9/LPT1-9
"""
from __future__ import annotations
import os
import re
import sys
from pathlib import Path, PureWindowsPath


# 默认白名单根目录
DEFAULT_ROOTS = [
    str(Path.home() / ".agentflow"),
    str(Path.cwd()),
]

# 敏感路径模式（读/写都拒绝）
SENSITIVE_PATTERNS = [
    r"(^|[/\\])\.env(\.|$|~)",          # .env, .env.local, .env.production~
    r"(^|[/\\])\.ssh([/\\]|$)",         # .ssh/
    r"(^|[/\\])\.aws([/\\]|$)",         # .aws/
    r"(^|[/\\])\.gnupg([/\\]|$)",       # .gnupg/
    r"(^|[/\\])\.kube([/\\]|$)",        # .kube/
    r"(^|[/\\])\.docker([/\\]|$)",      # .docker/
    r"(^|[/\\])\.netrc$",               # .netrc
    r"(^|[/\\])id_rsa(\.|$|_)",         # id_rsa, id_rsa.pub
    r"(^|[/\\])id_ed25519(\.|$|_)",     # id_ed25519
    r"\.pem$",                          # *.pem
    r"\.key$",                          # *.key
    r"\.p12$",                          # *.p12
    r"\.pfx$",                          # *.pfx
    r"\.jks$",                          # *.jks
    r"\.kdbx$",                         # KeePass DB
]

# Windows 保留文件名
_WIN_RESERVED = {"CON", "PRN", "AUX", "NUL"}
_WIN_RESERVED |= {f"COM{i}" for i in range(1, 10)}
_WIN_RESERVED |= {f"LPT{i}" for i in range(1, 10)}

# WebDAV/UNC 前缀
_UNC_PREFIXES = ("\\\\", "//", "\\??\\", "\\\\?\\")


def is_sensitive(path: str | Path) -> tuple[bool, str]:
    """检查路径是否命中敏感模式。返回 (is_sensitive, matched_pattern)"""
    s = str(path).replace("\\", "/").lower()
    for pat in SENSITIVE_PATTERNS:
        if re.search(pat, s):
            return True, pat
    return False, ""


def is_windows_reserved(path: str | Path) -> bool:
    """Windows 保留文件名检测（跨平台都检查，避免跨平台场景漏检）"""
    p = PureWindowsPath(str(path).replace("/", "\\"))
    # 每个路径段都检查
    for part in p.parts:
        name = part.split(".")[0].upper()
        if name in _WIN_RESERVED:
            return True
    return False


def has_ads(path: str | Path) -> bool:
    """检测 Windows Alternate Data Stream（file.txt:secret）"""
    s = str(path)
    # Windows 下冒号除了盘符都是 ADS
    if os.name != "nt":
        return False
    # 去掉盘符 c:
    without_drive = re.sub(r"^[a-zA-Z]:", "", s)
    return ":" in without_drive


def strip_verbatim_prefix(path: str) -> str:
    r"""剥离 Windows \\?\ 和 \\.\ 等 verbatim 前缀"""
    s = path
    for prefix in ("\\\\?\\", "\\\\.\\", "//?//", "//.//"):
        if s.startswith(prefix):
            return s[len(prefix):]
    return s


def safe_resolve(path: str | Path, roots: list[str] | None = None,
                 must_exist: bool = False, allow_write: bool = False) -> Path:
    """安全解析路径：
    - 展开 ~、环境变量、符号链接
    - 剥离 verbatim 前缀、检测 ADS（Windows）
    - 验证必须在一个白名单根目录内
    - 检测敏感文件
    - 检测 Windows 保留文件名

    返回解析后的 Path；越界/敏感/保留名抛 ValueError。
    """
    roots = roots or DEFAULT_ROOTS

    # 处理输入
    raw = str(path).strip()
    if not raw:
        raise ValueError("路径不能为空")

    # WebDAV/UNC 拒绝
    if any(raw.startswith(p) for p in _UNC_PREFIXES):
        raise ValueError(f"拒绝 UNC/WebDAV 路径: {raw[:60]}")

    # 展开 ~
    raw = os.path.expanduser(raw)
    # 展开环境变量
    raw = os.path.expandvars(raw)
    # 剥离 verbatim
    raw = strip_verbatim_prefix(raw)

    # ADS 检测
    if has_ads(raw):
        raise ValueError(f"检测到 Windows 备用数据流(ADS)，拒绝: {raw[:60]}")

    p = Path(raw)
    try:
        resolved = p.resolve(strict=False)
    except OSError as e:
        raise ValueError(f"路径解析失败: {e}") from e

    # Windows 保留文件名（目标本身或父路径已有文件名）
    if is_windows_reserved(resolved):
        raise ValueError(f"Windows 保留文件名，拒绝: {resolved.name}")

    # 白名单校验
    allowed_roots = [Path(r).expanduser().resolve() for r in roots]
    in_root = False
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            in_root = True
            break
        except ValueError:
            continue
    if not in_root:
        root_list = "\n  - ".join(str(r) for r in allowed_roots)
        raise ValueError(
            f"路径越界：{resolved}\n允许的根目录：\n  - {root_list}"
        )

    # 敏感文件（读/写都查）
    sensitive, pat = is_sensitive(resolved)
    if sensitive:
        raise ValueError(f"敏感路径命中规则 {pat}，拒绝访问: {resolved}")

    # must_exist 校验
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"路径不存在: {resolved}")

    return resolved
