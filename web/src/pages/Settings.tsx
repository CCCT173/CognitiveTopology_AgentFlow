import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { metaApi, authApi, User } from '@/api'
import { useAuthStore } from '@/store/auth'

type Tab = 'llm' | 'theme' | 'config'

export default function Settings() {
  const [tab, setTab] = useState<Tab>('llm')
  const user = useAuthStore(s => s.user)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  // LLM 配置
  const [llmConfig, setLlmConfig] = useState({
    system_prompt: '',
    max_context_length: 8192,
    max_output_tokens: 2048,
    thinking_level: 2,
    is_multimodal_input: false,
    is_embedding_model: false,
    temperature: 0.7,
    top_p: 0.9,
    frequency_penalty: 0.0,
    presence_penalty: 0.0,
    response_timeout: 60,
    api_retry_count: 2,
  })

  // 主题配置
  const [theme, setTheme] = useState<'light' | 'dark'>('dark')

  // 加载配置
  useEffect(() => {
    loadConfig()
    loadTheme()
  }, [])

  const loadConfig = async () => {
    try {
      const config = await metaApi.llmConfig()
      setLlmConfig(config)
    } catch (e) {
      console.error('加载 LLM 配置失败', e)
    }
  }

  const loadTheme = () => {
    const saved = localStorage.getItem('theme') as 'light' | 'dark' | null
    setTheme(saved || 'dark')
    document.documentElement.classList.toggle('light', saved === 'light')
  }

  // 保存 LLM 配置
  const saveLlmConfig = async () => {
    setSaving(true)
    try {
      await metaApi.updateLlmConfig(llmConfig)
      toast.success('配置已保存')
    } catch (e: any) {
      toast.error(e.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  // 切换主题
  const toggleTheme = (newTheme: 'light' | 'dark') => {
    setTheme(newTheme)
    localStorage.setItem('theme', newTheme)
    document.documentElement.classList.toggle('light', newTheme === 'light')
    toast.success(newTheme === 'light' ? '已切换到白天主题' : '已切换到夜晚主题')
  }

  // 重置为默认值
  const resetDefaults = () => {
    setLlmConfig({
      system_prompt: 'You are a helpful AI assistant. Please answer questions accurately and concisely.',
      max_context_length: 8192,
      max_output_tokens: 2048,
      thinking_level: 2,
      is_multimodal_input: false,
      is_embedding_model: false,
      temperature: 0.7,
      top_p: 0.9,
      frequency_penalty: 0.0,
      presence_penalty: 0.0,
      response_timeout: 60,
      api_retry_count: 2,
    })
    toast('已重置为默认值')
  }

  const tabs: { key: Tab; label: string; icon: string }[] = [
    { key: 'llm', label: 'LLM 参数', icon: '🤖' },
    { key: 'theme', label: '主题设置', icon: '🎨' },
    { key: 'config', label: '系统配置', icon: '⚙️' },
  ]

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">⚙️ 系统设置</h1>
        <p className="text-tertiary text-sm mt-1">管理系统配置、LLM 参数和界面主题</p>
      </div>

      {/* 标签页 */}
      <div className="flex gap-2 p-1 bg-card border border rounded-xl w-fit">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              tab === t.key
                ? 'bg-gradient-to-r from-brand to-brand-700 shadow-sm'
                : 'text-tertiary hover:text-primary hover:bg-hover'
            }`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* LLM 参数配置 */}
      {tab === 'llm' && (
        <div className="space-y-6">
          <div className="bg-card border border rounded-xl p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-bold">LLM 参数配置</h2>
              <div className="flex gap-2">
                <button onClick={resetDefaults} className="px-3 py-1.5 rounded-lg bg-hover hover:bg-active text-sm text-tertiary transition">
                  🔄 重置默认
                </button>
                <button onClick={saveLlmConfig} disabled={saving} className="px-4 py-1.5 rounded-lg bg-gradient-to-r from-brand to-brand-700 text-sm font-medium hover:opacity-90 disabled:opacity-50 transition">
                  {saving ? '保存中...' : '💾 保存配置'}
                </button>
              </div>
            </div>

            {/* 文本类参数 */}
            <div className="space-y-5">
              {/* 系统提示词 */}
              <div className="p-4 bg-hover/50 rounded-xl">
                <label className="block text-sm font-medium text-tertiary mb-2">
                  📝 系统提示词
                  <span className="text-placeholder ml-2">控制 AI 的行为和角色定位</span>
                </label>
                <textarea
                  value={llmConfig.system_prompt}
                  onChange={e => setLlmConfig(c => ({ ...c, system_prompt: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg bg-card border border focus:outline-none focus:border-cyan-400/50 text-sm resize-none min-h-[120px] transition"
                  placeholder="请输入系统提示词..."
                />
              </div>

              {/* 数值类参数 - 第一行 */}
              <div className="grid md:grid-cols-3 gap-4">
                {/* 最大上下文长度 */}
                <div className="p-4 bg-hover/50 rounded-xl">
                  <label className="block text-sm font-medium text-tertiary mb-2">
                    📐 最大上下文长度
                    <span className="text-placeholder ml-2">当前: {llmConfig.max_context_length}</span>
                  </label>
                  <input
                    type="number"
                    min={1024}
                    max={100000}
                    step={1024}
                    value={llmConfig.max_context_length}
                    onChange={e => setLlmConfig(c => ({ ...c, max_context_length: parseInt(e.target.value) || 8192 }))}
                    className="w-full px-3 py-2 rounded-lg bg-card border border focus:outline-none focus:border-cyan-400/50 text-sm transition"
                  />
                  <div className="text-[11px] text-placeholder mt-1">模型能处理的最大上下文 token 数</div>
                </div>

                {/* 最大输出令牌数 */}
                <div className="p-4 bg-hover/50 rounded-xl">
                  <label className="block text-sm font-medium text-tertiary mb-2">
                    📤 最大输出令牌数
                    <span className="text-placeholder ml-2">当前: {llmConfig.max_output_tokens}</span>
                  </label>
                  <input
                    type="number"
                    min={128}
                    max={16384}
                    step={128}
                    value={llmConfig.max_output_tokens}
                    onChange={e => setLlmConfig(c => ({ ...c, max_output_tokens: parseInt(e.target.value) || 2048 }))}
                    className="w-full px-3 py-2 rounded-lg bg-card border border focus:outline-none focus:border-cyan-400/50 text-sm transition"
                  />
                  <div className="text-[11px] text-placeholder mt-1">模型单次响应的最大 token 数</div>
                </div>

                {/* 思考推理等级 */}
                <div className="p-4 bg-hover/50 rounded-xl">
                  <label className="block text-sm font-medium text-tertiary mb-2">
                    🧠 思考推理等级
                    <span className="text-placeholder ml-2">当前: {llmConfig.thinking_level}</span>
                  </label>
                  <select
                    value={llmConfig.thinking_level}
                    onChange={e => setLlmConfig(c => ({ ...c, thinking_level: parseInt(e.target.value) }))}
                    className="w-full px-3 py-2 rounded-lg bg-card border border focus:outline-none focus:border-cyan-400/50 text-sm transition"
                  >
                    <option value={0}>0 - 关闭思考</option>
                    <option value={1}>1 - 简单思考</option>
                    <option value={2}>2 - 标准思考</option>
                    <option value={3}>3 - 深度思考</option>
                    <option value={4}>4 - 高级思考</option>
                    <option value={5}>5 - 极致思考</option>
                  </select>
                  <div className="text-[11px] text-placeholder mt-1">控制模型思考深度，越高越耗时</div>
                </div>
              </div>

              {/* 滑块类参数 - 温度和 top_p */}
              <div className="grid md:grid-cols-2 gap-4">
                {/* 温度系数 */}
                <div className="p-4 bg-hover/50 rounded-xl">
                  <label className="block text-sm font-medium text-tertiary mb-3">
                    🌡️ 温度系数 (Temperature)
                    <span className="text-placeholder ml-2">{llmConfig.temperature.toFixed(2)}</span>
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={llmConfig.temperature}
                    onChange={e => setLlmConfig(c => ({ ...c, temperature: parseFloat(e.target.value) }))}
                    className="w-full h-2 rounded-lg appearance-none cursor-pointer bg-hover accent-cyan-400"
                  />
                  <div className="flex justify-between text-[11px] text-placeholder mt-1">
                    <span>0.0 - 确定性输出</span>
                    <span>1.0 - 高度随机</span>
                  </div>
                </div>

                {/* 顶部P值 */}
                <div className="p-4 bg-hover/50 rounded-xl">
                  <label className="block text-sm font-medium text-tertiary mb-3">
                    🎯 顶部P值 (Top P)
                    <span className="text-placeholder ml-2">{llmConfig.top_p.toFixed(2)}</span>
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={llmConfig.top_p}
                    onChange={e => setLlmConfig(c => ({ ...c, top_p: parseFloat(e.target.value) }))}
                    className="w-full h-2 rounded-lg appearance-none cursor-pointer bg-hover accent-cyan-400"
                  />
                  <div className="flex justify-between text-[11px] text-placeholder mt-1">
                    <span>0.0 - 严格筛选</span>
                    <span>1.0 - 多样化输出</span>
                  </div>
                </div>
              </div>

              {/* 频率惩罚和存在惩罚 */}
              <div className="grid md:grid-cols-2 gap-4">
                {/* 频率惩罚 */}
                <div className="p-4 bg-hover/50 rounded-xl">
                  <label className="block text-sm font-medium text-tertiary mb-3">
                    🚫 频率惩罚 (Frequency Penalty)
                    <span className="text-placeholder ml-2">{llmConfig.frequency_penalty.toFixed(2)}</span>
                  </label>
                  <input
                    type="range"
                    min={-2}
                    max={2}
                    step={0.1}
                    value={llmConfig.frequency_penalty}
                    onChange={e => setLlmConfig(c => ({ ...c, frequency_penalty: parseFloat(e.target.value) }))}
                    className="w-full h-2 rounded-lg appearance-none cursor-pointer bg-hover accent-cyan-400"
                  />
                  <div className="flex justify-between text-[11px] text-placeholder mt-1">
                    <span>-2.0 - 鼓励重复</span>
                    <span>2.0 - 减少重复</span>
                  </div>
                </div>

                {/* 存在惩罚 */}
                <div className="p-4 bg-hover/50 rounded-xl">
                  <label className="block text-sm font-medium text-tertiary mb-3">
                    ➕ 存在惩罚 (Presence Penalty)
                    <span className="text-placeholder ml-2">{llmConfig.presence_penalty.toFixed(2)}</span>
                  </label>
                  <input
                    type="range"
                    min={-2}
                    max={2}
                    step={0.1}
                    value={llmConfig.presence_penalty}
                    onChange={e => setLlmConfig(c => ({ ...c, presence_penalty: parseFloat(e.target.value) }))}
                    className="w-full h-2 rounded-lg appearance-none cursor-pointer bg-hover accent-cyan-400"
                  />
                  <div className="flex justify-between text-[11px] text-placeholder mt-1">
                    <span>-2.0 - 鼓励旧主题</span>
                    <span>2.0 - 鼓励新主题</span>
                  </div>
                </div>
              </div>

              {/* 超时和重试 */}
              <div className="grid md:grid-cols-2 gap-4">
                {/* 响应超时时间 */}
                <div className="p-4 bg-hover/50 rounded-xl">
                  <label className="block text-sm font-medium text-tertiary mb-2">
                    ⏱️ 响应超时时间
                    <span className="text-placeholder ml-2">{llmConfig.response_timeout} 秒</span>
                  </label>
                  <input
                    type="number"
                    min={5}
                    max={600}
                    step={5}
                    value={llmConfig.response_timeout}
                    onChange={e => setLlmConfig(c => ({ ...c, response_timeout: parseInt(e.target.value) || 60 }))}
                    className="w-full px-3 py-2 rounded-lg bg-card border border focus:outline-none focus:border-cyan-400/50 text-sm transition"
                  />
                  <div className="text-[11px] text-placeholder mt-1">API 调用的最大等待时间</div>
                </div>

                {/* API 重试次数 */}
                <div className="p-4 bg-hover/50 rounded-xl">
                  <label className="block text-sm font-medium text-tertiary mb-2">
                    🔄 API 调用重试次数
                    <span className="text-placeholder ml-2">{llmConfig.api_retry_count} 次</span>
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={10}
                    value={llmConfig.api_retry_count}
                    onChange={e => setLlmConfig(c => ({ ...c, api_retry_count: parseInt(e.target.value) || 2 }))}
                    className="w-full px-3 py-2 rounded-lg bg-card border border focus:outline-none focus:border-cyan-400/50 text-sm transition"
                  />
                  <div className="text-[11px] text-placeholder mt-1">请求失败时的自动重试次数</div>
                </div>
              </div>

              {/* 布尔开关 */}
              <div className="grid md:grid-cols-2 gap-4">
                {/* 多模态输入 */}
                <div className="p-4 bg-hover/50 rounded-xl flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-primary">🖼️ 多模态输入</div>
                    <div className="text-[11px] text-placeholder mt-0.5">允许模型接收图片等非文本输入</div>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={llmConfig.is_multimodal_input}
                      onChange={e => setLlmConfig(c => ({ ...c, is_multimodal_input: e.target.checked }))}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-hover peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-gradient-to-r from-brand to-brand-700"></div>
                  </label>
                </div>

                {/* 嵌入模型 */}
                <div className="p-4 bg-hover/50 rounded-xl flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-primary">📊 嵌入模型</div>
                    <div className="text-[11px] text-placeholder mt-0.5">当前模型是否为 embedding 模型</div>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={llmConfig.is_embedding_model}
                      onChange={e => setLlmConfig(c => ({ ...c, is_embedding_model: e.target.checked }))}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-hover peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-gradient-to-r from-brand to-brand-700"></div>
                  </label>
                </div>
              </div>
            </div>

            <div className="mt-6 p-3 bg-warning/10 border border-warning/30 rounded-lg">
              <div className="flex items-start gap-2">
                <span className="text-lg">⚠️</span>
                <div className="text-sm text-warning">
                  <div className="font-medium">注意</div>
                  <div className="text-placeholder mt-1">部分配置修改后需要重启应用才能生效。建议在修改前备份当前配置。</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 主题设置 */}
      {tab === 'theme' && (
        <div className="space-y-6">
          <div className="bg-card border border rounded-xl p-6">
            <h2 className="text-lg font-bold mb-6">🎨 主题配色</h2>

            <div className="grid md:grid-cols-2 gap-6">
              {/* 夜晚主题 */}
              <div
                onClick={() => toggleTheme('dark')}
                className={`relative rounded-xl overflow-hidden cursor-pointer transition transform hover:scale-[1.02] ${
                  theme === 'dark' ? 'ring-2 ring-cyan-400' : ''
                }`}
              >
                <div className="h-40 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 relative">
                  {/* 预览内容 */}
                  <div className="absolute inset-4 space-y-3">
                    <div className="flex gap-2">
                      <div className="w-16 h-6 bg-slate-700 rounded"></div>
                      <div className="flex-1 h-6 bg-slate-700 rounded"></div>
                    </div>
                    <div className="flex gap-2">
                      <div className="flex-1 h-4 bg-slate-600 rounded"></div>
                      <div className="flex-1 h-4 bg-slate-600 rounded"></div>
                      <div className="flex-1 h-4 bg-slate-600 rounded"></div>
                    </div>
                    <div className="flex gap-2">
                      <div className="w-20 h-8 bg-gradient-to-r from-cyan-600 to-blue-600 rounded"></div>
                      <div className="w-20 h-8 bg-slate-700 rounded"></div>
                    </div>
                  </div>
                  {/* 月亮图标 */}
                  <div className="absolute top-4 right-4 text-4xl">🌙</div>
                </div>
                <div className="p-4 bg-card border-t border">
                  <div className="font-medium">夜晚主题</div>
                  <div className="text-sm text-placeholder">适合低光环境使用，护眼舒适</div>
                  {theme === 'dark' && (
                    <div className="mt-2 px-2 py-1 bg-cyan-500/20 text-cyan-400 text-xs rounded inline-flex items-center gap-1">
                      ✅ 当前使用
                    </div>
                  )}
                </div>
              </div>

              {/* 白天主题 */}
              <div
                onClick={() => toggleTheme('light')}
                className={`relative rounded-xl overflow-hidden cursor-pointer transition transform hover:scale-[1.02] ${
                  theme === 'light' ? 'ring-2 ring-cyan-400' : ''
                }`}
              >
                <div className="h-40 bg-gradient-to-br from-slate-100 via-white to-slate-100 relative">
                  {/* 预览内容 */}
                  <div className="absolute inset-4 space-y-3">
                    <div className="flex gap-2">
                      <div className="w-16 h-6 bg-slate-200 rounded"></div>
                      <div className="flex-1 h-6 bg-slate-200 rounded"></div>
                    </div>
                    <div className="flex gap-2">
                      <div className="flex-1 h-4 bg-slate-300 rounded"></div>
                      <div className="flex-1 h-4 bg-slate-300 rounded"></div>
                      <div className="flex-1 h-4 bg-slate-300 rounded"></div>
                    </div>
                    <div className="flex gap-2">
                      <div className="w-20 h-8 bg-gradient-to-r from-cyan-500 to-blue-500 rounded"></div>
                      <div className="w-20 h-8 bg-slate-200 rounded"></div>
                    </div>
                  </div>
                  {/* 太阳图标 */}
                  <div className="absolute top-4 right-4 text-4xl">☀️</div>
                </div>
                <div className="p-4 bg-card border-t border">
                  <div className="font-medium">白天主题</div>
                  <div className="text-sm text-placeholder">适合明亮环境使用，清晰清爽</div>
                  {theme === 'light' && (
                    <div className="mt-2 px-2 py-1 bg-cyan-500/20 text-cyan-400 text-xs rounded inline-flex items-center gap-1">
                      ✅ 当前使用
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="mt-6 p-3 bg-info/10 border border-info/30 rounded-lg">
              <div className="flex items-start gap-2">
                <span className="text-lg">💡</span>
                <div className="text-sm text-info">
                  主题设置会自动保存到本地，刷新页面后依然保持。切换主题不需要重启应用。
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 系统配置 */}
      {tab === 'config' && (
        <div className="space-y-6">
          <div className="bg-card border border rounded-xl p-6">
            <h2 className="text-lg font-bold mb-6">⚙️ 系统配置</h2>

            <div className="grid md:grid-cols-2 gap-4">
              <div className="p-4 bg-hover/50 rounded-xl">
                <div className="text-xs text-placeholder uppercase tracking-wider mb-1">应用名称</div>
                <div className="text-sm font-medium">AgentRAG Platform</div>
              </div>
              <div className="p-4 bg-hover/50 rounded-xl">
                <div className="text-xs text-placeholder uppercase tracking-wider mb-1">版本号</div>
                <div className="text-sm font-medium">0.2.0</div>
              </div>
              <div className="p-4 bg-hover/50 rounded-xl">
                <div className="text-xs text-placeholder uppercase tracking-wider mb-1">环境</div>
                <div className="text-sm font-medium">Development</div>
              </div>
              <div className="p-4 bg-hover/50 rounded-xl">
                <div className="text-xs text-placeholder uppercase tracking-wider mb-1">最大上传</div>
                <div className="text-sm font-medium">50 MB</div>
              </div>
            </div>

            <div className="mt-6">
              <h3 className="text-sm font-medium text-tertiary mb-3">配置导入/导出</h3>
              <div className="flex gap-3">
                <button className="px-4 py-2 rounded-lg bg-hover hover:bg-active text-sm transition">
                  📥 导出配置
                </button>
                <button className="px-4 py-2 rounded-lg bg-gradient-to-r from-brand to-brand-700 text-sm font-medium hover:opacity-90 transition">
                  📤 导入配置
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
