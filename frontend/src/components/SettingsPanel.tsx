import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { X } from 'lucide-react'
import { useSettingsStore } from '../store/useSettingsStore'

const VOICES = ['af_sarah', 'af_bella', 'af_nicole', 'am_adam', 'am_michael', 'bf_emma']

function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={`w-9 h-5 rounded-full transition-colors relative ${value ? 'bg-blue-500' : 'bg-neutral-700'}`}
    >
      <span
        className={`absolute top-0.5 w-4 h-4 bg-white rounded-full transition-all ${value ? 'left-4' : 'left-0.5'}`}
      />
    </button>
  )
}

export function SettingsPanel({ onClose }: { onClose: () => void }) {
  const s = useSettingsStore()
  const [mics, setMics] = useState<MediaDeviceInfo[]>([])

  useEffect(() => {
    navigator.mediaDevices
      ?.enumerateDevices()
      .then((devs) => setMics(devs.filter((d) => d.kind === 'audioinput')))
      .catch(() => setMics([]))
  }, [])

  return (
    <div className="absolute inset-0 z-40 flex items-stretch" style={{ background: 'rgba(0,0,0,0.5)' }} onClick={onClose}>
      <motion.div
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 30, stiffness: 300 }}
        className="ml-auto w-[280px] h-full bg-neutral-950/98 border-l border-white/10 p-4 overflow-y-auto flex flex-col gap-4"
        style={{ scrollbarWidth: 'none' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-widest text-neutral-300">Settings</span>
          <button onClick={onClose} className="text-neutral-500 hover:text-white"><X size={15} /></button>
        </div>

        <Field label="Backend URL">
          <input
            value={s.backendUrl}
            onChange={(e) => s.setBackendUrl(e.target.value)}
            className="w-full bg-neutral-900 border border-white/10 rounded-lg px-2.5 py-1.5 text-[12px] text-neutral-100 outline-none focus:border-blue-500/50"
          />
        </Field>

        <Field label="Microphone">
          <select
            value={s.micDeviceId ?? ''}
            onChange={(e) => s.setMicDeviceId(e.target.value || null)}
            className="w-full bg-neutral-900 border border-white/10 rounded-lg px-2.5 py-1.5 text-[12px] text-neutral-100 outline-none"
          >
            <option value="">System default</option>
            {mics.map((m) => (
              <option key={m.deviceId} value={m.deviceId}>
                {m.label || `Microphone ${m.deviceId.slice(0, 6)}`}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Voice">
          <select
            value={s.voice}
            onChange={(e) => s.setVoice(e.target.value)}
            className="w-full bg-neutral-900 border border-white/10 rounded-lg px-2.5 py-1.5 text-[12px] text-neutral-100 outline-none"
          >
            {VOICES.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </Field>

        <Row label="Streaming replies"><Toggle value={s.streamingEnabled} onChange={s.setStreamingEnabled} /></Row>
        <Row label="Spoken replies (TTS)"><Toggle value={s.ttsEnabled} onChange={s.setTtsEnabled} /></Row>
        <Row label="Allow screen capture"><Toggle value={s.screenCaptureConsent} onChange={s.setScreenCaptureConsent} /></Row>

        <button
          onClick={() => { s.newSession(); onClose() }}
          className="mt-2 w-full bg-white/[0.06] hover:bg-white/[0.1] border border-white/10 rounded-lg py-2 text-[12px] text-neutral-200"
        >
          Start new session
        </button>

        <p className="text-[10px] text-neutral-600 leading-relaxed mt-1">
          Session: <span className="font-mono">{s.sessionId.slice(0, 8)}</span>. Voice selection takes
          effect for newly synthesized speech.
        </p>
      </motion.div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wider text-neutral-500">{label}</span>
      {children}
    </label>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[12px] text-neutral-300">{label}</span>
      {children}
    </div>
  )
}
