// 页面切换动画容器 - 包裹页面内容提供淡入效果
import { ReactNode } from 'react'

export default function PageTransition({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`animate-fade-in ${className}`} key={location.pathname}>
      {children}
    </div>
  )
}
