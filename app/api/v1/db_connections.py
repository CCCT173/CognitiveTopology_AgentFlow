"""
数据库连接配置 API 路由
仅超级管理员可访问
"""
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.db_connection import (
    DbConnectionCreate, DbConnectionUpdate, DbConnectionOut,
    DbConnectionTestIn, DbConnectionTestOut,
    DbConnectionImportIn, DbConnectionExportOut,
)
from app.services import db_connection_service as conn_svc
from app.core.security import get_current_super_admin
from app.core.response import ok

router = APIRouter(prefix="/db-connections", tags=["数据库连接配置"])


# ===== CRUD 操作 =====

@router.get("", summary="获取所有数据库连接配置")
def list_connections(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_super_admin),
) -> List[DbConnectionOut]:
    """获取所有数据库连接配置列表（密码脱敏）"""
    return ok(conn_svc.list_connections(db))


@router.get("/{conn_id}", summary="获取单个数据库连接配置")
def get_connection(
    conn_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_super_admin),
) -> DbConnectionOut:
    """获取指定 ID 的数据库连接配置（密码脱敏）"""
    return ok(conn_svc.get_connection(db, conn_id))


@router.post("", summary="创建数据库连接配置")
def create_connection(
    data: DbConnectionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_super_admin),
) -> DbConnectionOut:
    """创建新的数据库连接配置（密码自动加密存储）"""
    return ok(conn_svc.create_connection(db, data, user.user_id))


@router.patch("/{conn_id}", summary="更新数据库连接配置")
def update_connection(
    conn_id: int,
    data: DbConnectionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_super_admin),
) -> DbConnectionOut:
    """更新指定 ID 的数据库连接配置"""
    return ok(conn_svc.update_connection(db, conn_id, data, user.user_id))


@router.delete("/{conn_id}", summary="删除数据库连接配置")
def delete_connection(
    conn_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_super_admin),
):
    """删除指定 ID 的数据库连接配置"""
    conn_svc.delete_connection(db, conn_id, user.user_id)
    return ok(msg="已删除")


@router.post("/{conn_id}/toggle", summary="启用/禁用数据库连接配置")
def toggle_connection(
    conn_id: int,
    enabled: bool = Query(..., description="是否启用"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_super_admin),
) -> DbConnectionOut:
    """启用或禁用指定的数据库连接配置"""
    return ok(conn_svc.toggle_connection(db, conn_id, enabled, user.user_id))


# ===== 连接测试 =====

@router.post("/test", summary="测试数据库连接")
def test_connection(
    data: DbConnectionTestIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_super_admin),
) -> DbConnectionTestOut:
    """测试数据库连接配置的有效性（不保存配置）"""
    return ok(conn_svc.test_connection(db, data))


@router.post("/{conn_id}/test", summary="测试已保存的数据库连接")
def test_saved_connection(
    conn_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_super_admin),
) -> DbConnectionTestOut:
    """测试已保存的数据库连接配置"""
    conn = conn_svc.get_connection(db, conn_id)
    # 创建测试参数（密码需要从数据库获取并解密）
    test_data = DbConnectionTestIn(
        db_type=conn.db_type,
        host=conn.host,
        port=conn.port,
        database=conn.database,
        username=conn.username,
        password=conn.password,  # 这里传入的是脱敏密码，测试时会使用解密后的密码
        charset=conn.charset,
        timeout=conn.timeout,
        extra_config=conn.extra_config,
    )
    # 需要从数据库获取解密后的密码
    from app.services.db_connection_service import _decrypt_password
    from app.models.db_connection import DbConnection
    db_conn = db.get(DbConnection, conn_id)
    test_data.password = _decrypt_password(db_conn.password)
    return ok(conn_svc.test_connection(db, test_data))


# ===== 导入导出 =====

@router.get("/export", summary="导出数据库连接配置")
def export_connections(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_super_admin),
) -> DbConnectionExportOut:
    """导出所有数据库连接配置（密码脱敏）"""
    return ok(conn_svc.export_connections(db))


@router.post("/import", summary="导入数据库连接配置")
def import_connections(
    data: DbConnectionImportIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_super_admin),
) -> List[DbConnectionOut]:
    """导入数据库连接配置（密码自动加密存储）"""
    return ok(conn_svc.import_connections(db, data, user.user_id))
