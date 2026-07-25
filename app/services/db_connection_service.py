"""
数据库连接配置服务层
负责数据库连接的 CRUD、密码加密、连接测试、导入导出等功能
"""
from __future__ import annotations
import json
import base64
from datetime import datetime
from typing import Optional, Any, List
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.models.db_connection import DbConnection
from app.models.audit import AuditLog
from app.schemas.db_connection import (
    DbConnectionCreate, DbConnectionUpdate, DbConnectionOut,
    DbConnectionTestIn, DbConnectionTestOut,
    DbConnectionImportIn, DbConnectionExportOut,
)
from app.core.exceptions import ErrNotFound, ErrConflict, ErrBadRequest
from app.core.logger import logger
from app.core.config import settings

# 密码加密密钥（使用环境变量或生成）
try:
    _FERNET_KEY = settings.DB_CONNECTION_ENCRYPT_KEY.encode()
    if len(_FERNET_KEY) != 44:
        raise ValueError("DB_CONNECTION_ENCRYPT_KEY must be 44 base64 characters")
except Exception:
    _FERNET_KEY = Fernet.generate_key()
    logger.warning("DB_CONNECTION_ENCRYPT_KEY not configured, using generated key (will change on restart)")

_FERNET = Fernet(_FERNET_KEY)


def _encrypt_password(password: Optional[str]) -> Optional[str]:
    """加密密码"""
    if not password:
        return None
    try:
        return _FERNET.encrypt(password.encode()).decode()
    except Exception as e:
        logger.error(f"密码加密失败: {e}")
        return None


def _decrypt_password(encrypted_password: Optional[str]) -> Optional[str]:
    """解密密码"""
    if not encrypted_password:
        return None
    try:
        return _FERNET.decrypt(encrypted_password.encode()).decode()
    except InvalidToken:
        logger.warning("密码解密失败: 无效的密钥")
        return None
    except Exception as e:
        logger.error(f"密码解密失败: {e}")
        return None


def _mask_password(password: Optional[str]) -> Optional[str]:
    """密码脱敏显示"""
    if not password:
        return None
    return "******"


def _to_out(conn: DbConnection) -> DbConnectionOut:
    """转换为响应模型（密码脱敏）"""
    out = DbConnectionOut.from_orm(conn)
    out.password = _mask_password(conn.password)
    # 格式化时间
    if conn.created_at:
        out.created_at = conn.created_at.isoformat()
    if conn.updated_at:
        out.updated_at = conn.updated_at.isoformat()
    return out


def _log_audit(db: Session, user_id: int, action: str, resource: str, detail: str):
    """记录操作日志"""
    try:
        db.add(AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            detail=detail,
        ))
        db.commit()
    except Exception as e:
        logger.error(f"记录审计日志失败: {e}")


# ===== CRUD 操作 =====

def list_connections(db: Session) -> List[DbConnectionOut]:
    """获取所有数据库连接配置"""
    query = select(DbConnection).order_by(DbConnection.name)
    results = db.execute(query).scalars().all()
    return [_to_out(conn) for conn in results]


def get_connection(db: Session, conn_id: int) -> DbConnectionOut:
    """获取单个数据库连接配置"""
    conn = db.get(DbConnection, conn_id)
    if not conn:
        raise ErrNotFound(f"数据库连接配置 {conn_id} 不存在")
    return _to_out(conn)


def get_connection_by_name(db: Session, name: str) -> Optional[DbConnectionOut]:
    """按名称获取数据库连接配置"""
    query = select(DbConnection).where(DbConnection.name == name)
    conn = db.execute(query).scalar_one_or_none()
    if not conn:
        return None
    return _to_out(conn)


