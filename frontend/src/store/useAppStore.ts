import { create } from 'zustand'

export type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'error'

interface AppState {
  orbState: OrbState
  isMuted: boolean
  isSpeakerActive: boolean
  isExpanded: boolean
  volumeLevel: number
  auditLogs: string[]
  commandReply: string
  setOrbState: (state: OrbState) => void
  toggleMute: () => void
  toggleSpeaker: () => void
  setExpanded: (expanded: boolean) => void
  setVolumeLevel: (level: number) => void
  addAuditLog: (log: string) => void
  setCommandReply: (reply: string) => void
  clearLogs: () => void
}

export const useAppStore = create<AppState>((set) => ({
  orbState: 'idle',
  isMuted: false,
  isSpeakerActive: true,
  isExpanded: false,
  volumeLevel: 0,
  auditLogs: ['[System] Lyra Interface Booted.'],
  commandReply: 'Resonance active. Ready to assist.',

  setOrbState: (orbState) => set({ orbState }),
  toggleMute: () => set((state) => ({ isMuted: !state.isMuted })),
  toggleSpeaker: () => set((state) => ({ isSpeakerActive: !state.isSpeakerActive })),
  setExpanded: (isExpanded) => set({ isExpanded }),
  setVolumeLevel: (volumeLevel) => set({ volumeLevel }),
  addAuditLog: (log) =>
    set((state) => ({
      auditLogs: [...state.auditLogs, `[${new Date().toLocaleTimeString()}] ${log}`],
    })),
  setCommandReply: (commandReply) => set({ commandReply }),
  clearLogs: () => set({ auditLogs: [`[${new Date().toLocaleTimeString()}] Logs Cleared.`] }),
}))
