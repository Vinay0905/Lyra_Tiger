import { create } from 'zustand'
import { persist } from 'zustand/middleware'

function makeSessionId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `sess-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export interface SettingsState {
  backendUrl: string
  sessionId: string
  micDeviceId: string | null
  voice: string
  streamingEnabled: boolean
  ttsEnabled: boolean
  screenCaptureConsent: boolean

  setBackendUrl: (url: string) => void
  setMicDeviceId: (id: string | null) => void
  setVoice: (voice: string) => void
  setStreamingEnabled: (v: boolean) => void
  setTtsEnabled: (v: boolean) => void
  setScreenCaptureConsent: (v: boolean) => void
  newSession: () => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      backendUrl: 'http://127.0.0.1:8000',
      sessionId: makeSessionId(),
      micDeviceId: null,
      voice: 'af_sarah',
      streamingEnabled: true,
      ttsEnabled: true,
      screenCaptureConsent: false,

      setBackendUrl: (backendUrl) => set({ backendUrl }),
      setMicDeviceId: (micDeviceId) => set({ micDeviceId }),
      setVoice: (voice) => set({ voice }),
      setStreamingEnabled: (streamingEnabled) => set({ streamingEnabled }),
      setTtsEnabled: (ttsEnabled) => set({ ttsEnabled }),
      setScreenCaptureConsent: (screenCaptureConsent) => set({ screenCaptureConsent }),
      newSession: () => set({ sessionId: makeSessionId() }),
    }),
    {
      name: 'lyra-settings',
      // sessionId is regenerated only when explicitly reset, otherwise persisted.
    },
  ),
)
