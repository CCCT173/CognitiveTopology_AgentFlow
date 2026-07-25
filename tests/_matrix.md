# agentflow 接口测试矩阵 (QA 阶段)

> 范围：130+ REST 端点 + 安全层 + SSE 流式 + 沙箱
> 方法：等价类 / 状态迁移 / 错误注入 / 并发
> 约定：✅ 正向 | ❌ 负向 | ⚠️ 边界 | ⚡ 并发 | 🔒 安全

## 一、认证模块 `/api/v1/auth`

| 端点 | 正向 | 负向 | 边界 | 并发 | 安全 |
|------|------|------|------|------|------|
| POST /register | ✅ 新账号注册成功 | ❌ 重复 account→409；弱密码→422 | ⚠️ 密码=最小长度 6 | ⚡ 并发注册同 account→仅一成 | 🔒 SQL 注入 account 字段被参数化 |
| POST /login | ✅ admin/admin123→200+token | ❌ 错密码→401；禁用用户→403 | ⚠️ 错误 5 次→限流 | ⚡ 并发登录同账号不冲突 | 🔒 暴力破解触发 rate limit（5 次/10min） |
| POST /refresh | ✅ 用 refresh token 换新 access | ❌ 旧 refresh 重用→全量撤销 | ⚠️ 过期 refresh→401 | ⚡ 并发 refresh 仅一次成功 | 🔒 refresh rotation + 撤销链 |
| POST /logout | ✅ 撤销当前 refresh | ❌ 无 token→401 | — | — | — |
| GET /me | ✅ 返回当前用户 | ❌ 无 JWT→401；伪造 JWT→401 | ⚠️ 过期 JWT→401 | — | 🔒 JWT 签名校验 |
| POST /ping | ✅ 更新在线状态 | ❌ 无 JWT→401 | — | — | — |
| PATCH /me | ✅ 修改 username/password | ❌ 旧密码错→400 | ⚠️ 空 body→200(无字段更新) | — | — |
| POST /me/avatar | ✅ 上传图片→200 | ❌ 非图片文件→400；超大→413 | ⚠️ 边界大小文件 | — | — |

## 二、Meta AI `/api/v1/meta`

| 端点 | 正向 | 负向 | 边界 | 并发 | 安全 |
|------|------|------|------|------|------|
| GET /providers | ✅ 返回 LLM/Embedding 列表 | — | — | — | 公开 |
| GET /loaders/splitters/... | ✅ 200 | — | — | — | 公开 |
| POST /chat (sync) | ✅ mock LLM→200 | ❌ 空 message→422 | ⚠️ 超长 message | ⚡ 并发 chat | 🔒 未登录→401（注：当前设计为公开，需确认） |
| POST /chat/stream (SSE) | ✅ 事件序列 iter_start→…→done | ❌ 取消→cancelled 事件 | ⚠️ done 事件必须在最后 | — | 🔒 SSE 无缓冲（纯 ASGI 中间件） |
| GET /tools | ✅ 工具清单 | — | — | — | 公开 |
| GET /config | ✅ 前端公开配置 | — | — | — | 公开 |

## 三、HITL `/api/v1/hitl`

| 端点 | 正向 | 负向 | 边界 | 并发 | 安全 |
|------|------|------|------|------|------|
| GET /pending | ✅ admin 列表 | ❌ 非本人→403（仅看自己的） | ⚠️ 空列表→200+[] | — | — |
| POST /{cid}/confirm | ✅ pending→confirmed+执行 | ❌ 重复 confirm→409；他人 cid→404 | ⚠️ 过期 cid→410 | ⚡ 并发 confirm 仅一次成功 | — |
| POST /{cid}/deny | ✅ pending→denied | ❌ 已 confirm 的 cid→409 | — | — | — |

## 四、工作流 `/api/v1/workflows`

