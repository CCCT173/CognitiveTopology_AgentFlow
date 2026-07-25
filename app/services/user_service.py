"""用户业务逻辑"""
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from app.models.user import User
from app.schemas.user import RegisterIn, UserUpdateMe, UserCreate, UserUpdate, UserTreeNode
from app.core.exceptions import ErrBadRequest, ErrNotFound, ErrUnauth, ErrForbidden
from app.core.security import hash_password, verify_password
from app.core.time import utc_now, utc_now_naive


ONLINE_WINDOW_SEC = 60  # last_active_at 在60秒内视为在线


def get_user_by_id(db: Session, user_id: int) -> User:
    u = db.get(User, user_id)
    if not u:
        raise ErrNotFound(f"用户 {user_id} 不存在")
    return u


def register(db: Session, body: RegisterIn) -> User:
    """公开注册: 默认不绑定管理员, 需要 admin/super_admin 后续绑定或通过 /admin/create 接口创建时指定"""
    exists = db.scalar(
        select(User).where((User.account == body.account) | (User.email == body.email))
    )
    if exists:
        raise ErrBadRequest("账号或邮箱已存在")

    # 如果传了 bind_admin_id 校验合法性
    bind_admin_id = body.bind_admin_id
    if bind_admin_id is not None:
        admin = db.get(User, bind_admin_id)
        if not admin or admin.role not in ("admin", "super_admin"):
            raise ErrBadRequest("bind_admin_id 必须是一个次级管理员或超级管理员")

    user = User(
        username=body.username,
        account=body.account,
        email=body.email,
        password_hash=hash_password(body.password),
        bind_admin_id=bind_admin_id,
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def admin_create_user(db: Session, operator: User, body: RegisterIn) -> User:
    """管理员创建用户: admin 只能把用户绑定给自己, super_admin 可指定任意 admin"""
    bind_admin_id = body.bind_admin_id
    if operator.role == "admin":
        # 次级管理员创建的用户必须绑定自己
        bind_admin_id = operator.user_id
    elif operator.role == "super_admin":
        if bind_admin_id is not None:
            a = db.get(User, bind_admin_id)
            if not a or a.role not in ("admin", "super_admin"):
                raise ErrBadRequest("bind_admin_id 必须是一个管理员")
        else:
            bind_admin_id = operator.user_id  # 默认绑定到 super_admin 自己
    else:
        raise ErrForbidden("仅管理员可创建用户")
    body.bind_admin_id = bind_admin_id
    return register(db, body)


def admin_bind_user(db: Session, operator: User, user_id: int, admin_id: int | None):
    """super_admin 重新绑定用户的管理员; admin 只允许把绑定到自己的用户改绑给自己"""
    target = get_user_by_id(db, user_id)
    if target.role in ("admin", "super_admin"):
        raise ErrBadRequest("不能绑定管理员角色的账号")
    if operator.role == "admin":
        if target.bind_admin_id != operator.user_id:
            raise ErrForbidden("只能操作自己绑定的用户")
        if admin_id is not None and admin_id != operator.user_id:
            raise ErrForbidden("次级管理员只能绑定给自己")
    elif operator.role != "super_admin":
        raise ErrForbidden("无权限")
    target.bind_admin_id = admin_id
    db.commit()
    db.refresh(target)
    return target


def authenticate(db: Session, account: str, password: str) -> User:
    user = db.scalar(
        select(User).where((User.account == account) | (User.email == account))
    )
    if not user or not verify_password(password, user.password_hash):
        raise ErrUnauth("账号或密码错误")
    if not user.is_active:
        raise ErrUnauth("账号已被封禁")
    if not user.enabled:
        raise ErrUnauth("账号未启用")
    return user


def touch_last_active(db: Session, user_id: int) -> None:
    u = db.get(User, user_id)
    if u:
        u.last_active_at = utc_now()
        db.commit()


def is_online(u: User) -> bool:
    if not u.last_active_at:
        return False
    return (utc_now() - u.last_active_at.replace(tzinfo=None)).total_seconds() < ONLINE_WINDOW_SEC


def update_me(db: Session, user: User, body: UserUpdateMe) -> User:
    if body.new_password:
        if not body.old_password or not verify_password(body.old_password, user.password_hash):
            raise ErrBadRequest("原密码错误")
        user.password_hash = hash_password(body.new_password)
    if body.username is not None:
        user.username = body.username
    if body.email is not None:
        exists = db.scalar(select(User).where(User.email == body.email, User.user_id != user.user_id))
        if exists:
            raise ErrBadRequest("邮箱已被其他账号使用")
        user.email = body.email
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    # 个人资料扩展字段
    for field in ('title', 'company', 'department', 'location', 'phone', 'website', 'bio'):
        val = getattr(body, field, None)
        if val is not None:
            setattr(user, field, val)
    if body.birthday is not None:
        user.birthday = body.birthday
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session, viewer: User, keyword: str | None = None) -> list[User]:
    """
    按角色过滤可见用户:
      - super_admin: 看全部
      - admin:       只看自己绑定的用户 (bind_admin_id == self.user_id)
      - user:        无权查看列表 (由路由层依赖拦截,这里不处理)
    keyword: 按 username/account/email 模糊搜索
    """
    stmt = select(User)
    if viewer.role == "admin":
        stmt = stmt.where(User.bind_admin_id == viewer.user_id)
    # super_admin 不加 where => 全量
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(User.username.ilike(like), User.account.ilike(like), User.email.ilike(like)))
    return list(db.scalars(stmt.order_by(User.user_id.asc())).all())


