import http from './http'

// ===== 类型 =====
export interface User {
  user_id: number; username: string; account: string; email: string; avatar_url: string
  role: 'super_admin' | 'admin' | 'user'; enabled: boolean; bind_admin_id?: number
  manager_id?: number | null; department?: string
  online?: boolean; last_active_at?: string; created_at?: string
  title?: string; company?: string; location?: string; phone?: string; website?: string; bio?: string
  birthday?: string | null
}
export interface LoginIn { account: string; password: string }
export interface RegisterIn { username: string; account: string; email: string; password: string; bind_admin_id?: number }
export interface UpdateMeIn {
  username?: string; email?: string; avatar_url?: string; old_password?: string; new_password?: string
  title?: string; company?: string; department?: string; location?: string; phone?: string; website?: string; bio?: string
  birthday?: string | null
}

export const authApi = {
  login: (data: LoginIn) => http.post('/auth/login', data) as Promise<{ token: string; user: User }>,
  register: (data: RegisterIn) => http.post('/auth/register', data) as Promise<{ token: string; user: User }>,
  me: () => http.get('/auth/me') as Promise<User>,
  updateMe: (data: UpdateMeIn) => http.patch('/auth/me', data) as Promise<User>,
  uploadAvatar: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post('/auth/me/avatar', fd) as Promise<User>
  },
  ping: () => http.post('/auth/ping'),
}

// ===== Agent =====
export interface LLMConfig {
  provider?: 'giteeai' | 'ark' | 'deepseek'
  model?: string
  temperature?: number        // 0~2, default 1.0
  top_p?: number              // 0~1, default 1.0
  max_tokens?: number | null  // 最大输出 tokens
  presence_penalty?: number   // -2~2
  frequency_penalty?: number  // -2~2
  stream?: boolean            // 流式输出
  thinking?: boolean          // 展示思考内容
  extra_body?: Record<string, any>
}
export interface Agent {
  id: number; name: string; display_name: string; description: string; framework: string
  architecture: 'single' | 'react' | 'workflow' | 'skill'; system_prompt: string
  tools: string[]; rag_kb_ids: number[]
  llm_config: LLMConfig
  workflow_id?: number | null; parent_agent_id?: number | null; max_iterations: number
  enabled: boolean; created_by?: number; created_at: string; updated_at: string
}
export interface ChatIn { agent_name: string; message: string; thread_id?: string; stream?: boolean; variables?: Record<string, any> }
export interface ToolCall { tool: string; args: Record<string, any>; result: string }
export interface ChatStep { iter: number; tool_calls: ToolCall[] }
export interface Citation {
  idx: number
  chunk_id?: number
  document_id?: number
  document_name: string
  kb_id?: number
  chunk_index?: number
  content: string
  score: number
}
export interface ChatOut { reply: string; thinking?: string; thread_id: string; title: string; tool_calls: ToolCall[]; steps: ChatStep[]; citations?: Citation[] }

export const agentsApi = {
  list: (params?: { keyword?: string; enabled_only?: boolean }) => http.get('/agents', { params }) as Promise<Agent[]>,
  create: (data: Partial<Agent>) => http.post('/agents', data) as Promise<Agent>,
  get: (name: string) => http.get(`/agents/${name}`) as Promise<Agent>,
  update: (name: string, data: Partial<Agent>) => http.patch(`/agents/${name}`, data) as Promise<Agent>,
  remove: (name: string) => http.delete(`/agents/${name}`),
  toggle: (name: string, enabled: boolean) => http.post(`/agents/${name}/toggle`, { enabled }),
  templates: () => http.get('/agents/templates') as Promise<Array<{ id: string; name: string; display_name: string; description: string; category: string; icon: string }>>,
  fromTemplate: (data: { template_id: string; name?: string; display_name?: string }) => http.post('/agents/from-template', data) as Promise<Agent>,
  chat: (data: ChatIn) => http.post('/chat', data) as Promise<ChatOut>,
  /** 流式对话(SSE), 返回 fetch Response */
  chatStream: (data: ChatIn) => {
    const token = localStorage.getItem('token') || ''
    return fetch('/api/v1/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify(data),
    })
  },
}

