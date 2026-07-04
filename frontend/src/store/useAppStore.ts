import { create } from 'zustand'

export type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'error'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  route?: string
  streaming?: boolean
}

function makeId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

interface AppState {
  orbState: OrbState
  isMuted: boolean
  isSpeakerActive: boolean
  isExpanded: boolean
  volumeLevel: number
  auditLogs: string[]
  messages: ChatMessage[]
  setOrbState: (state: OrbState) => void
  toggleMute: () => void
  toggleSpeaker: () => void
  setExpanded: (expanded: boolean) => void
  setVolumeLevel: (level: number) => void
  addAuditLog: (log: string) => void
  clearLogs: () => void

  // Transcript management (U2)
  addMessage: (role: ChatMessage['role'], content: string, opts?: Partial<ChatMessage>) => string
  appendToMessage: (id: string, delta: string) => void
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void
  clearMessages: () => void
}

export const useAppStore = create<AppState>((set) => ({
  orbState: 'idle',
  isMuted: false,
  isSpeakerActive: true,
  isExpanded: false,
  volumeLevel: 0,
  auditLogs: ['[System] Lyra Interface Booted.'],
  messages: [],

  setOrbState: (orbState) => set({ orbState }),
  toggleMute: () => set((state) => ({ isMuted: !state.isMuted })),
  toggleSpeaker: () => set((state) => ({ isSpeakerActive: !state.isSpeakerActive })),
  setExpanded: (isExpanded) => set({ isExpanded }),
  setVolumeLevel: (volumeLevel) => set({ volumeLevel }),
  addAuditLog: (log) =>
    set((state) => ({
      auditLogs: [...state.auditLogs, `[${new Date().toLocaleTimeString()}] ${log}`],
    })),
  clearLogs: () => set({ auditLogs: [`[${new Date().toLocaleTimeString()}] Logs Cleared.`] }),

  addMessage: (role, content, opts) => {
    const id = makeId()
    set((state) => ({
      messages: [...state.messages, { id, role, content, ...opts }],
    }))
    return id
  },
  appendToMessage: (id, delta) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, content: m.content + delta } : m,
      ),
    })),
  updateMessage: (id, patch) =>
    set((state) => ({
      messages: state.messages.map((m) => (m.id === id ? { ...m, ...patch } : m)),
    })),
  clearMessages: () => set({ messages: [] }),
}))