def admin_delete_user(db: Session, operator: User, target_id: int) -> None:
    target = get_user_by_id(db, target_id)

    # 权限校验
    if operator.role == "admin":
        # 次级管理员只能删自己绑定的用户
        if target.bind_admin_id != operator.user_id or target.role != "user":
            raise ErrForbidden("次级管理员只能删除自己绑定的普通用户")
    elif operator.role == "super_admin":
        if target.role == "super_admin":
            raise ErrForbidden("不能删除超级管理员")
    else:
        raise ErrForbidden("无权限")

    db.delete(target)
    db.commit()


def admin_set_role(db: Session, operator: User, target_id: int, new_role: str) -> User:
    if new_role not in ("user", "admin", "super_admin"):
        raise ErrBadRequest("非法角色")
    target = get_user_by_id(db, target_id)
    if target.user_id == operator.user_id and new_role != operator.role:
        raise ErrForbidden("不能修改自己的角色，请联系其他超级管理员操作")
    if target.role == "super_admin" and target.user_id != operator.user_id:
        raise ErrForbidden("不能修改其他超级管理员")
    if new_role == "admin" and operator.role != "super_admin":
        raise ErrForbidden("仅超级管理员可任命次级管理员")
    if new_role == "super_admin" and operator.role != "super_admin":
        raise ErrForbidden("仅超级管理员可设置超级管理员")
    # 降为普通 user 时, 必须有至少一个其他 super_admin
    if target.role == "super_admin" and new_role != "super_admin":
        from sqlalchemy import func
        other = db.scalar(select(func.count(User.user_id)).where(User.role == "super_admin", User.user_id != target.user_id))
        if not other:
            raise ErrForbidden("至少需要保留一个超级管理员")
    target.role = new_role
    # 提升为 admin 时, 解除自己的绑定
    if new_role in ("admin", "super_admin"):
        target.bind_admin_id = None
    db.commit()
    db.refresh(target)
    return target


def admin_set_enabled(db: Session, operator: User, target_id: int, enabled: bool) -> User:
    """启用/禁用用户。禁用后用户不能登录、已有token后续请求被拒。"""
    target = get_user_by_id(db, target_id)
    if operator.role not in ("super_admin", "admin"):
        raise ErrForbidden("仅管理员可启用/禁用用户")
    if target.user_id == operator.user_id:
        raise ErrForbidden("不能修改自己的启用状态")
    if target.role == "super_admin":
        if operator.role != "super_admin":
            raise ErrForbidden("仅超级管理员可禁用超级管理员")
        if not enabled:
            # 保留至少一个启用的超管
            from sqlalchemy import func
            other = db.scalar(select(func.count(User.user_id)).where(
                User.role == "super_admin", User.user_id != target.user_id, User.enabled.is_(True)
            ))
            if not other:
                raise ErrForbidden("至少需要保留一个启用的超级管理员")
    if operator.role == "admin":
        # 次级管理员只能启用/禁用自己绑定的普通用户
        if target.bind_admin_id != operator.user_id or target.role != "user":
            raise ErrForbidden("次级管理员只能操作自己绑定的普通用户")
    target.enabled = enabled
    target.is_active = enabled
    db.commit()
    db.refresh(target)
    return target


