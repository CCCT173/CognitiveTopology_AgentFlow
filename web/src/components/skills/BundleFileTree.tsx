import { useState } from 'react'

/** bundle 文件树展示 - 支持点击展开预览文件内容 */
export default function BundleFileTree({ bundle }: { bundle: Record<string, string> }) {
  const [openFile, setOpenFile] = useState<string | null>(null)
  // 构造树
  const tree: any = {}
  Object.keys(bundle).sort().forEach(path => {
    const parts = path.split('/')
    let cur = tree
    parts.forEach((seg, i) => {
      if (i === parts.length - 1) {
        cur[seg] = { __file: true, path }
      } else {
        cur[seg] = cur[seg] || {}
        cur = cur[seg]
      }
    })
  })

  const renderNode = (node: any, name: string, depth = 0): any => {
    if (node?.__file) {
      const full = node.path
      const isOpen = openFile === full
      const size = bundle[full]?.length || 0
      return (
        <div key={full}>
          <button onClick={() => setOpenFile(isOpen ? null : full)}
            className="w-full flex items-center gap-2 py-1 px-2 hover:bg-card rounded text-left text-xs transition"
            style={{ paddingLeft: `${depth * 12 + 8}px` }}>
            <span className="text-placeholder">📄</span>
            <span className={`flex-1 truncate font-mono ${isOpen ? 'text-cyan-300' : 'text-primary'}`}>{name}</span>
            <span className="text-placeholder">{size > 1024 ? `${(size / 1024).toFixed(1)}KB` : `${size}B`}</span>
          </button>
          {isOpen && (
            <pre className="mx-2 mb-2 p-2 bg-black/40 rounded border border text-[11px] text-primary font-mono overflow-x-auto max-h-60"
              style={{ marginLeft: `${depth * 12 + 16}px` }}>
              {bundle[full] || ''}
            </pre>
          )}
        </div>
      )
    }
    const children = Object.entries(node)
    return (
      <div key={name + depth}>
        {depth > 0 && (
          <div className="flex items-center gap-2 py-1 px-2 text-xs text-tertiary font-medium"
            style={{ paddingLeft: `${depth * 12 + 8}px` }}>
            <span>📁</span><span className="font-mono">{name}</span>
          </div>
        )}
        {children.map(([k, v]) => renderNode(v, k, depth + 1))}
      </div>
    )
  }

  return (
    <div className="max-h-60 overflow-y-auto bg-black/20 rounded-lg border border py-1">
      {Object.entries(tree).map(([k, v]) => renderNode(v, k, 0))}
    </div>
  )
}
