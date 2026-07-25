"""SimpleRunner: 单 Agent
- 一次 LLM 调用,支持 function_calling(0~1 轮工具)
- 若 agent.rag_kb_ids 非空,自动注入 rag_search 工具
- 若 LLM 返回 tool_calls,执行后再调一次 LLM 得到最终回答
- 非流式模式: 返回完整结果(RunResult)
- 流式模式: 通过 ctx.on_event 回调逐块吐出 (thinking/delta/tool/step/done)
"""
import json
from app.services.agent_runtime.base import BaseRunner, AgentContext, RunResult, collect_tools, msg_to_dict
from app.services.llm import build_chat_kwargs, build_chat_kwargs_async


def _build_messages(ctx: AgentContext) -> list[dict]:
    system = ctx.agent.system_prompt or "你是一个AI助手,请回答用户问题。"
    messages = [{"role": "system", "content": system}]
    for m in ctx.history[-10:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": ctx.message})
    return messages


def _call_kwargs(model: str, kwargs: dict, openai_tools, stream: bool) -> dict:
    """拼装 chat.completions.create 的参数"""
    k = {"model": model, **kwargs}
    # stream 由 runner 控制,这里把默认值按请求传入
    k["stream"] = bool(stream)
    if openai_tools:
        k["tools"] = openai_tools
        k["tool_choice"] = "auto"
    # max_tokens = None 时不传
    if k.get("max_tokens") is None:
        k.pop("max_tokens", None)
    return k


class SimpleRunner(BaseRunner):
    architecture = "single"

    # ------------------------------------------------------------------
    # 非流式入口 (旧 run())
    # ------------------------------------------------------------------
    def run(self, ctx: AgentContext) -> RunResult:
        client, model, kwargs = build_chat_kwargs(ctx.agent)
        openai_tools, tool_map = collect_tools(ctx)
        messages = _build_messages(ctx)

        call_kw = _call_kwargs(model, kwargs, openai_tools, stream=False)
        call_kw["messages"] = messages
        resp = client.chat.completions.create(**call_kw)
        msg = resp.choices[0].message

        tool_calls_record = []
        thinking_text = ""

        if msg.tool_calls:
            messages.append(msg_to_dict(msg))
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
                tool_calls_record.append({"tool": fn, "args": args, "result": str(result)[:2000]})

            call_kw2 = _call_kwargs(model, kwargs, None, stream=False)
            call_kw2["messages"] = messages
            resp2 = client.chat.completions.create(**call_kw2)
            final_msg = resp2.choices[0].message
            reply = (final_msg.content or "").strip()
        else:
            reply = (msg.content or "").strip()

        return RunResult(reply=reply, tool_calls=tool_calls_record, steps=[], citations=list(getattr(ctx, "citations", []) or []))

    async def async_run(self, ctx: AgentContext) -> RunResult:
        """异步执行，使用 AsyncOpenAI 客户端"""
        client, model, kwargs = build_chat_kwargs_async(ctx.agent)
        openai_tools, tool_map = collect_tools(ctx)
        messages = _build_messages(ctx)

        call_kw = _call_kwargs(model, kwargs, openai_tools, stream=False)
        call_kw["messages"] = messages
        # 使用 await 调用异步客户端
        resp = await client.chat.completions.create(**call_kw)
        msg = resp.choices[0].message

        tool_calls_record = []
        thinking_text = ""

        if msg.tool_calls:
            messages.append(msg_to_dict(msg))
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
                tool_calls_record.append({"tool": fn, "args": args, "result": str(result)[:2000]})

            call_kw2 = _call_kwargs(model, kwargs, None, stream=False)
            call_kw2["messages"] = messages
            resp2 = await client.chat.completions.create(**call_kw2)
            final_msg = resp2.choices[0].message
            reply = (final_msg.content or "").strip()
        else:
            reply = (msg.content or "").strip()

        return RunResult(reply=reply, tool_calls=tool_calls_record, steps=[], citations=list(getattr(ctx, "citations", []) or []))

    # ------------------------------------------------------------------
    # 流式入口
    # ------------------------------------------------------------------
    def run_stream(self, ctx: AgentContext):
        """生成器, 按事件 yield dict:
        {"type":"thinking"|"delta"|"tool"|"done","data":{...}}
        """
        client, model, kwargs = build_chat_kwargs(ctx.agent)
        openai_tools, tool_map = collect_tools(ctx)
        messages = _build_messages(ctx)

        call_kw = _call_kwargs(model, kwargs, openai_tools, stream=True)
        call_kw["messages"] = messages

        yield {"type": "iter_start", "data": {"iter": 1}}
        # ---- 第一轮 ----
        stream = client.chat.completions.create(**call_kw)
        first_msg_tool_calls: list[dict] = []   # 累积 tool_call
        first_content = ""
        thinking_buf = ""
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            # reasoning_content / reasoning 是 ARK/DeepSeek 思考字段
            reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
            if reasoning:
                thinking_buf += reasoning
                yield {"type": "thinking", "data": {"delta": reasoning, "iter": 1}}
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    # 累积 index
                    idx = tc.index
                    while len(first_msg_tool_calls) <= idx:
                        first_msg_tool_calls.append({"id": "", "type": "function",
                                                     "function": {"name": "", "arguments": ""}})
                    slot = first_msg_tool_calls[idx]
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function.name:
                        slot["function"]["name"] += tc.function.name
                    if tc.function.arguments:
                        slot["function"]["arguments"] += tc.function.arguments
            if delta.content:
                first_content += delta.content
                yield {"type": "delta", "data": {"delta": delta.content, "iter": 1}}

        tool_calls_record = []
        reply = first_content
        steps = []

        if first_msg_tool_calls:
            # 第一轮结束
            yield {"type": "iter_end", "data": {"iter": 1}}
            # 组装 assistant message
            assistant_msg = {"role": "assistant", "content": first_content or None,
                             "tool_calls": first_msg_tool_calls}
            messages.append(assistant_msg)

            for tc in first_msg_tool_calls:
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
                tool_record = {"tool": fn, "args": args, "result": str(result)[:2000], "iter": 1}
                tool_calls_record.append(tool_record)
                yield {"type": "tool", "data": tool_record}

            # ---- 第二轮: 生成最终回复 ----
            yield {"type": "iter_start", "data": {"iter": 2}}
            call_kw2 = _call_kwargs(model, kwargs, None, stream=True)
            call_kw2["messages"] = messages
            # 清掉之前的 content
            yield {"type": "delta", "data": {"delta": "", "iter": 2}}
            stream2 = client.chat.completions.create(**call_kw2)
            final_content = ""
            thinking_buf2 = ""
            for chunk in stream2:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
                if reasoning:
                    thinking_buf2 += reasoning
                    yield {"type": "thinking", "data": {"delta": reasoning, "iter": 2}}
                if delta.content:
                    final_content += delta.content
                    yield {"type": "delta", "data": {"delta": delta.content, "iter": 2}}
            reply = final_content
            thinking_buf = thinking_buf + thinking_buf2
            yield {"type": "iter_end", "data": {"iter": 2}}
        else:
            # 无工具调用，第一轮即是最终回复
            yield {"type": "iter_end", "data": {"iter": 1}}

        yield {"type": "done", "data": {
            "reply": reply.strip(),
            "thinking": thinking_buf,
            "tool_calls": tool_calls_record,
            "steps": steps,
            "citations": list(getattr(ctx, "citations", []) or []),
        }}
