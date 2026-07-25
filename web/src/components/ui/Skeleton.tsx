// 骨架屏组件 - 显示内容加载中的占位动画
interface SkeletonProps {
  className?: string
  rounded?: string
}

export function Skeleton({ className = '', rounded = 'rounded-lg' }: SkeletonProps) {
  return (
    <div className={`animate-pulse bg-hover ${rounded} ${className}`} />
  )
}

// 卡片骨架屏
export function CardSkeleton() {
  return (
    <div className="bg-card border border rounded-xl p-4 space-y-3 animate-fade-in">
      <Skeleton className="h-5 w-2/3" />
      <Skeleton className="h-3 w-1/3" />
      <Skeleton className="h-12 w-full" rounded="rounded" />
      <div className="flex gap-2 pt-2">
        <Skeleton className="h-7 w-16" rounded="rounded-lg" />
        <Skeleton className="h-7 w-16" rounded="rounded-lg" />
        <Skeleton className="h-7 w-12" rounded="rounded-lg" />
      </div>
    </div>
  )
}

// 列表骨架屏
export function ListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-card border border animate-fade-in" style={{ animationDelay: `${i * 50}ms` }}>
          <Skeleton className="h-10 w-10 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-1/4" />
            <Skeleton className="h-3 w-1/3" />
          </div>
          <Skeleton className="h-6 w-16" rounded="rounded-full" />
        </div>
      ))}
    </div>
  )
}

// 页面骨架屏
export function PageSkeleton() {
  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-4 w-64" />
        </div>
        <Skeleton className="h-10 w-32" rounded="rounded-xl" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <CardSkeleton /><CardSkeleton /><CardSkeleton /><CardSkeleton />
      </div>
    </div>
  )
}
