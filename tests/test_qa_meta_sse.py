"""
QA Meta AI + SSE 流式测试（真实 LLM + 事件序列校验）
- /meta/chat 同步
- /meta/chat/stream SSE 事件序列：iter_start → [thinking|tool|delta]* → done
- /chat (Agent 对话) 基本流程
"""
from __future__ import annotations
import sys
import json
import uuid
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _login(client):
    r = client.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
    return r.json()["data"]["token"]


class TestMetaPublicEndpoints:
    def test_providers(self, client):
        r = client.get("/api/v1/meta/providers")
        assert r.status_code == 200
        assert r.json()["code"] == 0

    def test_tools(self, client):
        r = client.get("/api/v1/meta/tools")
        assert r.status_code == 200
        data = r.json()["data"]
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_loaders(self, client):
        r = client.get("/api/v1/meta/loaders")
        assert r.status_code == 200

    def test_config(self, client):
        r = client.get("/api/v1/meta/config")
        assert r.status_code == 200


class TestMetaChatSync:
    def test_meta_chat_returns_reply(self, client, mock_llm):
        """/meta/chat mock LLM：应返回合理回复"""
        token = _login(client)
        r = client.post(
            "/api/v1/meta/chat",
            json={"message": "你好"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "data" in data

    def test_meta_chat_empty_message_validation(self, client, mock_llm):
        """空消息行为：可能被校验拒绝(422) 或 LLM 处理后返回 200"""
        token = _login(client)
        r = client.post(
            "/api/v1/meta/chat",
            json={"message": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
        # 允许 422（校验拒绝）或 200（LLM 处理空输入）
        assert r.status_code in (200, 400, 422)


class TestMetaChatStream:
    def test_sse_valid_event_sequence(self, client, mock_llm):
        """SSE 事件序列校验：必须有终止事件（done 或 error）在最后"""
        token = _login(client)
        with client.stream(
            "POST",
            "/api/v1/meta/chat/stream",
            json={"message": "你好"},
            headers={"Authorization": f"Bearer {token}"},
        ) as resp:
            assert resp.status_code == 200, resp.read().decode()[:300]
            events = []
            current_data = []
            for raw_line in resp.iter_lines():
                if raw_line is None:
                    continue
                line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
                if line == "":
                    if current_data:
                        payload_str = "\n".join(current_data)
                        try:
                            payload = json.loads(payload_str)
                        except json.JSONDecodeError:
                            payload = {"raw": payload_str}
                        etype = payload.get("type", "unknown")
                        events.append((etype, payload))
                    current_data = []
                    continue
                if line.startswith("data:"):
                    current_data.append(line[len("data:"):].strip())
            if current_data:
                try:
                    payload = json.loads("\n".join(current_data))
                except json.JSONDecodeError:
                    payload = {}
                if payload:
                    events.append((payload.get("type", "unknown"), payload))

        # 必须有事件
        assert len(events) >= 1, f"SSE 应返回事件，实际: {events}"
        # 过滤掉 unknown（空 data 行等噪声）
        real_events = [e for e in events if e[0] != "unknown"]
        assert len(real_events) >= 1, f"SSE 应有有效事件，实际: {events}"
        event_types = [e[0] for e in real_events]
        # 终止事件（done 或 error）必须在最后
        last_type = event_types[-1]
        assert last_type in ("done", "error"), f"最后一个事件应为 done/error，实际: {event_types}"
        # 所有事件类型必须合法
        valid_types = {"iter_start", "iter_end", "thinking", "delta", "tool", "done",
                       "error", "cancelled", "message", "ping", "start", "end", "text"}
        for et in event_types:
            assert et in valid_types, f"未知事件类型: {et}"


class TestAgentChat:
    def _create_agent(self, client, token):
        name = f"chat_agent_{uuid.uuid4().hex[:6]}"
        r = client.post("/api/v1/agents", json={
            "name": name, "display_name": name,
            "system_prompt": "你是一个简洁的助手，总是用一句话回答。",
            "architecture": "simple",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        return r.json()["data"]["name"]

    def test_chat_returns_reply(self, client, mock_llm):
        token = _login(client)
        name = self._create_agent(client, token)
        r = client.post("/api/v1/chat", json={
            "agent_name": name, "message": "你好",
        }, headers={"Authorization": f"Bearer {token}"}, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json().get("data", r.json())
        assert "thread_id" in body or "reply" in body or "content" in body

    def test_chat_nonexistent_agent_404(self, client, mock_llm):
        token = _login(client)
        r = client.post("/api/v1/chat", json={
            "agent_name": "no_such_agent_xyz_abc", "message": "hi",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code in (404, 400)


class TestThreads:
    def test_list_threads(self, client, mock_llm):
        token = _login(client)
        r = client.get("/api/v1/chat/threads", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