// ===== Chat Threads =====
export interface ChatThread {
  id: number; thread_id: string; user_id: number; agent_name: string
  title: string; last_message: string; enabled: boolean; created_at: string; updated_at: string
}
export interface ChatMsg {
  id: number; role: string; content: string; created_at: string
}
export interface ThreadDetail extends ChatThread {
  messages: ChatMsg[]
}
export const chatApi = {
  threads: (agent_name?: string) => http.get('/chat/threads', { params: { agent_name } }) as Promise<ChatThread[]>,
  threadDetail: (tid: string, limit = 100) => http.get(`/chat/threads/${tid}`, { params: { limit } }) as Promise<ThreadDetail>,
  rename: (tid: string, title: string) => http.patch(`/chat/threads/${tid}`, { title }),
  remove: (tid: string) => http.delete(`/chat/threads/${tid}`),
  exportUrl: (tid: string, fmt: 'json' | 'md' = 'json') => `/api/v1/chat/threads/${tid}/export?fmt=${fmt}`,
}

// ===== RAG =====
export interface KB {
  id: number; name: string; description: string; icon_url?: string
  loader: string; splitter_type: string; chunk_size: number; chunk_overlap: number; splitter_regex?: string
  enabled: boolean; created_by?: number; created_at: string; updated_at: string
  document_count?: number; total_chunks?: number
}
export interface DocItem {
  id: number; kb_id: number; name: string; display_name: string
  file_size: number; content_type: string; chunk_count: number; status: string
  enabled: boolean
  metadata_?: { error?: string; loader?: string; splitter_type?: string; chunk_size?: number; chunk_overlap?: number }
  created_at: string; updated_at: string
}
export interface Chunk {
  id: number; document_id: number; chunk_index: number; content: string; token_count: number
  metadata_?: { type?: 'text' | 'image'; page?: number }; created_at: string
}
export interface QueryHit {
  chunk_id: number; document_id: number; chunk_index: number; score: number
  content: string; document_name?: string
}
export const ragApi = {
  listKb: () => http.get('/rag/kbs') as Promise<KB[]>,
  createKb: (data: Partial<KB>) => http.post('/rag/kbs', data) as Promise<KB>,
  getKb: (id: number) => http.get(`/rag/kbs/${id}`) as Promise<KB & { document_count: number; total_chunks: number }>,
  updateKb: (id: number, data: Partial<KB>) => http.patch(`/rag/kbs/${id}`, data) as Promise<KB>,
  removeKb: (id: number) => http.delete(`/rag/kbs/${id}`),
  uploadIcon: (id: number, file: File) => {
    const fd = new FormData(); fd.append('file', file)
    return http.post(`/rag/kbs/${id}/icon`, fd) as Promise<{ icon_url: string }>
  },
  listDocs: (kbId: number) => http.get(`/rag/kbs/${kbId}/documents`) as Promise<DocItem[]>,
  uploadDoc: (kbId: number, file: File, opts: { loader: string; splitter_type: string; chunk_size: number; chunk_overlap: number; splitter_regex?: string }) => {
    const fd = new FormData()
    fd.append('file', file); fd.append('loader', opts.loader); fd.append('splitter_type', opts.splitter_type)
    fd.append('chunk_size', String(opts.chunk_size)); fd.append('chunk_overlap', String(opts.chunk_overlap))
    if (opts.splitter_regex) fd.append('splitter_regex', opts.splitter_regex)
    return http.post(`/rag/kbs/${kbId}/upload`, fd) as Promise<{ document_id: number; status: string }>
  },
  updateDoc: (id: number, data: { display_name?: string; enabled?: boolean }) => http.patch(`/rag/documents/${id}`, data) as Promise<DocItem>,
  removeDoc: (id: number) => http.delete(`/rag/documents/${id}`),
  listChunks: (docId: number) => http.get(`/rag/documents/${docId}/chunks`) as Promise<Chunk[]>,
  createChunk: (docId: number, content: string, metadata_?: any) => http.post(`/rag/documents/${docId}/chunks`, { content, metadata_ }) as Promise<Chunk>,
  updateChunk: (cid: number, content: string) => http.patch(`/rag/chunks/${cid}`, { content }) as Promise<Chunk>,
  removeChunk: (cid: number) => http.delete(`/rag/chunks/${cid}`),
  query: (data: { kb_id: number; query: string; top_k?: number; rerank?: boolean; return_content?: boolean }) => http.post('/rag/query', data) as Promise<QueryHit[]>,
  batchQuery: (queries: { kb_id: number; query: string; top_k?: number; rerank?: boolean; return_content?: boolean }[]) =>
    http.post('/rag/query/batch', { queries }) as Promise<QueryHit[][]>,
}