def create_connection(db: Session, data: DbConnectionCreate, user_id: int = 0) -> DbConnectionOut:
    """创建数据库连接配置"""
    # 检查名称是否已存在
    existing = db.execute(
        select(DbConnection).where(DbConnection.name == data.name)
    ).scalar_one_or_none()
    if existing:
        raise ErrConflict(f"连接名称 '{data.name}' 已存在")

    # 处理默认连接
    if data.is_default:
        # 取消其他默认连接
        db.execute(update(DbConnection).where(DbConnection.is_default == True).values(is_default=False))

    # 创建连接配置（密码加密）
    conn = DbConnection(
        name=data.name,
        display_name=data.display_name or data.name,
        db_type=data.db_type,
        host=data.host,
        port=data.port,
        database=data.database,
        username=data.username,
        password=_encrypt_password(data.password),
        charset=data.charset,
        timeout=data.timeout,
        extra_config=data.extra_config,
        enabled=data.enabled,
        is_default=data.is_default,
        description=data.description,
        created_by=user_id,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)

    _log_audit(db, user_id, "create", "db_connection", f"创建数据库连接: {conn.name}")
    logger.info(f"数据库连接配置已创建: {conn.name}")
    return _to_out(conn)


def update_connection(db: Session, conn_id: int, data: DbConnectionUpdate, user_id: int = 0) -> DbConnectionOut:
    """更新数据库连接配置"""
    conn = db.get(DbConnection, conn_id)
    if not conn:
        raise ErrNotFound(f"数据库连接配置 {conn_id} 不存在")

    # 更新字段
    if data.display_name is not None:
        conn.display_name = data.display_name
    if data.db_type is not None:
        conn.db_type = data.db_type
    if data.host is not None:
        conn.host = data.host
    if data.port is not None:
        conn.port = data.port
    if data.database is not None:
        conn.database = data.database
    if data.username is not None:
        conn.username = data.username
    if data.password is not None:
        conn.password = _encrypt_password(data.password)
    if data.charset is not None:
        conn.charset = data.charset
    if data.timeout is not None:
        conn.timeout = data.timeout
    if data.extra_config is not None:
        conn.extra_config = data.extra_config
    if data.enabled is not None:
        conn.enabled = data.enabled
    if data.is_default is not None:
        if data.is_default:
            # 取消其他默认连接
            db.execute(update(DbConnection).where(DbConnection.is_default == True).values(is_default=False))
        conn.is_default = data.is_default
    if data.description is not None:
        conn.description = data.description

    db.commit()
    db.refresh(conn)

    _log_audit(db, user_id, "update", "db_connection", f"更新数据库连接: {conn.name}")
    logger.info(f"数据库连接配置已更新: {conn.name}")
    return _to_out(conn)


def delete_connection(db: Session, conn_id: int, user_id: int = 0):
    """删除数据库连接配置"""
    conn = db.get(DbConnection, conn_id)
    if not conn:
        raise ErrNotFound(f"数据库连接配置 {conn_id} 不存在")

    name = conn.name
    db.delete(conn)
    db.commit()

    _log_audit(db, user_id, "delete", "db_connection", f"删除数据库连接: {name}")
    logger.info(f"数据库连接配置已删除: {name}")


def toggle_connection(db: Session, conn_id: int, enabled: bool, user_id: int = 0) -> DbConnectionOut:
    """启用/禁用数据库连接配置"""
    conn = db.get(DbConnection, conn_id)
    if not conn:
        raise ErrNotFound(f"数据库连接配置 {conn_id} 不存在")

    conn.enabled = enabled
    db.commit()
    db.refresh(conn)

    _log_audit(db, user_id, "update", "db_connection", f"{'启用' if enabled else '禁用'}数据库连接: {conn.name}")
    logger.info(f"数据库连接配置已{'启用' if enabled else '禁用'}: {conn.name}")
    return _to_out(conn)


# ===== 连接测试 =====

def test_connection(db: Session, data: DbConnectionTestIn) -> DbConnectionTestOut:
    """测试数据库连接"""
    try:
        db_type = data.db_type.lower()
        
        if db_type == "mysql":
            return _test_mysql_connection(data)
        elif db_type == "postgresql":
            return _test_postgresql_connection(data)
        elif db_type == "mongodb":
            return _test_mongodb_connection(data)
        elif db_type == "sqlite":
            return _test_sqlite_connection(data)
        elif db_type == "sqlserver":
            return _test_sqlserver_connection(data)
        elif db_type == "oracle":
            return _test_oracle_connection(data)
        else:
            return DbConnectionTestOut(
                success=False,
                message=f"不支持的数据库类型: {db_type}",
                error=f"不支持的数据库类型: {db_type}",
            )
    except Exception as e:
        logger.error(f"数据库连接测试失败: {e}")
        return DbConnectionTestOut(
            success=False,
            message=f"连接测试失败: {str(e)}",
            error=str(e),
        )


