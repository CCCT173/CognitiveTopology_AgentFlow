import { create } from 'zustand'
import { metaApi, LoaderOpt, ArchOpt, ToolOpt } from '@/api'

interface MetaState {
  loaded: boolean
  providers: any
  loaders: LoaderOpt[]
  splitters: { key: string; label: string }[]
  architectures: ArchOpt[]
  frameworks: { key: string; label: string }[]
  tools: ToolOpt[]
  config: { max_upload_mb: number; password_min_len: number; app_name: string; version: string }
  load: () => Promise<void>
}

export const useMetaStore = create<MetaState>((set) => ({
  loaded: false,
  providers: null,
  loaders: [],
  splitters: [],
  architectures: [],
  frameworks: [],
  tools: [],
  config: { max_upload_mb: 50, password_min_len: 6, app_name: 'AgentRAG', version: '0.1.0' },
  load: async () => {
    const [providers, loaders, splitters, architectures, frameworks, tools, config] = await Promise.all([
      metaApi.providers(), metaApi.loaders(), metaApi.splitters(),
      metaApi.architectures(), metaApi.frameworks(), metaApi.tools(), metaApi.config(),
    ])
    set({ providers, loaders, splitters, architectures, frameworks, tools, config, loaded: true })
  },
}))
