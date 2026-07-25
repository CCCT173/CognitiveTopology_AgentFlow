"""
统一错误码 + 应用异常基类
所有业务异常在 service 层 raise AppException(code, message),
全局异常处理器统一返回 {code, msg, data}
HTTP 状态码默认 400, 鉴权类用 401/403
"""
import logging
from enum import IntEnum
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger("app")


class ErrorCode(IntEnum):
    OK = 0

    # 通用 400x
    BAD_REQUEST = 4000
    NOT_FOUND = 4040
    CONFLICT = 4090         # 资源冲突(重名等)
    VALIDATION = 4220

    # 鉴权 401x/403x
    UNAUTHORIZED = 4010
    TOKEN_EXPIRED = 4011
    FORBIDDEN = 4030

    # 用户/账号 1xxx
    USER_EXISTS = 1001
    USER_NOT_FOUND = 1002
    WRONG_PASSWORD = 1003
    WEAK_PASSWORD = 1004
    BIND_ADMIN_INVALID = 1005

    # Agent/Knowledge/Doc/Chunk/Workflow 2xxx-5xxx
    AGENT_NOT_FOUND = 2001
    AGENT_CONFLICT = 2002
    KB_NOT_FOUND = 3001
    KB_CONFLICT = 3002
    DOC_NOT_FOUND = 3101
    CHUNK_NOT_FOUND = 3201
    INVALID_SPLITTER = 3301
    INVALID_REGEX = 3302
    UPLOAD_FAILED = 3401
    ICON_TYPE_INVALID = 3402
    WF_NOT_FOUND = 4001
    WF_DISABLED = 4002
    WF_EXEC_FAILED = 4003

    # 群组 5xxx
    GROUP_NOT_FOUND = 5001
    NOT_GROUP_MEMBER = 5002
    NOT_GROUP_OWNER = 5003
    ALREADY_MEMBER = 5004
    AGENT_NOT_SHARED = 5005
    KB_NOT_SHARED = 5006
    MSG_NOT_FOUND = 5007

    # LLM/Embedding/向量库 6xxx
    LLM_ERROR = 6001
    EMBEDDING_ERROR = 6002
    VECTOR_STORE_ERROR = 6003

    # 系统 9xxx
    INTERNAL = 9000
    RATE_LIMIT = 9001


# code -> HTTP 状态码
CODE_HTTP_STATUS = {
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.TOKEN_EXPIRED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.VALIDATION: 422,
    ErrorCode.RATE_LIMIT: 429,
}


class AppException(Exception):
    """业务异常基类。所有 service 层抛出这个,不抛 HTTPException"""

    def __init__(self, code: int | ErrorCode, msg: str = "", http_status: int | None = None, data=None):
        self.code = int(code)
        self.msg = msg or _default_msg(code)
        self.data = data
        if http_status is not None:
            self.http_status = http_status
        else:
            self.http_status = CODE_HTTP_STATUS.get(ErrorCode(self.code) if self.code in ErrorCode._value2member_map_ else 0, 400)
        super().__init__(self.msg)


def _default_msg(code) -> str:
    try:
        ec = ErrorCode(code)
        return ec.name.lower().replace("_", " ")
    except Exception:
        return "error"


# ---------- 常用便捷异常 ----------
def bad_request(msg: str = "参数错误"):
    return AppException(ErrorCode.BAD_REQUEST, msg)


def not_found(msg: str = "资源不存在"):
    return AppException(ErrorCode.NOT_FOUND, msg, 404)


def conflict(msg: str = "资源已存在"):
    return AppException(ErrorCode.CONFLICT, msg, 409)


def unauthorized(msg: str = "未登录或 token 无效"):
    return AppException(ErrorCode.UNAUTHORIZED, msg, 401)


def forbidden(msg: str = "无权限"):
    return AppException(ErrorCode.FORBIDDEN, msg, 403)


# ---------- 兼容旧代码的别名类(工厂) ----------
# 旧代码里写 `raise ErrNotFound("xxx")` 仍然可用,内部走 AppException
class ErrNotFound(AppException):
    def __init__(self, msg: str = "资源不存在"):
        super().__init__(ErrorCode.NOT_FOUND, msg, 404)


class ErrBadRequest(AppException):
    def __init__(self, msg: str = "参数错误"):
        super().__init__(ErrorCode.BAD_REQUEST, msg, 400)


class ErrConflict(AppException):
    def __init__(self, msg: str = "资源已存在"):
        super().__init__(ErrorCode.CONFLICT, msg, 409)


class ErrUnauth(AppException):
    def __init__(self, msg: str = "未登录或 token 无效"):
        super().__init__(ErrorCode.UNAUTHORIZED, msg, 401)


class ErrForbidden(AppException):
    def __init__(self, msg: str = "无权限"):
        super().__init__(ErrorCode.FORBIDDEN, msg, 403)


# ---------- 全局异常处理器注册 ----------
def register_exception_handlers(app):
    @app.exception_handler(AppException)
    async def _app_exc_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.http_status,
            content={"code": exc.code, "msg": exc.msg, "data": exc.data},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        # pydantic 参数校验错误
        msg = "; ".join(f"{e['loc'][-1]}: {e['msg']}" for e in exc.errors())
        return JSONResponse(status_code=422, content={"code": ErrorCode.VALIDATION, "msg": msg, "data": exc.errors()})

    @app.exception_handler(Exception)
    async def _unknown_handler(request: Request, exc: Exception):
        logger.exception(f"未处理异常: {exc}")
        return JSONResponse(status_code=500, content={"code": ErrorCode.INTERNAL, "msg": f"服务器内部错误: {exc}", "data": None})
