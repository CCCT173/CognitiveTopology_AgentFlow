"""群组业务逻辑"""
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, func

from app.models.group import Group, GroupMember, GroupAgent, GroupKB, GroupMessage, GroupNotice, GroupNoticeRead, GroupWorkflow, GroupSkill
from app.models.user import User
from app.models.agent import Agent as AgentModel
from app.models.rag import KnowledgeBase
from app.models.workflow import Workflow
from app.models.skill import Skill
from app.schemas.group import GroupCreate, GroupMessageIn, GroupNoticeIn
from app.core.exceptions import ErrNotFound, ErrForbidden, ErrBadRequest, ErrConflict
from app.services import user_service
from app.services.llm import get_chat_model
from app.core.logger import logger


def get_group(db: Session, gid: int) -> Group:
    g = db.get(Group, gid)
    if not g:
        raise ErrNotFound(f"群组 {gid} 不存在")
    return g


def _is_member(db: Session, gid: int, uid: int) -> bool:
    return db.get(GroupMember, (gid, uid)) is not None


def _is_owner(db: Session, gid: int, uid: int) -> bool:
    g = get_group(db, gid)
    return g.owner_id == uid


def create_group(db: Session, user: User, body: GroupCreate) -> Group:
    g = Group(name=body.name, description=body.description, owner_id=user.user_id)
    db.add(g)
    db.flush()
    db.add(GroupMember(group_id=g.id, user_id=user.user_id, role="owner"))
    db.commit()
    db.refresh(g)
    return g


def list_my_groups(db: Session, user: User) -> list[Group]:
    return list(db.scalars(
        select(Group).join(GroupMember, Group.id == GroupMember.group_id)
        .where(GroupMember.user_id == user.user_id)
    ).all())


def join_group(db: Session, user: User, gid: int) -> GroupMember:
    get_group(db, gid)
    if _is_member(db, gid, user.user_id):
        raise ErrConflict("已在群内")
    m = GroupMember(group_id=gid, user_id=user.user_id, role="member")
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def leave_group(db: Session, user: User, gid: int):
    g = get_group(db, gid)
    if g.owner_id == user.user_id:
        raise ErrBadRequest("群主不能退出, 请先解散或转让")
    m = db.get(GroupMember, (gid, user.user_id))
    if not m:
        raise ErrBadRequest("不在群内")
    db.delete(m)
    db.commit()


def kick_member(db: Session, owner: User, gid: int, uid: int):
    if not _is_owner(db, gid, owner.user_id):
        raise ErrForbidden("仅群主可踢人")
    if uid == owner.user_id:
        raise ErrBadRequest("不能踢自己")
    m = db.get(GroupMember, (gid, uid))
    if not m:
        raise ErrNotFound("该成员不在群内")
    db.delete(m)
    # 级联: 被踢成员共享的资源也移除
    db.execute(delete(GroupAgent).where(GroupAgent.group_id == gid, GroupAgent.shared_by == uid))
    db.execute(delete(GroupKB).where(GroupKB.group_id == gid, GroupKB.shared_by == uid))
    db.commit()


def invite_member(db: Session, operator: User, gid: int, uid: int):
    """群主邀请某用户直接入群 (不需要对方 join)"""
    g = get_group(db, gid)
    if g.owner_id != operator.user_id:
        raise ErrForbidden("仅群主可邀请成员")
    target = db.get(User, uid)
    if not target:
        raise ErrNotFound("用户不存在")
    if _is_member(db, gid, uid):
        raise ErrConflict("该用户已在群内")
    db.add(GroupMember(group_id=gid, user_id=uid, role="member"))
    db.commit()


def transfer_ownership(db: Session, operator: User, gid: int, uid: int):
    """转让群主"""
    g = get_group(db, gid)
    if g.owner_id != operator.user_id:
        raise ErrForbidden("仅群主可转让")
    if uid == operator.user_id:
        raise ErrBadRequest("不能转让给自己")
    target = db.get(GroupMember, (gid, uid))
    if not target:
        raise ErrNotFound("该成员不在群内")
    # 新旧群主角色调整
    target.role = "owner"
    old_owner = db.get(GroupMember, (gid, operator.user_id))
    if old_owner:
        old_owner.role = "member"
    g.owner_id = uid
    db.commit()


def disband_group(db: Session, owner: User, gid: int):
    if not _is_owner(db, gid, owner.user_id):
        raise ErrForbidden("仅群主可解散群组")
    db.delete(get_group(db, gid))
    db.commit()


