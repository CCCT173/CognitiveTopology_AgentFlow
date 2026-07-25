"""
工作群组接口 (成员校验 + 群主转让 + 邀请成员)
  POST   /api/v1/groups                         建群(创建者自动成为群主)
  GET    /api/v1/groups                         我加入的群
  POST   /api/v1/groups/{id}/join               加入群
  POST   /api/v1/groups/{id}/leave              退群
  DELETE /api/v1/groups/{id}                    解散(群主)
  DELETE /api/v1/groups/{id}/members/{uid}      踢人(群主)
  POST   /api/v1/groups/{id}/members/{uid}      邀请成员(群主/群管理员)
  POST   /api/v1/groups/{id}/transfer/{uid}     转让群主
  GET    /api/v1/groups/{id}/members            成员列表(仅成员可见)
  POST   /api/v1/groups/{id}/agents/{agent_id}  共享自己的agent到群
  DELETE /api/v1/groups/{id}/agents/{agent_id}  取消共享
  GET    /api/v1/groups/{id}/agents             群内共享agent(仅成员)
  POST   /api/v1/groups/{id}/kbs/{kb_id}        共享知识库
  DELETE /api/v1/groups/{id}/kbs/{kb_id}        取消共享
  GET    /api/v1/groups/{id}/kbs                群内共享知识库(仅成员)
  GET    /api/v1/groups/{id}/messages           群聊消息(仅成员)
  POST   /api/v1/groups/{id}/messages           发消息(仅成员)
  DELETE /api/v1/groups/{id}/messages/{mid}     撤回消息
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, is_admin
from app.schemas.common import ok
from app.schemas.group import (
    GroupCreate, GroupOut, GroupMemberOut, GroupAgentOut, GroupKBOut,
    GroupMessageIn, GroupMessageOut, GroupNoticeIn, GroupNoticeOut,
)
from app.services import group_service, user_service
from app.core.security import get_current_user_required_enabled
from app.core.exceptions import ErrForbidden, ErrNotFound
from app.models.user import User

router = APIRouter(prefix="/groups", tags=["工作群组"])


def _require_member(db: Session, gid: int, user: User):
    if not is_admin(user) and not group_service._is_member(db, gid, user.user_id):
        raise ErrForbidden("仅群成员可访问")


@router.post("", summary="创建群组")
def create(body: GroupCreate, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    g = group_service.create_group(db, user, body)
    return ok(GroupOut(**{**GroupOut.model_validate(g).model_dump(), "member_count": 1}).model_dump())


@router.get("", summary="我加入的群")
def my_groups(user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    gs = group_service.list_my_groups(db, user)
    unread = group_service.unread_notice_count(db, user)
    return ok([GroupOut.model_validate(g).model_dump() | {"member_count": len(g.members), "unread_notices": unread.get(g.id, 0)} for g in gs])


@router.post("/{gid}/join", summary="加入群组")
def join(gid: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    group_service.join_group(db, user, gid)
    return ok(msg="已加入")


@router.post("/{gid}/leave", summary="退出群组")
def leave(gid: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    group_service.leave_group(db, user, gid)
    return ok(msg="已退出")


@router.delete("/{gid}", summary="解散群组(群主)")
def disband(gid: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    group_service.disband_group(db, user, gid)
    return ok(msg="已解散")


@router.delete("/{gid}/members/{uid}", summary="移除成员(群主)")
def kick(gid: int, uid: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    group_service.kick_member(db, user, gid, uid)
    return ok(msg="已移除")


@router.post("/{gid}/members/{uid}", summary="邀请成员加入(群主/管理员)")
def invite(gid: int, uid: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    group_service.invite_member(db, user, gid, uid)
    return ok(msg="已邀请")


@router.post("/{gid}/transfer/{uid}", summary="转让群主")
def transfer(gid: int, uid: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    group_service.transfer_ownership(db, user, gid, uid)
    return ok(msg="群主已转让")


@router.get("/{gid}/members", summary="群成员列表(含在线状态)")
def members(gid: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    _require_member(db, gid, user)
    return ok(group_service.list_members(db, gid))


@router.get("/{gid}/agents", summary="群内共享的Agent")
def agents(gid: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    _require_member(db, gid, user)
    return ok(group_service.list_group_agents(db, gid))


@router.post("/{gid}/agents/{agent_id}", summary="共享Agent到群")
def share_agent(gid: int, agent_id: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    group_service.share_agent(db, user, gid, agent_id)
    return ok(msg="已共享")


@router.delete("/{gid}/agents/{agent_id}", summary="取消共享Agent")
def unshare_agent(gid: int, agent_id: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    group_service.unshare_agent(db, user, gid, agent_id)
    return ok(msg="已取消共享")


@router.get("/{gid}/kbs", summary="群内共享的知识库")
def kbs(gid: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    _require_member(db, gid, user)
    return ok(group_service.list_group_kbs(db, gid))


@router.post("/{gid}/kbs/{kb_id}", summary="共享知识库到群")
def share_kb(gid: int, kb_id: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    group_service.share_kb(db, user, gid, kb_id)
    return ok(msg="已共享")


@router.delete("/{gid}/kbs/{kb_id}", summary="取消共享知识库")
def unshare_kb(gid: int, kb_id: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    group_service.unshare_kb(db, user, gid, kb_id)
    return ok(msg="已取消共享")


# ============ 共享工作流 ============
@router.get("/{gid}/workflows", summary="群内共享的工作流")
def workflows(gid: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    _require_member(db, gid, user)
    return ok(group_service.list_group_workflows(db, gid))


@router.post("/{gid}/workflows/{wf_id}", summary="共享工作流到群")
def share_workflow(gid: int, wf_id: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    group_service.share_workflow(db, user, gid, wf_id)
    return ok(msg="已共享")


@router.delete("/{gid}/workflows/{wf_id}", summary="取消共享工作流")
def unshare_workflow(gid: int, wf_id: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    group_service.unshare_workflow(db, user, gid, wf_id)
    return ok(msg="已取消共享")


# ============ 共享技能 ============
@router.get("/{gid}/skills", summary="群内共享的技能")
def skills(gid: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    _require_member(db, gid, user)
    return ok(group_service.list_group_skills(db, gid))


@router.post("/{gid}/skills/{sk_id}", summary="共享技能到群")
def share_skill(gid: int, sk_id: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    group_service.share_skill(db, user, gid, sk_id)
    return ok(msg="已共享")


@router.delete("/{gid}/skills/{sk_id}", summary="取消共享技能")
def unshare_skill(gid: int, sk_id: int, user: User = Depends(get_current_user_required_enabled), db: Session = Depends(get_db)):
    group_service.unshare_skill(db, user, gid, sk_id)
    return ok(msg="已取消共享")


# ============ 群聊消息 ============
@router.get("/{gid}/messages", summary="群聊消息列表(分页: before_id 游标,默认最新50条)")
def list_messages(
    gid: int,
    before_id: Optional[int] = Query(None, description="游标:返回id<此值的更早消息"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user_required_enabled),
    db: Session = Depends(get_db),
):
    _require_member(db, gid, user)
    return ok(group_service.list_messages(db, gid, before_id, limit))


@router.post("/{gid}/messages", summary="发消息(可传agent_name调用群内共享agent)")
def send_message(
    gid: int,
    body: GroupMessageIn,
    user: User = Depends(get_current_user_required_enabled),
    db: Session = Depends(get_db),
):
    msgs = group_service.send_message(db, gid, user, body)
    return ok(msgs, msg="发送成功")


@router.delete("/{gid}/messages/{mid}", summary="撤回消息(自己或群主)")
def delete_message(
    gid: int, mid: int,
    user: User = Depends(get_current_user_required_enabled),
    db: Session = Depends(get_db),
):
    group_service.delete_message(db, gid, mid, user)
    return ok(msg="已撤回")


# ============ 群公告 ============

@router.get("/{gid}/notices", summary="群公告列表")
def list_notices(
    gid: int,
    user: User = Depends(get_current_user_required_enabled),
    db: Session = Depends(get_db),
):
    notices = group_service.list_notices(db, gid, user)
    return ok(notices)


@router.post("/{gid}/notices", summary="发布群公告(群主)")
def create_notice(
    gid: int, body: GroupNoticeIn,
    user: User = Depends(get_current_user_required_enabled),
    db: Session = Depends(get_db),
):
    n = group_service.create_notice(db, gid, user, body)
    return ok(n, msg="已发布")


@router.post("/{gid}/notices/{nid}/read", summary="标记公告已读")
def mark_read(
    gid: int, nid: int,
    user: User = Depends(get_current_user_required_enabled),
    db: Session = Depends(get_db),
):
    group_service.mark_notice_read(db, gid, nid, user)
    return ok(msg="ok")


@router.post("/{gid}/notices/{nid}/pin", summary="置顶/取消置顶公告(群主)")
def toggle_pin(
    gid: int, nid: int, pin: bool = Query(True),
    user: User = Depends(get_current_user_required_enabled),
    db: Session = Depends(get_db),
):
    n = group_service.toggle_pin(db, gid, nid, pin, user)
    return ok(n, msg=f"已{'置顶' if pin else '取消置顶'}")


@router.delete("/{gid}/notices/{nid}", summary="删除公告(群主/作者)")
def delete_notice(
    gid: int, nid: int,
    user: User = Depends(get_current_user_required_enabled),
    db: Session = Depends(get_db),
):
    group_service.delete_notice(db, gid, nid, user)
    return ok(msg="已删除")