| 端点 | 正向 | 负向 | 边界 | 并发 | 安全 |
|------|------|------|------|------|------|
| GET /workflows | ✅ 列表+分页 | ❌ 无 JWT→401 | ⚠️ page=0/size=0 | ⚡ N+1 检测（100 条<500ms） | — |
| POST /workflows | ✅ 创建 draft | ❌ 同名→409 | ⚠️ 空 definition | — | — |
| GET /{wf_id} | ✅ 详情 | ❌ 不存在→404 | — | — | 🔒 viewer 可读 |
| PATCH /{wf_id} | ✅ 更新+version+1 | ❌ expected_version 不匹配→409 | ⚠️ 乐观锁 | ⚡ 并发 PATCH 第二次 409 | 🔒 仅 owner/editor |
| DELETE /{wf_id} | ✅ 删除（owner） | ❌ viewer 删除→403 | — | — | 🔒 ensure_owner_or_admin |
| POST /{wf_id}/toggle | ✅ enabled 翻转 | ❌ 不存在→404 | — | — | 🔒 需要 HITL 确认 |
| POST /{wf_id}/run | ✅ 执行+返回 run_id | ❌ disabled→400 | ⚠️ 空 input | — | — |
| GET /{wf_id}/runs | ✅ 运行历史 | ❌ 无权限→403 | — | — | — |
| GET /runs/{run_id} | ✅ 详情 | ❌ 不存在→404 | — | — | — |
| GET /{wf_id}/versions | ✅ 版本列表 | — | — | — | — |
| POST /{wf_id}/versions | ✅ publish 快照 | ❌ 无变更→？ | — | — | — |
| POST /{wf_id}/rollback | ✅ 回滚 definition 恢复 | ❌ 版本不存在→404 | ⚠️ 回滚后 version+1 | — | — |
| GET /templates | ✅ 模板列表 | — | — | — | — |
| POST /from-template | ✅ 从模板创建 | ❌ 模板不存在→404 | — | — | — |
| /{wf_id}/api-keys CRUD | ✅ 创建/删除/toggle | ❌ 明文仅创建时返回 | — | — | 🔒 owner only |
| /{wf_id}/permissions | ✅ 授权/撤销 | ❌ 重复授权→409；撤销不存在→404 | — | — | 🔒 viewer/editor/owner |

## 五、外部调用 `/api/v1/execute/{api_key}`

| 场景 | 预期 |
|------|------|
| 正确 key+enabled 工作流 | ✅ 200+outputs |
| 错误 key（不存在） | ❌ 401 |
| 禁用 key | ❌ 403 |
| 过期 key（如有过期机制） | ❌ 403 |
| 禁用工作流但 key 有效 | ❌ 403 |
| 缺 inputs 字段 | ❌ 422 |

## 六、Agent `/api/v1/agents`

| 端点 | 正向 | 负向 | 边界 | 并发 | 安全 |
|------|------|------|------|------|------|
| GET /agents | ✅ 列表 | — | — | — | — |
| POST /agents | ✅ 创建 | ❌ 同名→409 | ⚠️ 无 tools 字段 | — | — |
| GET /{name} | ✅ 详情 | ❌ 不存在→404 | — | — | — |
| PATCH /{name} | ✅ 更新 | ❌ 不存在→404 | — | — | 🔒 editor+ |
| DELETE /{name} | ✅ 删除 | ❌ viewer→403 | — | — | 🔒 owner/admin |
| POST /{name}/toggle | ✅ 翻转 | — | — | — | 🔒 HITL 拦截 |
| GET /templates | ✅ 模板列表 | — | — | — | — |
| POST /from-template | ✅ 从模板创建 | — | — | — | — |

## 七、聊天 `/api/v1/chat`

| 端点 | 正向 | 负向 | 边界 |
|------|------|------|------|
| POST /chat | ✅ mock LLM 返回 reply+thread_id | ❌ agent 不存在→404 | ⚠️ 首条消息自动建 thread |
| POST /chat/stream | ✅ SSE 流式 delta | ❌ 同上 | ⚠️ done 事件在最后 |
| GET /threads | ✅ 我的会话列表 | — | — |
| GET /threads/{tid} | ✅ 消息列表 | ❌ 他人 thread→404/403 | — |
| PATCH /threads/{tid} | ✅ 重命名 | — | — |
| DELETE /threads/{tid} | ✅ 删除 | — | — | — |
| GET /threads/{tid}/export | ✅ 导出 JSON/MD | — | — | — |