# ---------- 成员列表(含在线) ----------
def list_members(db: Session, gid: int) -> list[dict]:
    get_group(db, gid)
    rows = db.scalars(
        select(GroupMember).where(GroupMember.group_id == gid)
    ).all()
    out = []
    for m in rows:
        u = db.get(User, m.user_id)
        if not u:
            continue
        out.append({
            "user_id": u.user_id,
            "username": u.username,
            "avatar_url": u.avatar_url,
            "role": m.role,
            "online": user_service.is_online(u),
            "last_active_at": u.last_active_at,
        })
    return out


# ---------- 共享 Agent ----------
def share_agent(db: Session, user: User, gid: int, agent_id: int):
    g = get_group(db, gid)
    if not _is_member(db, gid, user.user_id):
        raise ErrForbidden("仅群成员可共享")
    agent = db.get(AgentModel, agent_id)
    if not agent:
        raise ErrNotFound("Agent不存在")
    # 仅 owner 或 admin 可共享他人创建的资源; 普通成员只能共享自己创建的
    from app.api.deps import is_admin as _is_admin
    if agent.created_by != user.user_id and not _is_admin(user) and g.owner_id != user.user_id:
        raise ErrForbidden("只能共享自己创建的 Agent (群主/管理员除外)")
    if agent.id in [s.agent_id for s in db.scalars(select(GroupAgent).where(GroupAgent.group_id == gid)).all()]:
        raise ErrConflict("该Agent已在群内共享")
    db.add(GroupAgent(group_id=gid, agent_id=agent_id, shared_by=user.user_id))
    db.commit()


def unshare_agent(db: Session, user: User, gid: int, agent_id: int):
    if not _is_member(db, gid, user.user_id):
        raise ErrForbidden("仅群成员可取消共享")
    rel = db.get(GroupAgent, (gid, agent_id))
    if not rel:
        raise ErrNotFound("该Agent未被共享")
    # 共享者本人 或 群主可取消
    if rel.shared_by != user.user_id and not _is_owner(db, gid, user.user_id):
        raise ErrForbidden("只能取消自己共享的资源(群主例外)")
    db.delete(rel)
    db.commit()


def list_group_agents(db: Session, gid: int) -> list[dict]:
    get_group(db, gid)
    rows = db.scalars(select(GroupAgent).where(GroupAgent.group_id == gid)).all()
    out = []
    for r in rows:
        a = db.get(AgentModel, r.agent_id)
        if not a:
            continue
        out.append({
            "agent_id": a.id, "name": a.name, "description": a.description,
            "shared_by": r.shared_by,
        })
    return out


# ---------- 共享 KB ----------
def share_kb(db: Session, user: User, gid: int, kb_id: int):
    g = get_group(db, gid)
    if not _is_member(db, gid, user.user_id):
        raise ErrForbidden("仅群成员可共享")
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise ErrNotFound("知识库不存在")
    from app.api.deps import is_admin as _is_admin
    if kb.created_by != user.user_id and not _is_admin(user) and g.owner_id != user.user_id:
        raise ErrForbidden("只能共享自己创建的知识库 (群主/管理员除外)")
    if kb.id in [s.kb_id for s in db.scalars(select(GroupKB).where(GroupKB.group_id == gid)).all()]:
        raise ErrConflict("该知识库已在群内共享")
    db.add(GroupKB(group_id=gid, kb_id=kb_id, shared_by=user.user_id))
    db.commit()


def unshare_kb(db: Session, user: User, gid: int, kb_id: int):
    if not _is_member(db, gid, user.user_id):
        raise ErrForbidden("仅群成员可取消共享")
    rel = db.get(GroupKB, (gid, kb_id))
    if not rel:
        raise ErrNotFound("该知识库未被共享")
    if rel.shared_by != user.user_id and not _is_owner(db, gid, user.user_id):
        raise ErrForbidden("只能取消自己共享的资源(群主例外)")
    db.delete(rel)
    db.commit()


def list_group_kbs(db: Session, gid: int) -> list[dict]:
    get_group(db, gid)
    rows = db.scalars(select(GroupKB).where(GroupKB.group_id == gid)).all()
    out = []
    for r in rows:
        k = db.get(KnowledgeBase, r.kb_id)
        if not k:
            continue
        out.append({
            "kb_id": k.id, "name": k.name, "description": k.description,
            "shared_by": r.shared_by,
        })
    return out


