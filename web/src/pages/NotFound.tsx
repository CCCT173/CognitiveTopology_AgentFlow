import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-slate-950 text-primary">
      <div className="text-center max-w-md">
        <div className="text-7xl mb-4">🧭</div>
        <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-cyan-400 to-purple-400 bg-clip-text text-transparent">404</h1>
        <p className="text-tertiary mb-6">页面走丢了，或者它从未存在过。</p>
        <div className="flex items-center justify-center gap-3">
          <button onClick={() => history.back()} className="px-5 py-2 rounded-lg bg-hover hover:bg-active transition">返回上一页</button>
          <Link to="/" className="px-5 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-purple-500 hover:opacity-90 transition">回到首页</Link>
        </div>
      </div>
    </div>
  )
}
