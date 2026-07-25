// 空状态组件
interface EmptyProps {
  icon?: string
  title: string
  description?: string
  action?: React.ReactNode
}

export default function Empty({ icon = '📭', title, description, action }: EmptyProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 animate-fade-in">
      <div className="text-6xl mb-4 opacity-60">{icon}</div>
      <div className="text-lg font-medium text-secondary mb-1">{title}</div>
      {description && <p className="text-sm text-placeholder text-center max-w-sm mb-4">{description}</p>}
      {action && <div>{action}</div>}
    </div>
  )
}

// 错误状态
export function ErrorState({ message = '加载失败', onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 animate-fade-in">
      <div className="text-5xl mb-3">⚠️</div>
      <div className="text-red-400 font-medium mb-1">{message}</div>
      <p className="text-sm text-placeholder mb-4">请检查网络连接后重试</p>
      {onRetry && (
        <button onClick={onRetry} className="px-4 py-2 rounded-xl bg-hover hover:bg-active text-sm transition">
          🔄 重试
        </button>
      )}
    </div>
  )
}

// 加载状态
export function Loading({ text = '加载中...' }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6">
      <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mb-3" />
      <div className="text-sm text-tertiary">{text}</div>
    </div>
  )
}