# ---------- 共享工作流 ----------
def share_workflow(db: Session, user: User, gid: int, wf_id: int):
    g = get_group(db, gid)
    if not _is_member(db, gid, user.user_id):
        raise ErrForbidden("仅群成员可共享")
    wf = db.get(Workflow, wf_id)
    if not wf:
        raise ErrNotFound("工作流不存在")
    if wf.created_by != user.user_id and g.owner_id != user.user_id and user.role not in ("admin", "super_admin"):
        raise ErrForbidden("只能共享自己创建的工作流(群主/管理员除外)")
    exists = db.scalar(select(GroupWorkflow).where(GroupWorkflow.group_id == gid, GroupWorkflow.workflow_id == wf_id))
    if exists:
        raise ErrConflict("该工作流已在群内共享")
    db.add(GroupWorkflow(group_id=gid, workflow_id=wf_id, shared_by=user.user_id))
    db.commit()


def unshare_workflow(db: Session, user: User, gid: int, wf_id: int):
    if not _is_member(db, gid, user.user_id):
        raise ErrForbidden("仅群成员可操作")
    rel = db.get(GroupWorkflow, (gid, wf_id))
    if not rel:
        raise ErrNotFound("该工作流未被共享")
    if rel.shared_by != user.user_id and not _is_owner(db, gid, user.user_id):
        raise ErrForbidden("只能取消自己共享的资源(群主例外)")
    db.delete(rel); db.commit()


def list_group_workflows(db: Session, gid: int) -> list[dict]:
    get_group(db, gid)
    rows = db.scalars(select(GroupWorkflow).where(GroupWorkflow.group_id == gid)).all()
    out = []
    for r in rows:
        wf = db.get(Workflow, r.workflow_id)
        if not wf: continue
        out.append({"workflow_id": wf.id, "name": wf.name, "display_name": wf.display_name,
                    "description": wf.description, "category": wf.category, "shared_by": r.shared_by})
    return out


# ---------- 共享技能 ----------
def share_skill(db: Session, user: User, gid: int, skill_id: int):
    g = get_group(db, gid)
    if not _is_member(db, gid, user.user_id):
        raise ErrForbidden("仅群成员可共享")
    sk = db.get(Skill, skill_id)
    if not sk:
        raise ErrNotFound("技能不存在")
    if not sk.is_builtin and sk.created_by != user.user_id and g.owner_id != user.user_id and user.role not in ("admin", "super_admin"):
        raise ErrForbidden("只能共享自己创建的技能(群主/管理员除外)")
    exists = db.scalar(select(GroupSkill).where(GroupSkill.group_id == gid, GroupSkill.skill_id == skill_id))
    if exists:
        raise ErrConflict("该技能已在群内共享")
    db.add(GroupSkill(group_id=gid, skill_id=skill_id, shared_by=user.user_id))
    db.commit()


def unshare_skill(db: Session, user: User, gid: int, skill_id: int):
    if not _is_member(db, gid, user.user_id):
        raise ErrForbidden("仅群成员可操作")
    rel = db.get(GroupSkill, (gid, skill_id))
    if not rel:
        raise ErrNotFound("该技能未被共享")
    if rel.shared_by != user.user_id and not _is_owner(db, gid, user.user_id):
        raise ErrForbidden("只能取消自己共享的资源(群主例外)")
    db.delete(rel); db.commit()


def list_group_skills(db: Session, gid: int) -> list[dict]:
    get_group(db, gid)
    rows = db.scalars(select(GroupSkill).where(GroupSkill.group_id == gid)).all()
    out = []
    for r in rows:
        sk = db.get(Skill, r.skill_id)
        if not sk: continue
        out.append({"skill_id": sk.id, "name": sk.name,
                    "display_name": getattr(sk, "display_name", None) or sk.name,
                    "description": sk.description, "category": sk.category,
                    "is_builtin": sk.is_builtin, "shared_by": r.shared_by})
    return out


# ============ 群聊消息 ============
def list_messages(db: Session, gid: int, before_id: int | None = None, limit: int = 50) -> list[dict]:
    get_group(db, gid)
    stmt = select(GroupMessage).where(GroupMessage.group_id == gid)
    if before_id:
        stmt = stmt.where(GroupMessage.id < before_id)
    stmt = stmt.order_by(GroupMessage.id.desc()).limit(limit)
    msgs = list(db.scalars(stmt).all())
    msgs.reverse()

    # 拉用户信息
    user_ids = {m.user_id for m in msgs}
    users_map = {u.user_id: u for u in db.scalars(select(User).where(User.user_id.in_(user_ids))).all()} if user_ids else {}
    out = []
    for m in msgs:
        u = users_map.get(m.user_id)
        out.append({
            "id": m.id, "group_id": m.group_id,
            "user_id": m.user_id,
            "username": u.username if u else "",
            "avatar_url": u.avatar_url if u else "",
            "agent_id": m.agent_id, "content": m.content,
            "reply_to": m.reply_to, "bot": m.bot,
            "created_at": m.created_at,
        })
    return out


