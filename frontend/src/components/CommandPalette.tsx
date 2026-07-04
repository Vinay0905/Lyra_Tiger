import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { Camera, Clipboard, Globe, MessageSquarePlus, Search, Settings as SettingsIcon } from 'lucide-react'
import { useAppStore } from '../store/useAppStore'
import { useSettingsStore } from '../store/useSettingsStore'

interface Action {
  id: string
  label: string
  hint?: string
  icon: ReactNode
  disabled?: boolean
  run: () => void
}

interface Props {
  onClose: () => void
  onSend: (query: string) => void
  onOpenSettings: () => void
}

export function CommandPalette({ onClose, onSend, onOpenSettings }: Props) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const { clearMessages } = useAppStore()
  const { screenCaptureConsent, newSession, streamingEnabled, setStreamingEnabled } =
    useSettingsStore()

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const baseActions: Action[] = useMemo(() => {
    return [
      {
        id: 'new-chat',
        label: 'New conversation',
        hint: 'Clear transcript + new session',
        icon: <MessageSquarePlus size={15} />,
        run: () => {
          clearMessages()
          newSession()
          onClose()
        },
      },
      {
        id: 'screenshot',
        label: 'Screenshot & explain',
        hint: screenCaptureConsent ? 'Analyze the current screen' : 'Enable screen capture in Settings',
        icon: <Camera size={15} />,
        disabled: !screenCaptureConsent,
        run: () => {
          onSend("What's on my screen right now? Explain it.")
          onClose()
        },
      },
      {
        id: 'clipboard',
        label: 'Read clipboard',
        hint: 'Summarize clipboard contents',
        icon: <Clipboard size={15} />,
        run: () => {
          onSend('Read my clipboard and summarize it.')
          onClose()
        },
      },
      {
        id: 'search',
        label: query.trim() ? `Search the web for “${query.trim()}”` : 'Search the web…',
        hint: 'Open a browser search',
        icon: <Globe size={15} />,
        run: () => {
          onSend(query.trim() ? `Search Google for ${query.trim()}` : 'Open Google')
          onClose()
        },
      },
      {
        id: 'toggle-stream',
        label: `${streamingEnabled ? 'Disable' : 'Enable'} streaming replies`,
        icon: <Search size={15} />,
        run: () => {
          setStreamingEnabled(!streamingEnabled)
          onClose()
        },
      },
      {
        id: 'settings',
        label: 'Open settings',
        icon: <SettingsIcon size={15} />,
        run: () => {
          onOpenSettings()
        },
      },
    ]
  }, [query, screenCaptureConsent, streamingEnabled, clearMessages, newSession, onClose, onSend, onOpenSettings, setStreamingEnabled])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const matches = baseActions.filter((a) => !q || a.label.toLowerCase().includes(q))
    // Always allow a free-form "Ask Lyra" fallback when typing.
    if (q) {
      matches.push({
        id: 'ask',
        label: `Ask Lyra: “${query.trim()}”`,
        icon: <MessageSquarePlus size={15} />,
        run: () => {
          onSend(query.trim())
          onClose()
        },
      })
    }
    return matches
  }, [baseActions, query, onSend, onClose])

  useEffect(() => {
    setActive(0)
  }, [query])

  const runActive = () => {
    const a = filtered[active]
    if (a && !a.disabled) a.run()
  }

  return (
    <div
      className="absolute inset-0 z-40 flex items-start justify-center pt-6 px-4"
      style={{ background: 'rgba(0,0,0,0.45)' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, y: -8, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.15 }}
        className="w-full bg-neutral-950/98 border border-white/10 rounded-2xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-3 py-2.5 border-b border-white/[0.06]">
          <Search size={14} className="text-neutral-500" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => Math.min(i + 1, filtered.length - 1)) }
              else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)) }
              else if (e.key === 'Enter') { e.preventDefault(); runActive() }
              else if (e.key === 'Escape') { e.preventDefault(); onClose() }
            }}
            placeholder="Type a command or ask Lyra…"
            className="flex-1 bg-transparent text-sm text-neutral-100 outline-none placeholder:text-neutral-600"
          />
          <kbd className="text-[9px] text-neutral-600 border border-white/10 rounded px-1">esc</kbd>
        </div>
        <div className="max-h-[200px] overflow-y-auto py-1" style={{ scrollbarWidth: 'none' }}>
          {filtered.map((a, i) => (
            <button
              key={a.id}
              disabled={a.disabled}
              onMouseEnter={() => setActive(i)}
              onClick={a.run}
              className={`w-full flex items-center gap-2.5 px-3 py-2 text-left text-[12.5px] transition-colors ${
                a.disabled
                  ? 'text-neutral-600 cursor-not-allowed'
                  : i === active
                  ? 'bg-white/[0.07] text-white'
                  : 'text-neutral-300 hover:bg-white/[0.04]'
              }`}
            >
              <span className="text-neutral-400">{a.icon}</span>
              <span className="flex-1">{a.label}</span>
              {a.hint && <span className="text-[10px] text-neutral-600">{a.hint}</span>}
            </button>
          ))}
        </div>
      </motion.div>
    </div>
  )
}