// ===== Workflow =====
export interface Workflow {
  id: number; name: string; display_name: string; description: string; category: string
  definition: any; enabled: boolean; created_by?: number; created_at: string; updated_at: string
}
export const workflowApi = {
  list: () => http.get('/workflows') as Promise<Workflow[]>,
  create: (data: Partial<Workflow>) => http.post('/workflows', data) as Promise<Workflow>,
  get: (id: number) => http.get(`/workflows/${id}`) as Promise<Workflow>,
  update: (id: number, data: Partial<Workflow>) => http.patch(`/workflows/${id}`, data) as Promise<Workflow>,
  remove: (id: number) => http.delete(`/workflows/${id}`),
  toggle: (id: number, enabled: boolean) => http.post(`/workflows/${id}/toggle`, { enabled }),
  run: (id: number, input?: any) => http.post(`/workflows/${id}/run`, { input }),
  templates: () => http.get('/workflows/templates') as Promise<Array<{ id: string; name: string; display_name: string; description: string; category: string; node_count: number; edge_count: number }>>,
  fromTemplate: (data: { template_id: string; name?: string; display_name?: string }) => http.post('/workflows/from-template', data) as Promise<Workflow>,
  runs: (wfId: number, limit = 20) => http.get(`/workflows/${wfId}/runs`, { params: { limit } }) as Promise<Array<{ id: number; run_id: string; workflow_id: number; workflow_name: string; status: string; elapsed_ms: number; error?: string; created_at: string }>>,
  runDetail: (runId: string) => http.get(`/workflows/runs/${runId}`) as Promise<{ run_id: string; workflow_id: number; workflow_name: string; status: string; input_data: any; output_data: any; logs: string[]; node_outputs: any; error?: string; elapsed_ms: number; created_at: string }>,
}

// ===== Skills =====
export interface Skill {
  id: number; name: string; description: string; version: string; author: string
  category: string; tags: string[]; content: string; entry_point?: string
  code?: string; config?: Record<string, any>; is_builtin: boolean; is_active: boolean
  usage_count: number; last_used_at?: string; created_by?: number; created_at: string; updated_at: string
}
export interface SkillTestIn { input_params: Record<string, any>; context?: any }
export interface SkillTestOut { success: boolean; output: any; logs: string[]; elapsed_ms: number; error?: string; execution_time?: number }
export interface SkillCategory { category: string; count: number }
export const skillApi = {
  list: (params?: { keyword?: string; category?: string; tag?: string; is_active?: boolean }) =>
    http.get('/skills', { params }) as Promise<Skill[]>,
  categories: () => http.get('/skills/categories') as Promise<SkillCategory[]>,
  get: (id: number) => http.get(`/skills/${id}`) as Promise<Skill>,
  create: (data: Partial<Skill>) => http.post('/skills', data) as Promise<Skill>,
  update: (id: number, data: Partial<Skill>) => http.put(`/skills/${id}`, data) as Promise<Skill>,
  remove: (id: number) => http.delete(`/skills/${id}`),
  test: (id: number, data: SkillTestIn) => http.post(`/skills/${id}/test`, data) as Promise<SkillTestOut>,
  import: (data: { content?: string; file?: File }) => {
    if (data.file) {
      const fd = new FormData(); fd.append('file', data.file)
      return http.post('/skills/import', fd) as Promise<Skill>
    }
    return http.post('/skills/import', { content: data.content }) as Promise<Skill>
  },
  toggle: (id: number, is_active: boolean) => http.post(`/skills/${id}/toggle`, { is_active }),
}

