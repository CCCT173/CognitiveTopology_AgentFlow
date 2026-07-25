"""通用响应包装"""
from typing import Any, Optional
from pydantic import BaseModel


class Resp(BaseModel):
    code: int = 0
    msg: str = "ok"
    data: Optional[Any] = None


def ok(data=None, msg: str = "ok") -> Resp:
    return Resp(code=0, msg=msg, data=data)
