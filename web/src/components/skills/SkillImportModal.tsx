import { useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { skillApi } from '@/api'
import Button from '@/components/ui/Button'
import Modal from '@/components/ui/Modal'

/** 导入技能 - 支持粘贴md内容或上传.md/.zip文件 */
export default function SkillImportModal({ onClose, onImported }: { onClose: () => void; onImported: () => void }) {
  const [mode, setMode] = useState<'paste' | 'file'>('paste')
  const [content, setContent] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const doImport = async () => {
    if (mode === 'paste' && !content.trim()) { toast.error('请粘贴 SKILL.md 内容'); return }
    if (mode === 'file' && !file) { toast.error('请选择文件'); return }
    setImporting(true)
    try {
      await skillApi.import(mode === 'file' ? { file: file! } : { content })
      toast.success('导入成功'); onImported()
    } catch (e: any) {
      toast.error(e?.response?.data?.msg || '导入失败')
    } finally { setImporting(false) }
  }

  const onFile = (f: File | null) => {
    setFile(f)
    if (f && f.name.endsWith('.md')) {
      const reader = new FileReader()
      reader.onload = e => setContent(String(e.target?.result || ''))
      reader.readAsText(f)
    }
  }

  return (
    <Modal isOpen={true} onClose={onClose} title="📥 导入技能" width="max-w-2xl">
      <div className="flex gap-2 mb-4">
        <button onClick={() => setMode('paste')}
          className={`flex-1 py-2 rounded-lg text-sm transition ${mode === 'paste' ? 'bg-purple-500/30 border border-purple-500/50' : 'bg-card border border'}`}>
          📝 粘贴内容
        </button>
        <button onClick={() => setMode('file')}
          className={`flex-1 py-2 rounded-lg text-sm transition ${mode === 'file' ? 'bg-purple-500/30 border border-purple-500/50' : 'bg-card border border'}`}>
          📁 上传文件 (.md/.zip)
        </button>
      </div>

      {mode === 'paste' ? (
        <textarea value={content} onChange={e => setContent(e.target.value)} rows={14}
          className="glass-input w-full font-mono text-sm resize-y"
          placeholder="粘贴 SKILL.md 完整内容（需包含 YAML Front Matter）..." />
      ) : (
        <div className="space-y-3">
          <div onClick={() => fileRef.current?.click()}
            className="border-2 border-dashed border rounded-xl p-8 text-center cursor-pointer hover:border-purple-400/50 transition">
            <div className="text-4xl mb-2">📄</div>
            <p className="text-secondary text-sm">{file ? file.name : '点击选择文件或拖放到此处'}</p>
            <p className="text-placeholder text-xs mt-1">支持 .md / .zip 格式</p>
            <input ref={fileRef} type="file" accept=".md,.zip,.markdown" className="hidden"
              onChange={e => onFile(e.target.files?.[0] || null)} />
          </div>
          {content && file?.name.endsWith('.md') && (
            <details className="bg-card rounded-lg p-3">
              <summary className="text-sm text-secondary cursor-pointer">预览内容</summary>
              <pre className="mt-2 text-xs text-tertiary max-h-40 overflow-auto whitespace-pre-wrap">{content.slice(0, 2000)}</pre>
            </details>
          )}
        </div>
      )}

      <div className="flex justify-end gap-3 mt-6">
        <Button variant="secondary" onClick={onClose}>取消</Button>
        <Button onClick={doImport} disabled={importing}>{importing ? '导入中...' : '导入'}</Button>
      </div>
    </Modal>
  )
}