# ============ 组织树 ============

def _get_subtree_ids(db: Session, root_id: int) -> set[int]:
    """递归获取 root_id 下级（含自己）所有 user_id。BFS 避免深递归。"""
    ids: set[int] = {root_id}
    frontier = [root_id]
    while frontier:
        nxt: list[int] = []
        for fid in frontier:
            children = db.scalars(select(User.user_id).where(User.manager_id == fid)).all()
            for c in children:
                if c not in ids:
                    ids.add(c); nxt.append(c)
        frontier = nxt
    return ids


def can_manage_user(db: Session, operator: User, target_id: int) -> bool:
    """operator 是否有权限管理 target_id 用户：
       - super_admin: 全部
       - admin: 只能管理自己子树里的人 (manager_id 链能走到自己)
       - user: 只能管理自己
    """
    if operator.role == "super_admin":
        return True
    if operator.user_id == target_id:
        return True
    if operator.role == "admin":
        subtree = _get_subtree_ids(db, operator.user_id)
        return target_id in subtree
    return False


def build_user_tree(db: Session, users: list[User]) -> list[UserTreeNode]:
    """把用户列表组装成 manager_id 为父节点的树结构（多根：所有无 manager_id 或 manager 不在列表中的用户作为根）。"""
    by_id: dict[int, User] = {u.user_id: u for u in users}
    children_map: dict[int, list[User]] = {}
    roots: list[User] = []
    for u in users:
        if u.manager_id is not None and u.manager_id in by_id and u.manager_id != u.user_id:
            children_map.setdefault(u.manager_id, []).append(u)
        else:
            roots.append(u)

    def to_node(u: User) -> UserTreeNode:
        kids = sorted(children_map.get(u.user_id, []), key=lambda x: (x.role != 'super_admin', x.role != 'admin', x.username))
        return UserTreeNode.model_validate(u, from_attributes=True).model_copy(update={
            "children": [to_node(c) for c in kids],
        })

    roots.sort(key=lambda x: (x.role != 'super_admin', x.role != 'admin', x.username))
    return [to_node(r) for r in roots]


def list_users_tree(db: Session, viewer: User, keyword: str | None = None) -> list[UserTreeNode]:
    """
    返回 viewer 可见范围内的组织树:
      - super_admin: 全公司树（所有用户）
      - admin: 以自己为根的子树
      - user: 只能看到自己
    """
    stmt = select(User)
    if viewer.role == "super_admin":
        pass  # 全量
    elif viewer.role == "admin":
        subtree = _get_subtree_ids(db, viewer.user_id)
        stmt = stmt.where(User.user_id.in_(subtree))
    else:
        stmt = stmt.where(User.user_id == viewer.user_id)

    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(User.username.ilike(like), User.account.ilike(like), User.email.ilike(like),
                              User.title.ilike(like), User.department.ilike(like)))
    users = list(db.scalars(stmt).all())
    # 对于非超管且关键词搜索，需要把命中的上级链也加入结果，否则树不完整
    if keyword and viewer.role != "super_admin":
        # 把所有命中节点的上级链（直到 viewer）补全
        need_ids: set[int] = set()
        for u in users:
            cur = u
            while cur and cur.manager_id and cur.user_id != viewer.user_id:
                parent = db.get(User, cur.manager_id)
                if not parent: break
                need_ids.add(parent.user_id)
                cur = parent
        if need_ids:
            extra = list(db.scalars(select(User).where(User.user_id.in_(need_ids))).all())
            existing = {u.user_id for u in users}
            for u in extra:
                if u.user_id not in existing:
                    users.append(u)
    return build_user_tree(db, users)


# ============ 管理员增删改 ============