def send_message(db: Session, gid: int, sender: User, body: GroupMessageIn) -> list[dict]:
    """
    发送消息。
    - 不传 agent_name: 普通群消息, 返回 [user_msg_dict]
    - 传 agent_name: 先写入用户消息, 再调群内共享 agent 生成回复, 写入 bot 消息, 返回 [user_msg, bot_msg]
    """
    get_group(db, gid)
    if not _is_member(db, gid, sender.user_id):
        raise ErrForbidden("仅群成员可发言")
    if not body.content.strip():
        raise ErrBadRequest("消息不能为空")

    result = []
    # 1) 用户消息
    msg = GroupMessage(
        group_id=gid, user_id=sender.user_id,
        content=body.content.strip(), reply_to=body.reply_to, bot=False,
    )
    db.add(msg)
    db.flush()
    result.append(_msg_to_dict(db, msg))

    # 2) Agent 回复
    if body.agent_name:
        # 找 agent 且必须在群内共享
        agent = db.scalar(select(AgentModel).where(AgentModel.name == body.agent_name))
        if not agent:
            raise ErrNotFound(f"Agent {body.agent_name} 不存在")
        shared = db.get(GroupAgent, (gid, agent.id))
        if not shared:
            raise ErrBadRequest(f"Agent {body.agent_name} 未在本群共享")
        try:
            llm = get_chat_model()
            system = agent.system_prompt or "你是群聊助手,请简短回答。"
            # 取最近 10 条上下文
            recent = list_messages(db, gid, limit=10)
            history = "\n".join(f"{m['username']}{'[bot]' if m['bot'] else ''}: {m['content']}" for m in recent)
            prompt = f"{history}\n{sender.username}: {body.content}\n{agent.display_name or agent.name}:"
            resp = llm.invoke([("system", system), ("user", prompt)])
            reply_text = (resp.content or "").strip()
            bot_msg = GroupMessage(
                group_id=gid, user_id=sender.user_id, agent_id=agent.id,
                content=reply_text, reply_to=msg.id, bot=True,
            )
            db.add(bot_msg)
            db.flush()
            result.append(_msg_to_dict(db, bot_msg))
        except Exception as e:
            logger.warning(f"群聊 Agent 回复失败: {e}")
            err_msg = GroupMessage(
                group_id=gid, user_id=sender.user_id, agent_id=agent.id,
                content=f"[Agent 回复失败: {e}]", reply_to=msg.id, bot=True,
            )
            db.add(err_msg)
            db.flush()
            result.append(_msg_to_dict(db, err_msg))

    db.commit()
    for d in result:
        m = db.get(GroupMessage, d["id"])
        if m:
            d["created_at"] = m.created_at
    return result


def delete_message(db: Session, gid: int, msg_id: int, operator: User):
    msg = db.get(GroupMessage, msg_id)
    if not msg or msg.group_id != gid:
        raise ErrNotFound("消息不存在")
    is_owner = _is_owner(db, gid, operator.user_id)
    if msg.user_id != operator.user_id and not is_owner:
        raise ErrForbidden("只能撤回自己的消息或群主撤回任意消息")
    db.delete(msg)
    db.commit()


def _msg_to_dict(db: Session, m: GroupMessage) -> dict:
    u = db.get(User, m.user_id)
    return {
        "id": m.id, "group_id": m.group_id,
        "user_id": m.user_id,
        "username": u.username if u else "",
        "avatar_url": u.avatar_url if u else "",
        "agent_id": m.agent_id, "content": m.content,
        "reply_to": m.reply_to, "bot": m.bot,
        "created_at": m.created_at,
    }


# ============ 群组公告 ============