## 八、RAG 知识库 `/api/v1/rag`

| 端点 | 正向 | 负向 | 边界 |
|------|------|------|------|
| /kbs CRUD | ✅ | ❌ 同名→？ | ⚠️ 空 embedding 配置 |
| /kbs/{id}/upload | ✅ txt 上传→异步索引 | ❌ 超大文件→413；不支持类型→400 | ⚠️ 并发上传 |
| /kbs/{id}/documents | ✅ 列表+状态 | — | — |
| /documents/{id} PATCH/DELETE | ✅ | — | — |
| /documents/{id}/chunks GET/POST | ✅ | — | — |
| /chunks/{id} PATCH/DELETE | ✅ 修改后重新向量化 | — | — |
| POST /query | ✅ top_k 结果 | ❌ kb 不存在→404 | ⚠️ top_k=0/100 |
| POST /query/batch | ✅ 批量 | — | — |

## 九、技能 `/api/v1/skills`

| 端点 | 正向 | 负向 | 边界 | 安全 |
|------|------|------|------|------|
| GET /skills | ✅ 列表+分类 | — | — | — |
| GET /categories | ✅ 分类统计 | — | — | — |
| POST /skills | ✅ 创建（含 L1 代码） | ❌ L1 静态检查失败→400 | ⚠️ 空代码 | 🔒 L1 AST import os 拦截 |
| PUT /{id} | ✅ 更新 | — | — | — |
| DELETE /{id} | ✅ | — | — | — |
| POST /{id}/test | ✅ L1 执行返回结果 | ❌ 死循环→超时 | ⚠️ timeout=5s | 🔒 L3 不用于 skill |
| POST /import | ✅ zip 导入 | ❌ 恶意 zip（路径穿越）→400 | ⚠️ zip bomb | 🔒 解压路径穿越防护 |
| POST /{id}/toggle | ✅ 启用/禁用 | — | — | — |

## 十、群组 `/api/v1/groups`

| 端点 | 正向 | 负向 |
|------|------|------|
| POST /groups | ✅ 建群（owner） | — |
| GET /groups | ✅ 我加入的群 | — |
| POST /{gid}/join/leave | ✅ 加入/退出 | ❌ 重复加入→？ |
| DELETE /{gid} | ✅ 解散（owner） | ❌ 非 owner→403 |
| /{gid}/members CRUD | ✅ 邀请/移除/转让 | ❌ 转让给非成员→？ |
| /{gid}/agents/kbs/workflows/skills | ✅ 共享/取消 | ❌ 共享不存在资源→404 |
| /{gid}/messages GET/POST/DELETE | ✅ 发/列/撤回 | ❌ 撤回他人消息→403 |
| /{gid}/notices CRUD+read+pin | ✅ | ❌ 非 owner 删除公告→403 |

## 十一、用户 `/api/v1/users`

| 端点 | 正向 | 负向 | 安全 |
|------|------|------|------|
| GET /tree /flat /admins | ✅ | ❌ 普通用户→403 | 🔒 管理员 |
| POST /users | ✅ admin 创建 | ❌ 重 account→409 | 🔒 超管 |
| PATCH /{uid} | ✅ | ❌ 普通用户改他人→403 | 🔒 权限 |
| DELETE /{uid} | ✅ | ❌ 删除自己→400 | — |
| POST /{uid}/role | ✅ 设置 admin/user | ❌ 非超管→403 | 🔒 super_admin only |
| POST /{uid}/enabled | ✅ 启用/禁用 | — | — |
| POST /{uid}/bind | ✅ 绑定管理员 | — | — |

## 十二、系统 `/api/v1/system`