// ===== Groups =====
export interface Group { id: number; name: string; description: string; owner_id: number; member_count?: number; unread_notices?: number; created_at: string }
export interface Member { user_id: number; username: string; avatar_url: string; role: 'owner' | 'member'; online?: boolean; last_active_at?: string }
export interface GroupAgent { agent_id: number; name: string; description: string; shared_by: number }
export interface GroupKB { kb_id: number; name: string; description: string; shared_by: number }
export interface GroupMsg {
  id: number; group_id: number; user_id: number; username: string; avatar_url?: string
  role: 'user' | 'bot'; agent_name?: string; content: string; reply_to?: number; created_at: string
}
export interface GroupNotice {
  id: number; group_id: number; author_id: number; author_name: string; author_avatar: string
  title: string; content: string; pinned: boolean; created_at: string; updated_at: string
  read_count: number; is_read: boolean
}
export const groupApi = {
  list: () => http.get('/groups') as Promise<Group[]>,
  create: (data: { name: string; description: string }) => http.post('/groups', data) as Promise<Group>,
  join: (gid: number) => http.post(`/groups/${gid}/join`),
  leave: (gid: number) => http.post(`/groups/${gid}/leave`),
  disband: (gid: number) => http.delete(`/groups/${gid}`),
  kickMember: (gid: number, uid: number) => http.delete(`/groups/${gid}/members/${uid}`),
  inviteMember: (gid: number, uid: number) => http.post(`/groups/${gid}/members/${uid}`),
  transferOwner: (gid: number, uid: number) => http.post(`/groups/${gid}/transfer/${uid}`),
  listMembers: (gid: number) => http.get(`/groups/${gid}/members`) as Promise<Member[]>,
  listAgents: (gid: number) => http.get(`/groups/${gid}/agents`) as Promise<GroupAgent[]>,
  shareAgent: (gid: number, aid: number) => http.post(`/groups/${gid}/agents/${aid}`),
  unshareAgent: (gid: number, aid: number) => http.delete(`/groups/${gid}/agents/${aid}`),
  listKBs: (gid: number) => http.get(`/groups/${gid}/kbs`) as Promise<GroupKB[]>,
  shareKB: (gid: number, kid: number) => http.post(`/groups/${gid}/kbs/${kid}`),
  unshareKB: (gid: number, kid: number) => http.delete(`/groups/${gid}/kbs/${kid}`),
  listMsgs: (gid: number, params?: { before_id?: number; limit?: number }) => http.get(`/groups/${gid}/messages`, { params }) as Promise<GroupMsg[]>,
  sendMsg: (gid: number, data: { content: string; agent_name?: string; reply_to?: number }) => http.post(`/groups/${gid}/messages`, data) as Promise<GroupMsg[]>,
  deleteMsg: (gid: number, mid: number) => http.delete(`/groups/${gid}/messages/${mid}`),
  // 群公告
  listNotices: (gid: number) => http.get(`/groups/${gid}/notices`) as Promise<GroupNotice[]>,
  createNotice: (gid: number, data: { title: string; content: string; pinned?: boolean }) => http.post(`/groups/${gid}/notices`, data) as Promise<GroupNotice>,
  deleteNotice: (gid: number, nid: number) => http.delete(`/groups/${gid}/notices/${nid}`),
  markNoticeRead: (gid: number, nid: number) => http.post(`/groups/${gid}/notices/${nid}/read`),
  toggleNoticePin: (gid: number, nid: number, pin: boolean) => http.post(`/groups/${gid}/notices/${nid}/pin?pin=${pin}`),
  // 共享工作流
  listWorkflows: (gid: number) => http.get(`/groups/${gid}/workflows`) as Promise<Array<{ workflow_id: number; name: string; display_name: string; description: string; category: string; shared_by: number }>>,
  shareWorkflow: (gid: number, wfId: number) => http.post(`/groups/${gid}/workflows/${wfId}`),
  unshareWorkflow: (gid: number, wfId: number) => http.delete(`/groups/${gid}/workflows/${wfId}`),
  // 共享技能
  listSkills: (gid: number) => http.get(`/groups/${gid}/skills`) as Promise<Array<{ skill_id: number; name: string; display_name: string; description: string; category: string; is_builtin: boolean; shared_by: number }>>,
  shareSkill: (gid: number, skId: number) => http.post(`/groups/${gid}/skills/${skId}`),
  unshareSkill: (gid: number, skId: number) => http.delete(`/groups/${gid}/skills/${skId}`),
}

