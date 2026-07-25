import { useEffect, useState, useMemo } from 'react'
import toast from 'react-hot-toast'
import { useNavigate } from 'react-router-dom'
import { dbConnectionApi, DbConnection, DbConnectionCreate, DbConnectionUpdate } from '@/api'
import { useAuthStore } from '@/store/auth'
import Modal from '@/components/ui/Modal'
import Input from '@/components/ui/Input'
import Textarea from '@/components/ui/Textarea'

const DB_TYPES = [
  { value: 'mysql', label: 'MySQL', defaultPort: 3306 },
  { value: 'postgresql', label: 'PostgreSQL', defaultPort: 5432 },
  { value: 'mongodb', label: 'MongoDB', defaultPort: 27017 },
  { value: 'sqlite', label: 'SQLite', defaultPort: null },
  { value: 'sqlserver', label: 'SQL Server', defaultPort: 1433 },
  { value: 'oracle', label: 'Oracle', defaultPort: 1521 },
]

const CHARSETS = ['utf8mb4', 'utf8', 'gbk', 'gb2312', 'latin1', 'ascii']

export default function DbConnections() {
  const nav = useNavigate()
  const me = useAuthStore(s => s.user)
  const isSuper = me?.role === 'super_admin'
  const [connections, setConnections] = useState<DbConnection[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<DbConnection | null>(null)
  const [creating, setCreating] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; version?: string } | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await dbConnectionApi.list()
      setConnections(res)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const create = async (data: DbConnectionCreate) => {
    try {
      await dbConnectionApi.create(data)
      toast.success('已创建')
      setCreating(false)
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '创建失败')
    }
  }

  const update = async (id: number, data: DbConnectionUpdate) => {
    try {
      await dbConnectionApi.update(id, data)
      toast.success('已更新')
      setEditing(null)
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '更新失败')
    }
  }

  const remove = async (id: number, name: string) => {
    if (!confirm(`确定删除连接 "${name}"?`)) return
    try {
      await dbConnectionApi.remove(id)
      toast.success('已删除')
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '删除失败')
    }
  }

  const toggle = async (id: number, enabled: boolean) => {
    try {
      await dbConnectionApi.toggle(id, enabled)
      toast.success(enabled ? '已启用' : '已禁用')
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '操作失败')
    }
  }

  const test = async (data: any) => {
    try {
      const res = await dbConnectionApi.test(data)
      setTestResult(res)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '测试失败')
    }
  }

  const testSaved = async (id: number) => {
    try {
      const res = await dbConnectionApi.testSaved(id)
      setTestResult(res)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '测试失败')
    }
  }

  const exportConfig = async () => {
    try {
      const res = await dbConnectionApi.export()
      const blob = new Blob([JSON.stringify(res, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `db-connections-${Date.now()}.json`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('导出成功')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '导出失败')
    }
  }

  const importConfig = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const content = await file.text()
      const data = JSON.parse(content)
      await dbConnectionApi.import(data)
      toast.success('导入成功')
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '导入失败')
    }
  }

  return (
    <div className="p-6 space-y-5 animate-fadeIn">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-primary">数据库连接管理</h1>
          <p className="text-tertiary text-sm mt-1">管理系统数据库连接配置，支持多种数据库类型</p>
        </div>
        <div className="flex gap-2">
          <button onClick={exportConfig} className="btn btn-secondary">📥 导出配置</button>
          <label className="btn btn-secondary cursor-pointer">
            📤 导入配置
            <input type="file" accept=".json" className="hidden" onChange={importConfig} />
          </label>
          <button onClick={() => setCreating(true)} className="btn btn-primary">➕ 新建连接</button>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1,2,3,4].map(i => (
            <div key={i} className="card p-4">
              <div className="skeleton h-4 w-32 mb-3" /><div className="skeleton h-3 w-full mb-2" /><div className="skeleton h-3 w-2/3" />
            </div>
          ))}
        </div>
      ) : connections.length === 0 ? (
        <div className="py-12 text-center">
          <div className="text-4xl mb-3">🗄️</div>
          <div className="text-primary font-medium mb-2">暂无数据库连接配置</div>
          <div className="text-tertiary text-sm">点击上方按钮创建第一个数据库连接</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {connections.map(conn => {
            const dbType = DB_TYPES.find(t => t.value === conn.db_type)
            return (
              <div key={conn.id} className="card p-4">
                <div className="flex items-start justify-between mb-2">
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold text-primary truncate">{conn.display_name || conn.name}</div>
                    <div className="text-xs text-placeholder truncate mt-0.5">
                      {dbType?.label || conn.db_type} · {conn.host}:{conn.port} · {conn.database}
                    </div>
                  </div>
                  <span className={`badge shrink-0 ml-2 ${conn.enabled ? 'badge-green' : 'badge-gray'}`}>
                    {conn.enabled ? '已启用' : '已禁用'}
                  </span>
                </div>
                <p className="text-sm text-secondary mb-3 line-clamp-2">{conn.description || '无描述'}</p>
                <div className="flex gap-2 pt-3 border-t border">
                  <button onClick={() => testSaved(conn.id)} className="btn btn-secondary btn-sm">🔗 测试连接</button>
                  <button onClick={() => setEditing(conn)} className="btn btn-primary btn-sm">✏️ 编辑</button>
                  <button onClick={() => toggle(conn.id, !conn.enabled)} className="btn btn-ghost btn-sm">
                    {conn.enabled ? '禁用' : '启用'}
                  </button>
                  <button onClick={() => remove(conn.id, conn.display_name || conn.name)} className="btn btn-ghost btn-sm text-danger ml-auto">删除</button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* 创建连接弹窗 */}
      {creating && (
        <ConnectionModal
          mode="create"
          onClose={() => { setCreating(false); setTestResult(null) }}
          onSave={create}
          onTest={(data) => { setTestResult(null); test(data) }}
          testResult={testResult}
        />
      )}

      {/* 编辑连接弹窗 */}
      {editing && (
        <ConnectionModal
          mode="edit"
          connection={editing}
          onClose={() => { setEditing(null); setTestResult(null) }}
          onSave={(data) => update(editing.id, data)}
          onTest={(data) => { setTestResult(null); test(data) }}
          testResult={testResult}
        />
      )}
    </div>
  )
}

function ConnectionModal({ mode, connection, onClose, onSave, onTest, testResult }: {
  mode: 'create' | 'edit'
  connection?: DbConnection
  onClose: () => void
  onSave: (data: any) => void
  onTest: (data: any) => void
  testResult: { success: boolean; message: string; version?: string } | null
}) {
  const [f, setF] = useState({
    name: connection?.name || '',
    display_name: connection?.display_name || '',
    db_type: connection?.db_type || 'mysql',
    host: connection?.host || 'localhost',
    port: connection?.port || 3306,
    database: connection?.database || '',
    username: connection?.username || '',
    password: '',
    charset: connection?.charset || 'utf8mb4',
    timeout: connection?.timeout || 30,
    extra_config: connection?.extra_config || {},
    enabled: connection?.enabled ?? true,
    is_default: connection?.is_default ?? false,
    description: connection?.description || '',
  })

  const dbType = useMemo(() => DB_TYPES.find(t => t.value === f.db_type), [f.db_type])

  const set = <K extends keyof typeof f>(k: K, v: any) => {
    if (k === 'db_type') {
      const t = DB_TYPES.find(t => t.value === v)
      setF(p => ({ ...p, [k]: v, port: t?.defaultPort || p.port }))
    } else {
      setF(p => ({ ...p, [k]: v }))
    }
  }

  const handleSave = () => {
    if (!f.name.trim()) { toast.error('请填写连接名称'); return }
    if (!f.database && f.db_type !== 'sqlite') { toast.error('请填写数据库名称'); return }

    const data: any = { ...f }
    if (mode === 'edit' && !f.password) {
      delete data.password
    }
    onSave(data)
  }

  const handleTest = () => {
    onTest({
      db_type: f.db_type,
      host: f.host,
      port: f.port,
      database: f.database,
      username: f.username,
      password: f.password,
      charset: f.charset,
      timeout: 10,
    })
  }

  return (
    <Modal isOpen={true} onClose={onClose} title={mode === 'create' ? '新建数据库连接' : `编辑连接: ${connection?.display_name || connection?.name}`} width="max-w-2xl">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Field label="连接名称 *">
            <Input
              value={f.name}
              onChange={e => set('name', e.target.value)}
              disabled={mode === 'edit'}
              placeholder="唯一标识，如：production_mysql"
            />
          </Field>
          <Field label="显示名称">
            <Input
              value={f.display_name}
              onChange={e => set('display_name', e.target.value)}
              placeholder="友好显示名称"
            />
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label="数据库类型 *">
            <select
              value={f.db_type}
              onChange={e => set('db_type', e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-card border border text-sm"
            >
              {DB_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </Field>
          <Field label="字符编码">
            <select
              value={f.charset}
              onChange={e => set('charset', e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-card border border text-sm"
            >
              {CHARSETS.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </Field>
        </div>

        {f.db_type !== 'sqlite' && (
          <div className="grid grid-cols-3 gap-4">
            <Field label="主机地址 *">
              <Input
                value={f.host}
                onChange={e => set('host', e.target.value)}
                placeholder="localhost"
              />
            </Field>
            <Field label="端口">
              <Input
                type="number"
                value={f.port}
                onChange={e => set('port', parseInt(e.target.value) || 0)}
                placeholder={String(dbType?.defaultPort)}
              />
            </Field>
            <Field label="数据库名称 *">
              <Input
                value={f.database}
                onChange={e => set('database', e.target.value)}
                placeholder="数据库名"
              />
            </Field>
          </div>
        )}

        {f.db_type === 'sqlite' && (
          <Field label="数据库文件路径 *">
            <Input
              value={f.database}
              onChange={e => set('database', e.target.value)}
              placeholder="如：/data/example.db"
            />
          </Field>
        )}

        <div className="grid grid-cols-2 gap-4">
          <Field label="用户名">
            <Input
              value={f.username}
              onChange={e => set('username', e.target.value)}
              placeholder="数据库用户名"
            />
          </Field>
          <Field label={mode === 'create' ? '密码 *' : '新密码（留空不改）'}>
            <Input
              type="password"
              value={f.password}
              onChange={e => set('password', e.target.value)}
              placeholder={mode === 'create' ? '数据库密码' : '留空则不修改密码'}
            />
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label="连接超时（秒）">
            <Input
              type="number"
              value={f.timeout}
              onChange={e => set('timeout', parseInt(e.target.value) || 30)}
              placeholder="30"
            />
          </Field>
          <Field label="高级配置（JSON）">
            <Textarea
              value={JSON.stringify(f.extra_config, null, 2)}
              onChange={e => {
                try {
                  set('extra_config', JSON.parse(e.target.value))
                } catch {}
              }}
              rows={3}
              placeholder='{"ssl": true}'
            />
          </Field>
        </div>

        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-secondary cursor-pointer">
            <input type="checkbox" checked={f.enabled} onChange={e => set('enabled', e.target.checked)} />
            启用连接
          </label>
          <label className="flex items-center gap-2 text-sm text-secondary cursor-pointer">
            <input type="checkbox" checked={f.is_default} onChange={e => set('is_default', e.target.checked)} />
            设置为默认连接
          </label>
        </div>

        <Field label="描述">
          <Textarea
            value={f.description}
            onChange={e => set('description', e.target.value)}
            rows={2}
            placeholder="描述这个连接的用途..."
          />
        </Field>

        {/* 测试结果 */}
        {testResult && (
          <div className={`p-3 rounded-lg ${testResult.success ? 'bg-green-500/10 border border-green-500/20' : 'bg-red-500/10 border border-red-500/20'}`}>
            <div className="flex items-center gap-2 mb-1">
              <span>{testResult.success ? '✅' : '❌'}</span>
              <span className={testResult.success ? 'text-green-300' : 'text-red-300'}>{testResult.message}</span>
            </div>
            {testResult.version && (
              <div className="text-xs text-placeholder ml-6">数据库版本: {testResult.version}</div>
            )}
          </div>
        )}
      </div>

      <div className="flex justify-end gap-3 mt-5 pt-4 border-t border">
        <button onClick={onClose} className="btn btn-secondary">取消</button>
        <button onClick={handleTest} className="btn btn-secondary">🔗 测试连接</button>
        <button onClick={handleSave} className="btn btn-primary">
          {mode === 'create' ? '创建' : '保存'}
        </button>
      </div>
    </Modal>
  )
}

function Field({ label, children, help }: { label: string; children: React.ReactNode; help?: string }) {
  return <div>
    <label className="block text-xs text-tertiary mb-1.5 font-medium">{label}</label>
    {children}
    {help && <div className="text-xs text-placeholder mt-1">{help}</div>}
  </div>
}