def list_notices(db: Session, gid: int, viewer: User) -> list[dict]:
    """列出群公告: 置顶优先, 然后按时间倒序。带 is_read 和 read_count。"""
    if not _is_member(db, gid, viewer.user_id):
        raise ErrForbidden("不是群成员")
    notices = db.scalars(
        select(GroupNotice)
        .where(GroupNotice.group_id == gid)
        .order_by(GroupNotice.pinned.desc(), GroupNotice.created_at.desc())
    ).all()
    # 批量查作者信息
    author_ids = {n.author_id for n in notices}
    authors = {uid: db.get(User, uid) for uid in author_ids}
    # 批量查已读数量
    notice_ids = [n.id for n in notices]
    read_counts = dict()
    if notice_ids:
        rows = db.execute(
            select(GroupNoticeRead.notice_id, func.count(GroupNoticeRead.user_id))
            .where(GroupNoticeRead.notice_id.in_(notice_ids))
            .group_by(GroupNoticeRead.notice_id)
        ).all()
        read_counts = {rid: cnt for rid, cnt in rows}
    # 已读集合 (viewer)
    my_reads = set()
    if notice_ids:
        my_reads = set(db.scalars(
            select(GroupNoticeRead.notice_id).where(
                GroupNoticeRead.notice_id.in_(notice_ids),
                GroupNoticeRead.user_id == viewer.user_id,
            )
        ).all())
    out = []
    for n in notices:
        a = authors.get(n.author_id)
        out.append({
            "id": n.id, "group_id": n.group_id, "author_id": n.author_id,
            "author_name": a.username if a else "",
            "author_avatar": a.avatar_url if a else "",
            "title": n.title, "content": n.content, "pinned": n.pinned,
            "created_at": n.created_at, "updated_at": n.updated_at,
            "read_count": read_counts.get(n.id, 0),
            "is_read": n.id in my_reads,
        })
    return out


def create_notice(db: Session, gid: int, author: User, body: GroupNoticeIn) -> dict:
    """群主/管理员可发公告。"""
    if not _is_member(db, gid, author.user_id):
        raise ErrForbidden("不是群成员")
    g = get_group(db, gid)
    # 仅 owner 或群内 role=admin 可发（简化: owner 即可）
    if g.owner_id != author.user_id:
        # 允许群内任何成员发布？保守起见仅 owner
        raise ErrForbidden("仅群主可发布公告")
    n = GroupNotice(
        group_id=gid, author_id=author.user_id,
        title=body.title or "", content=body.content,
        pinned=body.pinned,
    )
    db.add(n); db.commit(); db.refresh(n)
    return {
        "id": n.id, "group_id": n.group_id, "author_id": n.author_id,
        "author_name": author.username, "author_avatar": author.avatar_url,
        "title": n.title, "content": n.content, "pinned": n.pinned,
        "created_at": n.created_at, "updated_at": n.updated_at,
        "read_count": 0, "is_read": True,
    }


def delete_notice(db: Session, gid: int, nid: int, operator: User) -> None:
    g = get_group(db, gid)
    n = db.get(GroupNotice, nid)
    if not n or n.group_id != gid:
        raise ErrNotFound("公告不存在")
    if g.owner_id != operator.user_id and n.author_id != operator.user_id:
        raise ErrForbidden("仅群主或作者可删除")
    db.delete(n); db.commit()


def mark_notice_read(db: Session, gid: int, nid: int, viewer: User) -> None:
    if not _is_member(db, gid, viewer.user_id):
        raise ErrForbidden("不是群成员")
    n = db.get(GroupNotice, nid)
    if not n or n.group_id != gid:
        raise ErrNotFound("公告不存在")
    exists = db.scalar(select(GroupNoticeRead).where(
        GroupNoticeRead.notice_id == nid, GroupNoticeRead.user_id == viewer.user_id))
    if not exists:
        db.add(GroupNoticeRead(notice_id=nid, user_id=viewer.user_id))
        db.commit()


def toggle_pin(db: Session, gid: int, nid: int, pin: bool, operator: User) -> dict:
    g = get_group(db, gid)
    if g.owner_id != operator.user_id:
        raise ErrForbidden("仅群主可置顶")
    n = db.get(GroupNotice, nid)
    if not n or n.group_id != gid:
        raise ErrNotFound("公告不存在")
    n.pinned = pin; db.commit(); db.refresh(n)
    a = db.get(User, n.author_id)
    return {
        "id": n.id, "group_id": n.group_id, "author_id": n.author_id,
        "author_name": a.username if a else "", "author_avatar": a.avatar_url if a else "",
        "title": n.title, "content": n.content, "pinned": n.pinned,
        "created_at": n.created_at, "updated_at": n.updated_at,
    }


def unread_notice_count(db: Session, user: User) -> dict[int, int]:
    """返回 {group_id: 未读数}，用于群组列表角标。"""
    from sqlalchemy import exists
    groups = list_my_groups(db, user)
    out: dict[int, int] = {}
    for g in groups:
        # 该群中 user 未读的公告数 = notices - reads
        stmt = select(func.count(GroupNotice.id)).where(
            GroupNotice.group_id == g.id,
            ~exists().where(GroupNoticeRead.notice_id == GroupNotice.id,
                            GroupNoticeRead.user_id == user.user_id),
        )
        out[g.id] = db.scalar(stmt) or 0
    return out
