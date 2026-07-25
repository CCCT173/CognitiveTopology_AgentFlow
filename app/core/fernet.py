"""
Fernet 对称加密：用于加密 DB 里的第三方 API Key / MCP 配置等敏感字段。
- key 存储：~/.agentflow/fernet.key (Unix chmod 600, Windows ACL)
- 加密格式：v{key_id}:{ciphertext}（支持多 key 轮换）
- 首次启动自动生成 key；丢失会导致历史加密数据不可恢复（启动大字警告）
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

# Fernet key 存放位置
_KEY_DIR = Path.home() / ".agentflow"
_KEY_PATH = _KEY_DIR / "fernet.key"


def _warn(msg: str):
    print("\n" + "=" * 70, file=sys.stderr)
    for line in msg.splitlines():
        print(f"  {line}", file=sys.stderr)
    print("=" * 70 + "\n", file=sys.stderr)


def _secure_path(path: Path):
    """Unix chmod 600; Windows 尝试 DACL（需要 pywin32，没有就算了）"""
    try:
        if os.name == "nt":
            try:
                import win32api  # pywin32
                import win32con
                import win32security
                user, domain, type_ = win32security.LookupAccountName(None, win32api.GetUserName())
                dacl = win32security.ACL()
                dacl.AddAccessAllowedAce(win32security.ACL_REVISION, win32con.GENERIC_ALL, user)
                sd = win32security.GetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION)
                sd.SetSecurityDescriptorDacl(1, dacl, 0)
                win32security.SetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION, sd)
            except ImportError:
                pass  # pywin32 没装就跳过
        else:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass


def generate_key() -> bytes:
    return Fernet.generate_key()


def load_or_create_key() -> bytes:
    """读 fernet.key；不存在则自动生成"""
    if not _KEY_PATH.exists():
        _KEY_DIR.mkdir(parents=True, exist_ok=True)
        key = generate_key()
        _KEY_PATH.write_bytes(key)
        _secure_path(_KEY_PATH)
        _warn(
            "⚠️  已生成新的 Fernet 加密 key\n"
            f"  位置: {_KEY_PATH}\n"
            "  请立即备份此文件。丢失后所有已加密的第三方密钥/Token 将不可恢复。"
        )
        return key
    # 读取并校验
    key = _KEY_PATH.read_bytes().strip()
    try:
        Fernet(key)
    except Exception as e:
        raise RuntimeError(
            f"Fernet key at {_KEY_PATH} 格式错误: {e}。删除后重启重新生成（旧加密数据不可解密）"
        ) from e
    return key


class FernetManager:
    """多 key 管理器（支持轮换），当前实现单 key，预留 key_id 扩展"""

    def __init__(self):
        self._primary_key = load_or_create_key()
        self._fernets: dict[int, Fernet] = {1: Fernet(self._primary_key)}
        self._primary_id: int = 1

    def encrypt(self, plaintext: str) -> str:
        """加密字符串，返回 v{id}:{token}"""
        if plaintext is None:
            return ""
        token = self._fernets[self._primary_id].encrypt(plaintext.encode("utf-8")).decode("ascii")
        return f"v{self._primary_id}:{token}"

    def decrypt(self, ciphertext: str) -> Optional[str]:
        """解密；非法/失败返回 None"""
        if not ciphertext:
            return None
        try:
            if ciphertext.startswith("v"):
                # v1:xxx
                vid, token = ciphertext[1:].split(":", 1)
                kid = int(vid)
            else:
                kid, token = 1, ciphertext
            f = self._fernets.get(kid)
            if not f:
                return None
            return f.decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError, Exception):
            return None


_manager: Optional[FernetManager] = None


def get_fernet() -> FernetManager:
    global _manager
    if _manager is None:
        _manager = FernetManager()
    return _manager


def encrypt(plaintext: str) -> str:
    return get_fernet().encrypt(plaintext)


def decrypt(ciphertext: str) -> Optional[str]:
    return get_fernet().decrypt(ciphertext)