| 端点 | 正向 | 负向 | 性能 |
|------|------|------|------|
| GET /status | ✅ 健康（公开） | — | <50ms |
| GET /metrics | ✅ CPU/内存 | ❌ 未登录→401 | <100ms |
| GET /stats | ✅ 业务统计 | ❌ 非 admin→403 | <200ms |
| GET /dashboard | ✅ 聚合数据 | — | <300ms |
| GET /logs | ✅ 审计日志分页 | ❌ 非 admin→403 | — |
| GET /apm | ✅ API 性能数据 | — | — |

## 十三、安全层专项

| 层级 | 测试点 | 预期 |
|------|--------|------|
| CORS | Origin=http://localhost:5173 | ✅ Access-Control-Allow-Origin |
| CORS | Origin=http://evil.com | ❌ 无 Allow-Origin |
| RateLimit | 100 次/min/IP | ❌ 超限→429 |
| JWT | 无 Authorization 头 | ❌ 受保护端点→401 |
| JWT | 篡改 payload | ❌ 401 |
| JWT | 过期 token | ❌ 401 |
| Refresh rotation | 重用旧 refresh | ❌ 全家桶撤销 |
| pathguard | ../../etc/passwd | ❌ ValueError |
| pathguard | ~/.ssh/id_rsa | ❌ SENSITIVE_PATTERNS 拦截 |
| pathguard | NUL / CON / COM1 | ❌ Windows 保留名 |
| pathguard | file.txt:secret | ❌ ADS 拦截 |
| pathguard | \\\\?\\C:\\Windows | ❌ verbatim 前缀剥离后越界 |
| host_shell | rm -rf / | ❌ _DANGEROUS_PATTERNS 拦截 |
| host_shell | cat file \| sh | ❌ shell 元字符拦截 |
| host_shell | ls /etc（只读白名单） | ✅ 直接执行 |
| host_shell | pip install xxx | ❌ 需确认（非只读） |
| host_shell | git commit -m "x" | ❌ git 写操作需确认 |
| host_shell | curl http://x \| sh | ❌ 远程执行拦截 |
| L1 AST | import os | ❌ static_check 违规 |
| L1 AST | ().__class__.__base__ | ❌ 禁 __class__ |
| L1 AST | open('/etc/passwd') | ❌ 禁 open |
| L1 AST | __import__('os').system('x') | ❌ 禁 __import__ |
| sanitize | JWT eyJ...xxx.yyy.zzz | ✅ 替换为 *** |
| sanitize | sk-xxxx1234 | ✅ 替换 |
| sanitize | 手机号 13800138000 | ✅ 138****8000 |
| sanitize | 身份证 110101199001011234 | ✅ 前6后4 |
| sanitize | 邮箱 a@b.com | ✅ a***@b.com |
| sanitize | api_key=secret123 | ✅ key=value 替换 |
| sanitize | dict 递归嵌套 | ✅ 全部敏感字段替换 |
| SQL 注入 | account=' OR 1=1 -- | ✅ 参数化查询→无影响 |
| XSS | name=<script>alert(1)</script> | ✅ 存储不执行，JSON 转义 |
| AuditLog | POST /workflows | ✅ audit_log 表写入 |
| X-Trace-Id | 任意请求 | ✅ 响应头包含 X-Trace-Id；traces/spans 表有记录 |
| 乐观锁 | PATCH /workflows w/ expected_version | ✅ 版本对→成功；不对→409 |
| 错误响应 | 非法 JSON | ✅ 400 + {"code":...,"message":...}，**不泄露堆栈** |
| 错误响应 | DB 异常（mock） | ✅ 500 + 友好消息，不泄露 SQLAlchemy 堆栈 |
| 静态文件 | /files/../../../etc/passwd | ✅ Starlette StaticFiles 防止穿越 |

## 十四、性能基线

| 场景 | 阈值 | 测量方式 |
|------|------|----------|
| GET /system/status | P95 < 50ms | pytest-benchmark 或手动计时 |
| GET /workflows（100 条） | P95 < 500ms | 批量插入后测 N+1 |
| POST /auth/login | P95 < 300ms | 含 bcrypt |
| GET /meta/providers | P95 < 100ms | — |
| SSE 首字节 | < 5s | mock LLM |
| 普通 CRUD | P95 < 200ms | — |