// ===== Users (admin) =====
export interface UserTreeNode extends User {
  children: UserTreeNode[]
}
export interface UserCreateIn {
  username: string; account: string; email: string; password: string
  role?: 'admin' | 'user'; manager_id?: number | null
  department?: string; title?: string
}
export interface UserUpdateIn {
  username?: string; email?: string; role?: 'admin' | 'user'
  manager_id?: number | null; department?: string; title?: string
  enabled?: boolean; password?: string
}
export const userApi = {
  list: (params?: { keyword?: string }) => http.get('/users', { params }) as Promise<User[]>,
  tree: (params?: { keyword?: string }) => http.get('/users/tree', { params }) as Promise<UserTreeNode[]>,
  flat: (params?: { keyword?: string }) => http.get('/users/flat', { params }) as Promise<Array<User & { depth: number }>>,
  create: (data: UserCreateIn) => http.post('/users', data) as Promise<User>,
  update: (id: number, data: UserUpdateIn) => http.patch(`/users/${id}`, data) as Promise<User>,
  remove: (id: number) => http.delete(`/users/${id}`),
  setRole: (id: number, role: string) => http.post(`/users/${id}/role`, { role }),
  setEnabled: (id: number, enabled: boolean) => http.post(`/users/${id}/enabled`, { enabled }),
  bind: (id: number, admin_id?: number) => http.post(`/users/${id}/bind`, { admin_id }),
  admins: () => http.get('/users/admins') as Promise<User[]>,
}

// ===== Meta =====
export interface LoaderOpt { key: string; label: string; desc: string }
export interface ArchOpt { key: string; label: string; desc: string; needs_framework: boolean; frameworks?: string[] }
export interface ToolOpt { name: string; display_name: string; description: string; params_schema: any }
export interface MetaConfig { app_name: string; version: string; max_upload_mb: number; password_min_len: number }

export interface SystemLLMConfig {
  system_prompt: string
  max_context_length: number
  max_output_tokens: number
  thinking_level: number
  is_multimodal_input: boolean
  is_embedding_model: boolean
  temperature: number
  top_p: number
  frequency_penalty: number
  presence_penalty: number
  response_timeout: number
  api_retry_count: number
}

export const metaApi = {
  providers: () => http.get('/meta/providers'),
  loaders: () => http.get('/meta/loaders') as Promise<LoaderOpt[]>,
  splitters: () => http.get('/meta/splitters') as Promise<{ key: string; label: string }[]>,
  architectures: () => http.get('/meta/architectures') as Promise<ArchOpt[]>,
  frameworks: () => http.get('/meta/frameworks') as Promise<{ key: string; label: string }[]>,
  tools: () => http.get('/meta/tools') as Promise<ToolOpt[]>,
  config: () => http.get('/meta/config') as Promise<MetaConfig>,
  llmConfig: () => http.get('/meta/llm-config') as Promise<SystemLLMConfig>,
  updateLlmConfig: (data: Partial<SystemLLMConfig>) => http.patch('/meta/llm-config', data),
}