def _test_mysql_connection(data: DbConnectionTestIn) -> DbConnectionTestOut:
    """测试 MySQL 连接"""
    try:
        import pymysql
        connection = pymysql.connect(
            host=data.host or "localhost",
            port=data.port or 3306,
            user=data.username,
            password=data.password,
            database=data.database,
            charset=data.charset or "utf8mb4",
            connect_timeout=data.timeout or 10,
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
        connection.close()
        return DbConnectionTestOut(
            success=True,
            message="MySQL 连接成功",
            version=str(version),
        )
    except Exception as e:
        return DbConnectionTestOut(
            success=False,
            message=f"MySQL 连接失败: {str(e)}",
            error=str(e),
        )


def _test_postgresql_connection(data: DbConnectionTestIn) -> DbConnectionTestOut:
    """测试 PostgreSQL 连接"""
    try:
        import psycopg2
        connection = psycopg2.connect(
            host=data.host or "localhost",
            port=data.port or 5432,
            user=data.username,
            password=data.password,
            database=data.database,
            connect_timeout=data.timeout or 10,
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
        connection.close()
        return DbConnectionTestOut(
            success=True,
            message="PostgreSQL 连接成功",
            version=str(version),
        )
    except ImportError:
        return DbConnectionTestOut(
            success=False,
            message="PostgreSQL 驱动未安装，请安装 psycopg2",
            error="psycopg2 not installed",
        )
    except Exception as e:
        return DbConnectionTestOut(
            success=False,
            message=f"PostgreSQL 连接失败: {str(e)}",
            error=str(e),
        )


def _test_mongodb_connection(data: DbConnectionTestIn) -> DbConnectionTestOut:
    """测试 MongoDB 连接"""
    try:
        from pymongo import MongoClient
        uri = f"mongodb://{data.username}:{data.password}@{data.host}:{data.port}/" if data.username else f"mongodb://{data.host}:{data.port}/"
        client = MongoClient(uri, serverSelectionTimeoutMS=(data.timeout or 10) * 1000)
        version = client.server_info().get("version")
        client.close()
        return DbConnectionTestOut(
            success=True,
            message="MongoDB 连接成功",
            version=str(version),
        )
    except ImportError:
        return DbConnectionTestOut(
            success=False,
            message="MongoDB 驱动未安装，请安装 pymongo",
            error="pymongo not installed",
        )
    except Exception as e:
        return DbConnectionTestOut(
            success=False,
            message=f"MongoDB 连接失败: {str(e)}",
            error=str(e),
        )


def _test_sqlite_connection(data: DbConnectionTestIn) -> DbConnectionTestOut:
    """测试 SQLite 连接"""
    try:
        import sqlite3
        db_path = data.database or ":memory:"
        connection = sqlite3.connect(db_path, timeout=data.timeout or 10)
        cursor = connection.cursor()
        cursor.execute("SELECT sqlite_version()")
        version = cursor.fetchone()[0]
        connection.close()
        return DbConnectionTestOut(
            success=True,
            message="SQLite 连接成功",
            version=str(version),
        )
    except Exception as e:
        return DbConnectionTestOut(
            success=False,
            message=f"SQLite 连接失败: {str(e)}",
            error=str(e),
        )


def _test_sqlserver_connection(data: DbConnectionTestIn) -> DbConnectionTestOut:
    """测试 SQL Server 连接"""
    try:
        import pyodbc
        conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={data.host},{data.port or 1433};DATABASE={data.database};UID={data.username};PWD={data.password};CONNECTION TIMEOUT={data.timeout or 10}"
        connection = pyodbc.connect(conn_str)
        cursor = connection.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        connection.close()
        return DbConnectionTestOut(
            success=True,
            message="SQL Server 连接成功",
            version=str(version),
        )
    except ImportError:
        return DbConnectionTestOut(
            success=False,
            message="SQL Server 驱动未安装，请安装 pyodbc",
            error="pyodbc not installed",
        )
    except Exception as e:
        return DbConnectionTestOut(
            success=False,
            message=f"SQL Server 连接失败: {str(e)}",
            error=str(e),
        )


def _test_oracle_connection(data: DbConnectionTestIn) -> DbConnectionTestOut:
    """测试 Oracle 连接"""
    try:
        import cx_Oracle
        dsn = cx_Oracle.makedsn(data.host, data.port or 1521, service_name=data.database)
        connection = cx_Oracle.connect(user=data.username, password=data.password, dsn=dsn, connection_timeout=data.timeout or 10)
        version = connection.version
        connection.close()
        return DbConnectionTestOut(
            success=True,
            message="Oracle 连接成功",
            version=str(version),
        )
    except ImportError:
        return DbConnectionTestOut(
            success=False,
            message="Oracle 驱动未安装，请安装 cx_Oracle",
            error="cx_Oracle not installed",
        )
    except Exception as e:
        return DbConnectionTestOut(
            success=False,
            message=f"Oracle 连接失败: {str(e)}",
            error=str(e),
        )


# ===== 导入导出 =====

def export_connections(db: Session) -> DbConnectionExportOut:
    """导出所有数据库连接配置（密码脱敏）"""
    connections = list_connections(db)
    return DbConnectionExportOut(
        connections=connections,
        export_time=datetime.now().isoformat(),
    )


def import_connections(db: Session, data: DbConnectionImportIn, user_id: int = 0) -> List[DbConnectionOut]:
    """导入数据库连接配置"""
    results = []
    for item in data.connections:
        try:
            # 检查名称是否已存在
            existing = db.execute(
                select(DbConnection).where(DbConnection.name == item.name)
            ).scalar_one_or_none()
            if existing:
                # 更新现有配置
                update_data = DbConnectionUpdate(
                    display_name=item.display_name,
                    db_type=item.db_type,
                    host=item.host,
                    port=item.port,
                    database=item.database,
                    username=item.username,
                    password=item.password,
                    charset=item.charset,
                    timeout=item.timeout,
                    extra_config=item.extra_config,
                    enabled=item.enabled,
                    is_default=item.is_default,
                    description=item.description,
                )
                result = update_connection(db, existing.id, update_data, user_id)
            else:
                # 创建新配置
                result = create_connection(db, item, user_id)
            results.append(result)
        except Exception as e:
            logger.error(f"导入连接 {item.name} 失败: {e}")
            continue

    _log_audit(db, user_id, "import", "db_connection", f"导入了 {len(results)} 个数据库连接配置")
    logger.info(f"数据库连接配置已导入: {len(results)} 个")
    return results


# ===== 工具函数 =====

def get_db_url(conn: DbConnection) -> str:
    """根据连接配置生成数据库 URL"""
    password = _decrypt_password(conn.password)
    db_type = conn.db_type.lower()
    
    if db_type == "mysql":
        return f"mysql+pymysql://{conn.username}:{password}@{conn.host}:{conn.port}/{conn.database}?charset={conn.charset or 'utf8mb4'}"
    elif db_type == "postgresql":
        return f"postgresql://{conn.username}:{password}@{conn.host}:{conn.port}/{conn.database}"
    elif db_type == "mongodb":
        return f"mongodb://{conn.username}:{password}@{conn.host}:{conn.port}/{conn.database}"
    elif db_type == "sqlite":
        return f"sqlite:///{conn.database}"
    elif db_type == "sqlserver":
        return f"mssql+pyodbc://{conn.username}:{password}@{conn.host}:{conn.port}/{conn.database}?driver=ODBC+Driver+17+for+SQL+Server"
    elif db_type == "oracle":
        return f"oracle+cx_oracle://{conn.username}:{password}@{conn.host}:{conn.port}/{conn.database}"
    else:
        return ""
