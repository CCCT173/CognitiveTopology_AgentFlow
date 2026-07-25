"""ReActRunner: 思考-行动-观察循环
与 SimpleRunner 区别:
- 允许多轮工具调用(最多 agent.max_iterations 次)
- system prompt 引导 LLM 按 ReAct 格式思考
- 每轮 step 记录到 RunResult.steps
"""
import json
from app.services.agent_runtime.base import BaseRunner, AgentContext, RunResult, collect_tools, msg_to_dict
from app.services.llm import build_chat_kwargs, build_chat_kwargs_async


REACT_SYSTEM = """你是一个会使用工具的AI助手,按照 ReAct(思考-行动-观察) 模式工作。

工作流程:
1. Thought: 思考要做什么,分析用户需求
2. Action: 调用合适的工具(可选,若不需要工具直接回答)
3. Observation: 查看工具返回结果
4. 重复 1-3 直到能给出最终答案
5. Final Answer: 用自然语言给出最终回答

规则:
- 如果已有足够信息回答,直接给出答案,不要强行调用工具
- 每次只调用必要的工具,不要反复调用同一个工具
- 严格基于工具返回的事实回答,不要编造
- 最终答案用中文回答,清晰易读
"""


def _build_messages(ctx: AgentContext) -> list[dict]:
    system = (ctx.agent.system_prompt or "") + "\n\n" + REACT_SYSTEM
    messages = [{"role": "system", "content": system.strip()}]
    for m in ctx.history[-10:]:
        if m["role"] in ("user", "assistant"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": ctx.message})
    return messages


def _call_kwargs(model: str, kwargs: dict, openai_tools, stream: bool) -> dict:
    k = {"model": model, **kwargs}
    k["stream"] = bool(stream)
    if openai_tools:
        k["tools"] = openai_tools
        k["tool_choice"] = "auto"
    if k.get("max_tokens") is None:
        k.pop("max_tokens", None)
    return k


class ReActRunner(BaseRunner):
    architecture = "react"

    def run(self, ctx: AgentContext) -> RunResult:
        client, model, kwargs = build_chat_kwargs(ctx.agent)
        openai_tools, tool_map = collect_tools(ctx)

        max_iter = int(getattr(ctx.agent, "max_iterations", 10) or 10)
        messages = _build_messages(ctx)

        steps = []
        last_reply = ""

        for i in range(max_iter):
            call_kw = _call_kwargs(model, kwargs, openai_tools, stream=False)
            call_kw["messages"] = messages
            resp = client.chat.completions.create(**call_kw)
            msg = resp.choices[0].message

            if not msg.tool_calls:
                last_reply = (msg.content or "").strip()
                messages.append({"role": "assistant", "content": msg.content or ""})
                break

            messages.append(msg_to_dict(msg))
            step_calls = []
            for tc in msg.tool_calls:
                fn = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                tool = tool_map.get(fn)
                if not tool:
                    result = f"[未知工具 {fn}]"
                else:
                    try:
                        result = tool.run(ctx, **args)
                    except Exception as e:
                        result = f"[工具调用失败: {e}]"
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)[:8000]})
                step_calls.append({"tool": fn, "args": args, "result": str(result)[:2000]})
            steps.append({"iter": i + 1, "tool_calls": step_calls})
        else:
            last_reply = "抱歉,我在规定步数内没能完成任务。请尝试更明确的问题,或增加 max_iterations。"

        return RunResult(reply=last_reply, tool_calls=[c for s in steps for c in s["tool_calls"]], steps=steps, citations=list(getattr(ctx, "citations", []) or []))

    async def async_run(self, ctx: AgentContext) -> RunResult:
        """异步执行 ReAct 循环，使用 AsyncOpenAI 客户端"""
        client, model, kwargs = build_chat_kwargs_async(ctx.agent)
        openai_tools, tool_map = collect_tools(ctx)

        max_iter = int(getattr(ctx.agent, "max_iterations", 10) or 10)
        messages = _build_messages(ctx)

        steps = []
        last_reply = ""

        for i in range(max_iter):
            call_kw = _call_kwargs(model, kwargs, openai_tools, stream=False)
            call_kw["messages"] = messages
            # 使用 await 调用异步客户端
            resp = await client.chat.completions.create(**call_kw)
            msg = resp.choices[0].message

            if not msg.tool_calls:
                last_reply = (msg.content or "").strip()
                messages.append({"role": "assistant", "content": msg.content or ""})
                break

            messages.append(msg_to_dict(msg))
            step_calls = []
            for tc in msg.tool_calls:
                fn = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                tool = tool_map.get(fn)
                if not tool:
                    result = f"[未知工具 {fn}]"
                else:
                    try:
                        result = tool.run(ctx, **args)
                    except Exception as e:
                        result = f"[工具调用失败: {e}]"
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)[:8000]})
                step_calls.append({"tool": fn, "args": args, "result": str(result)[:2000]})
            steps.append({"iter": i + 1, "tool_calls": step_calls})
        else:
            last_reply = "抱歉,我在规定步数内没能完成任务。请尝试更明确的问题,或增加 max_iterations。"

        return RunResult(reply=last_reply, tool_calls=[c for s in steps for c in s["tool_calls"]], steps=steps, citations=list(getattr(ctx, "citations", []) or []))

    # ------------------------------------------------------------------
    # 流式入口
    # ------------------------------------------------------------------
    def run_stream(self, ctx: AgentContext):
        client, model, kwargs = build_chat_kwargs(ctx.agent)
        openai_tools, tool_map = collect_tools(ctx)

        max_iter = int(getattr(ctx.agent, "max_iterations", 10) or 10)
        messages = _build_messages(ctx)

        steps = []
        all_tool_calls = []
        thinking_all = ""
        final_reply = ""

        for i in range(max_iter):
            iter_no = i + 1
            call_kw = _call_kwargs(model, kwargs, openai_tools, stream=True)
            call_kw["messages"] = messages

            # 通知前端：新一轮开始
            yield {"type": "iter_start", "data": {"iter": iter_no}}

            stream = client.chat.completions.create(**call_kw)
            tool_calls_acc: list[dict] = []
            content_acc = ""
            thinking_iter = ""

            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
                if reasoning:
                    thinking_iter += reasoning
                    thinking_all += reasoning
                    yield {"type": "thinking", "data": {"delta": reasoning, "iter": iter_no}}
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        while len(tool_calls_acc) <= idx:
                            tool_calls_acc.append({"id": "", "type": "function",
                                                    "function": {"name": "", "arguments": ""}})
                        slot = tool_calls_acc[idx]
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function.name:
                            slot["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            slot["function"]["arguments"] += tc.function.arguments
                if delta.content:
                    content_acc += delta.content

            if not tool_calls_acc:
                # 没有工具调用,这一轮就是最终回答,需要把内容流式吐出来
                # 上面的循环只累积了 content,没有 yield(因为可能 tool_call)
                # 由于我们无法预知是否 tool_call,这里直接 yield 整块内容
                if content_acc:
                    yield {"type": "delta", "data": {"delta": content_acc, "iter": iter_no}}
                final_reply = content_acc
                messages.append({"role": "assistant", "content": content_acc})
                yield {"type": "iter_end", "data": {"iter": iter_no}}
                break

            # 有工具调用
            messages.append({"role": "assistant", "content": content_acc or None,
                             "tool_calls": tool_calls_acc})
            step_calls = []
            for tc in tool_calls_acc:
                fn = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except Exception:
                    args = {}
                tool = tool_map.get(fn)
                if not tool:
                    result = f"[未知工具 {fn}]"
                else:
                    try:
                        result = tool.run(ctx, **args)
                    except Exception as e:
                        result = f"[工具调用失败: {e}]"
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)[:8000]})
                rec = {"tool": fn, "args": args, "result": str(result)[:2000], "iter": iter_no}
                step_calls.append(rec)
                all_tool_calls.append(rec)
                yield {"type": "tool", "data": rec}
            step = {"iter": iter_no, "tool_calls": step_calls}
            steps.append(step)
            yield {"type": "step", "data": step}
            yield {"type": "iter_end", "data": {"iter": iter_no}}
        else:
            final_reply = "抱歉,我在规定步数内没能完成任务。请尝试更明确的问题,或增加 max_iterations。"
            yield {"type": "delta", "data": {"delta": final_reply, "iter": max_iter + 1}}

        yield {"type": "done", "data": {
            "reply": final_reply.strip(),
            "thinking": thinking_all,
            "tool_calls": all_tool_calls,
            "steps": steps,
            "citations": list(getattr(ctx, "citations", []) or []),
        }}