// ===== System =====
export interface SysMetrics {
  uptime_seconds: number
  process: { pid: number; memory_rss_mb: number; cpu_percent: number; threads: number }
  system: { cpu_percent: number; memory_percent: number; memory_total_gb: number; memory_available_gb: number; disk_percent: number; disk_total_gb: number; disk_free_gb: number }
  psutil_available: boolean
}
export interface SysStats {
  total: { agents: number; skills: number; workflows: number; users: number }
  enabled: { agents: number; workflows: number }
}
export interface WFStats {
  total: number; success: number; failed: number; running: number
  success_rate: number; avg_ms: number; p50_ms: number; p95_ms: number
}
export interface WFTrendDay { date: string; success: number; failed: number }
export interface WFTopItem { id: number; name: string; runs: number; success: number; avg_ms: number }
export interface RecentRun {
  run_id: string; workflow_id: number; workflow_name: string
  status: string; elapsed_ms: number; created_at: string
}
export interface DashboardData {
  wf_stats: WFStats
  wf_trend: WFTrendDay[]
  wf_top: WFTopItem[]
  agent_stats: { messages: number; threads: number }
  agent_top: Array<{ name: string; msgs: number }>
  recent_runs: RecentRun[]
}
export const systemApi = {
  status: () => http.get('/system/status') as Promise<any>,
  metrics: () => http.get('/system/metrics') as Promise<SysMetrics>,
  stats: () => http.get('/system/stats') as Promise<SysStats>,
  dashboard: () => http.get('/system/dashboard') as Promise<DashboardData>,
  logs: (params?: { page?: number; page_size?: number; user_id?: number; action?: string; resource?: string; days?: number }) => http.get('/system/logs', { params }) as Promise<any>,
}

// ===== Database Connections =====
export interface DbConnection {
  id: number
  name: string
  display_name: string | null
  db_type: string
  host: string | null
  port: number | null
  database: string | null
  username: string | null
  password: string | null
  charset: string | null
  timeout: number | null
  extra_config: Record<string, any> | null
  enabled: boolean
  is_default: boolean
  description: string | null
  created_by: number | null
  created_at: string
  updated_at: string
}
export interface DbConnectionCreate {
  name: string
  display_name?: string
  db_type: string
  host?: string
  port?: number
  database?: string
  username?: string
  password?: string
  charset?: string
  timeout?: number
  extra_config?: Record<string, any>
  enabled?: boolean
  is_default?: boolean
  description?: string
}
export interface DbConnectionUpdate {
  display_name?: string
  db_type?: string
  host?: string
  port?: number
  database?: string
  username?: string
  password?: string
  charset?: string
  timeout?: number
  extra_config?: Record<string, any>
  enabled?: boolean
  is_default?: boolean
  description?: string
}
export interface DbConnectionTestResult {
  success: boolean
  message: string
  version?: string
  error?: string
}
export interface DbConnectionExport {
  connections: DbConnection[]
  export_time: string
}
export const dbConnectionApi = {
  list: () => http.get('/db-connections') as Promise<DbConnection[]>,
  get: (id: number) => http.get(`/db-connections/${id}`) as Promise<DbConnection>,
  create: (data: DbConnectionCreate) => http.post('/db-connections', data) as Promise<DbConnection>,
  update: (id: number, data: DbConnectionUpdate) => http.patch(`/db-connections/${id}`, data) as Promise<DbConnection>,
  remove: (id: number) => http.delete(`/db-connections/${id}`),
  toggle: (id: number, enabled: boolean) => http.post(`/db-connections/${id}/toggle`, { enabled }) as Promise<DbConnection>,
  test: (data: any) => http.post('/db-connections/test', data) as Promise<DbConnectionTestResult>,
  testSaved: (id: number) => http.post(`/db-connections/${id}/test`) as Promise<DbConnectionTestResult>,
  export: () => http.get('/db-connections/export') as Promise<DbConnectionExport>,
  import: (data: { connections: DbConnectionCreate[] }) => http.post('/db-connections/import', data) as Promise<DbConnection[]>,
}
