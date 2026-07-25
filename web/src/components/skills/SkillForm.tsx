import { useState } from 'react'
import toast from 'react-hot-toast'
import { skillApi, Skill } from '@/api'
import Button from '@/components/ui/Button'
import Modal from '@/components/ui/Modal'
import Input from '@/components/ui/Input'
import BundleFileTree from './BundleFileTree'

/** 新建/编辑 Skill 表单 */
export default function SkillForm({ skill, categories, onClose, onSaved }: {
  skill: Skill | null; categories: string[]; onClose: () => void; onSaved: () => void
}) {
  const isEdit = !!skill
  const isBuiltin = skill?.is_builtin
  const [f, setF] = useState({
    name: skill?.name || '',
    description: skill?.description || '',
    version: skill?.version || '1.0.0',
    author: skill?.author || '',
    category: skill?.category || '',
    tags: (skill?.tags || []).join(', '),
    entry_point: skill?.entry_point || '',
    content: skill?.content || '',
  })
  const [saving, setSaving] = useState(false)

  // 从 content 自动解析 front matter
  const parseFrontMatter = (text: string) => {
    const m = text.match(/^---\s*\n([\s\S]*?)\n---/)
    if (!m) return
    try {
      const meta: Record<string, any> = {}
      m[1].split('\n').forEach(line => {
        const idx = line.indexOf(':')
        if (idx > 0) {
          const k = line.slice(0, idx).trim()
          let v: any = line.slice(idx + 1).trim()
          if (v.startsWith('[') && v.endsWith(']')) {
            v = v.slice(1, -1).split(',').map((s: string) => s.trim().replace(/^["']|["']$/g, '')).filter(Boolean)
          } else {
            v = v.replace(/^["']|["']$/g, '')
          }
          meta[k] = v
        }
      })
      setF(prev => ({
        ...prev,
        name: meta.name || prev.name,
        description: meta.description || prev.description,
        version: meta.version || prev.version,
        author: meta.author || prev.author,
        category: meta.category || prev.category,
        tags: Array.isArray(meta.tags) ? meta.tags.join(', ') : (typeof meta.tags === 'string' ? meta.tags : prev.tags),
        entry_point: meta.entry_point || prev.entry_point,
      }))
      toast.success('已从 Front Matter 解析元信息')
    } catch (e) {
      toast.error('解析 Front Matter 失败')
    }
  }

  const save = async () => {
    if (!f.name.trim()) { toast.error('请填写技能名称'); return }
    if (!f.content.trim()) { toast.error('请填写技能内容 (SKILL.md)'); return }
    setSaving(true)
    try {
      const body = {
        name: f.name.trim(),
        description: f.description,
        version: f.version,
        author: f.author,
        category: f.category,
        tags: f.tags.split(',').map(s => s.trim()).filter(Boolean),
        entry_point: f.entry_point || undefined,
        content: f.content,
      }
      if (isEdit) await skillApi.update(skill!.id, body)
      else await skillApi.create(body)
      toast.success('已保存'); onSaved()
    } catch (e: any) {
      toast.error(e?.response?.data?.msg || '保存失败')
    } finally { setSaving(false) }
  }

  return (
    <Modal isOpen={true} onClose={onClose} title={isEdit ? `编辑技能: ${skill?.name}` : '新建技能'} width="max-w-4xl">
      {isBuiltin && (
        <div className="mb-4 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-sm text-amber-300">
          ⚠️ 这是内置技能，不可修改
        </div>
      )}
      <div className="grid grid-cols-2 gap-4">
        <Input label="技能名称 (英文唯一标识) *" value={f.name}
          onChange={e => setF({ ...f, name: e.target.value })} disabled={isBuiltin || isEdit}
          placeholder="my-skill" />
        <Input label="版本" value={f.version}
          onChange={e => setF({ ...f, version: e.target.value })} disabled={isBuiltin}
          placeholder="1.0.0" />
        <Input label="作者" value={f.author}
          onChange={e => setF({ ...f, author: e.target.value })} disabled={isBuiltin}
          placeholder="your name" />
        <div>
          <label className="block text-sm font-medium text-tertiary mb-1.5">分类</label>
          <input list="skill-categories" value={f.category}
            onChange={e => setF({ ...f, category: e.target.value })} disabled={isBuiltin}
            className="glass-input w-full" placeholder="例如: data, dev, writing" />
          <datalist id="skill-categories">
            {categories.map(c => <option key={c} value={c} />)}
          </datalist>
        </div>
        <Input label="标签 (逗号分隔)" value={f.tags}
          onChange={e => setF({ ...f, tags: e.target.value })} disabled={isBuiltin}
          placeholder="tag1, tag2" />
        <Input label="入口函数" value={f.entry_point}
          onChange={e => setF({ ...f, entry_point: e.target.value })} disabled={isBuiltin}
          placeholder="main.run (可选)" />
      </div>
      <div className="mt-3">
        <label className="block text-sm font-medium text-tertiary mb-1.5">描述</label>
        <textarea value={f.description} onChange={e => setF({ ...f, description: e.target.value })}
          disabled={isBuiltin} rows={2}
          className="glass-input w-full resize-none" placeholder="简要描述技能的功能..." />
      </div>
      {/* 多文件 bundle 展示 (zip 导入时自动出现) */}
      {skill?.config?.bundle && typeof skill.config.bundle === 'object' && Object.keys(skill.config.bundle).length > 0 && (
        <div className="mt-3 p-3 bg-card rounded-lg border border">
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs font-medium text-secondary flex items-center gap-1.5">
              📦 文件包 ({Object.keys(skill.config.bundle).length} 个文件)
              {skill.config.entry && <span className="text-placeholder">入口: <code className="text-cyan-300">{skill.config.entry}</code></span>}
            </div>
          </div>
          <BundleFileTree bundle={skill.config.bundle as Record<string, string>} />
        </div>
      )}
      <div className="mt-3">
        <div className="flex items-center justify-between mb-1.5">
          <label className="text-sm font-medium text-tertiary">SKILL.md 内容 (支持 YAML Front Matter)</label>
          {!isBuiltin && (
            <button onClick={() => parseFrontMatter(f.content)}
              className="text-xs text-brand hover:text-purple-200">
              🔄 重新解析 Front Matter
            </button>
          )}
        </div>
        <textarea value={f.content} onChange={e => setF({ ...f, content: e.target.value })}
          disabled={isBuiltin} rows={14}
          className="glass-input w-full resize-y font-mono text-sm"
          placeholder={`---\nname: my-skill\ndescription: 技能描述\nversion: 1.0.0\nauthor: your-name\ncategory: data\ntags: [tag1, tag2]\n---\n\n# 技能内容...`} />
      </div>
      <div className="flex justify-end gap-3 mt-6 pt-4 border-t border">
        <Button variant="secondary" onClick={onClose}>取消</Button>
        {!isBuiltin && (
          <Button onClick={save} disabled={saving}>{saving ? '保存中...' : '保存'}</Button>
        )}
      </div>
    </Modal>
  )
}