def admin_create_user_v2(db: Session, operator: User, body: UserCreate) -> User:
    """新版创建用户（支持 manager_id/department/title）。
    - super_admin 可指定任意 manager_id（包括 admin/super_admin）
    - admin 创建的用户 manager_id 必须是自己或自己子树中的 admin
    - user 无权
    """
    if operator.role not in ("super_admin", "admin"):
        raise ErrForbidden("仅管理员可创建用户")

    exists = db.scalar(
        select(User).where((User.account == body.account) | (User.email == body.email))
    )
    if exists:
        raise ErrBadRequest("账号或邮箱已存在")

    manager_id = body.manager_id
    if manager_id is None:
        # 默认挂在 operator 自己下面
        manager_id = operator.user_id
    else:
        mgr = db.get(User, manager_id)
        if not mgr:
            raise ErrBadRequest("指定的上级不存在")
        # 权限校验: admin 只能挂到自己或自己子树下的 admin/user
        if operator.role == "admin":
            subtree = _get_subtree_ids(db, operator.user_id)
            if manager_id not in subtree:
                raise ErrForbidden("不能把用户挂到你管理范围之外的上级名下")
        # 不能挂到 user 角色下面（user 没有管理权限）
        if mgr.role == "user":
            raise ErrBadRequest("上级必须是管理员角色或超级管理员")

    # 角色约束：admin 不能创建 admin/super_admin
    role = body.role
    if operator.role == "admin" and role != "user":
        raise ErrForbidden("次级管理员只能创建普通用户")

    user = User(
        username=body.username,
        account=body.account,
        email=body.email,
        password_hash=hash_password(body.password),
        role=role,
        manager_id=manager_id,
        department=body.department or "",
        title=body.title or "",
        bind_admin_id=operator.user_id if operator.role == "admin" else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def admin_update_user(db: Session, operator: User, target_id: int, body: UserUpdate) -> User:
    """管理员修改用户。manager_id 变更会做环路检测与权限校验。"""
    target = get_user_by_id(db, target_id)

    # 权限范围校验
    if operator.role != "super_admin":
        if operator.user_id == target_id:
            # 自己改自己：只能改基础字段（不能改自己的 role/enabled/manager_id）
            if body.role is not None or body.enabled is not None or body.manager_id is not None:
                raise ErrForbidden("不能修改自己的角色、启用状态或上级")
        elif not can_manage_user(db, operator, target_id):
            raise ErrForbidden("无权操作该用户")

    # 角色变更
    if body.role is not None and body.role != target.role:
        if body.role not in ("user", "admin"):
            raise ErrBadRequest("只能设置 admin 或 user 角色")
        if operator.role != "super_admin":
            raise ErrForbidden("仅超级管理员可调整角色")
        if target.role == "super_admin":
            raise ErrForbidden("不能修改其他超级管理员的角色")
        target.role = body.role
        if body.role == "admin":
            target.bind_admin_id = None

    # 启用状态
    if body.enabled is not None and body.enabled != target.enabled:
        if target.user_id == operator.user_id:
            raise ErrForbidden("不能修改自己的启用状态")
        if target.role == "super_admin" and operator.role != "super_admin":
            raise ErrForbidden("不能操作超级管理员")
        target.enabled = body.enabled
        target.is_active = body.enabled

    # manager_id 变更（重挂节点）
    if body.manager_id is not None and body.manager_id != target.manager_id:
        new_mid = body.manager_id
        if new_mid == target.user_id:
            raise ErrBadRequest("不能把自己设为自己的上级")
        if new_mid is not None:
            mgr = db.get(User, new_mid)
            if not mgr: raise ErrBadRequest("指定的上级不存在")
            if mgr.role == "user": raise ErrBadRequest("上级必须是管理员或超级管理员")
            # 环路检测: new_mgr 的祖先链不能包含 target
            ancestor = mgr
            seen = set()
            while ancestor and ancestor.manager_id:
                if ancestor.user_id == target.user_id:
                    raise ErrBadRequest("不能形成环路：目标上级在当前用户的下级链中")
                if ancestor.user_id in seen: break
                seen.add(ancestor.user_id)
                ancestor = db.get(User, ancestor.manager_id) if ancestor.manager_id else None
            # admin 权限：只能挂到自己子树内
            if operator.role == "admin":
                subtree = _get_subtree_ids(db, operator.user_id)
                if new_mid not in subtree:
                    raise ErrForbidden("不能把用户挂到你管理范围之外")
        target.manager_id = new_mid

    # 密码重置
    if body.password:
        target.password_hash = hash_password(body.password)

    # 文本字段
    for field in ('username', 'department', 'title'):
        val = getattr(body, field, None)
        if val is not None:
            setattr(target, field, val)
    if body.email is not None:
        exists = db.scalar(select(User).where(User.email == body.email, User.user_id != target.user_id))
        if exists: raise ErrBadRequest("邮箱已被使用")
        target.email = body.email

    db.commit()
    db.refresh(target)
    return target
