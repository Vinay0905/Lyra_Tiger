import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Keyboard,
  Send,
  Terminal,
  ChevronUp,
  ChevronDown,
  Command,
  Clock,
  Settings as SettingsIcon,
  X,
} from 'lucide-react'
import { useAppStore } from './store/useAppStore'
import { OrbVisualizer } from './components/OrbVisualizer'
import { Transcript } from './components/Transcript'
import { CommandPalette } from './components/CommandPalette'
import { SettingsPanel } from './components/SettingsPanel'
import { HistoryDrawer } from './components/HistoryDrawer'
import { useWindowResizer } from './hooks/useWindowResizer'
import { useVoiceCapture } from './hooks/useVoiceCapture'
import { useSpeechPlayer } from './hooks/useSpeechPlayer'
import { useCommandStream } from './hooks/useCommandStream'
import { useConnectionHealth } from './hooks/useConnectionHealth'

const GLOW_CONFIG = {
  idle:      'radial-gradient(ellipse at 50% 40%, rgba(0,100,255,0.16) 0%, transparent 70%)',
  listening: 'radial-gradient(ellipse at 50% 40%, rgba(0,220,255,0.20) 0%, transparent 65%)',
  thinking:  'radial-gradient(ellipse at 50% 40%, rgba(80,80,255,0.16) 0%, transparent 70%)',
  speaking:  'radial-gradient(ellipse at 50% 40%, rgba(30,120,255,0.20) 0%, transparent 65%)',
  error:     'radial-gradient(ellipse at 50% 40%, rgba(200,30,30,0.18) 0%, transparent 70%)',
}

const panelVariants = {
  hidden:  { opacity: 0, y: -10, scale: 0.97 },
  visible: { opacity: 1, y: 0, scale: 1,
    transition: { type: 'spring' as const, damping: 28, stiffness: 300, duration: 0.25 } },
  exit:    { opacity: 0, y: -10, scale: 0.97, transition: { duration: 0.15, ease: 'easeIn' as const } },
}

const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

async function hideWindow() {
  if (!isTauri) return
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window')
    await getCurrentWindow().hide()
  } catch (err) { console.error('hide error', err) }
}

function App() {
  useWindowResizer()
  useConnectionHealth()

  const { enqueueSpeech, playSpeech, interrupt, unlockAudio } = useSpeechPlayer()
  const { isRecording, startRecording, stopRecording } = useVoiceCapture(enqueueSpeech, interrupt)
  const { sendCommand, confirmAction } = useCommandStream()

  const {
    orbState,
    connection,
    isMuted,
    isSpeakerActive,
    auditLogs,
    toggleMute,
    toggleSpeaker,
    clearLogs,
  } = useAppStore()

  const [textInput, setTextInput] = useState('')
  const [showTextDrawer, setShowTextDrawer] = useState(false)
  const [showLogsDrawer, setShowLogsDrawer] = useState(false)
  const [showPalette, setShowPalette] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [caretX, setCaretX] = useState<number | null>(null)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [auditLogs, showLogsDrawer])

  // ── Global keyboard: Cmd/Ctrl+K palette, Esc dismiss (U1) ─────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        unlockAudio()
        setShowPalette((v) => !v)
      } else if (e.key === 'Escape') {
        if (showPalette) setShowPalette(false)
        else if (showSettings) setShowSettings(false)
        else if (showHistory) setShowHistory(false)
        else if (showTextDrawer) setShowTextDrawer(false)
        else void hideWindow()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [showPalette, showSettings, showHistory, showTextDrawer, unlockAudio])

  // ── Auto-focus the input whenever the popover is summoned (U1) ────────────
  useEffect(() => {
    if (!isTauri) return
    let unlisten: (() => void) | undefined
    ;(async () => {
      try {
        const { getCurrentWindow } = await import('@tauri-apps/api/window')
        unlisten = await getCurrentWindow().onFocusChanged(({ payload: focused }) => {
          if (focused) {
            unlockAudio()
            setShowTextDrawer(true)
            setTimeout(() => inputRef.current?.focus(), 60)
          }
        })
      } catch (err) { console.error('focus listener error', err) }
    })()
    return () => { if (unlisten) unlisten() }
  }, [unlockAudio])

  // ── Caret alignment: Rust emits where the tray icon sits (UN1) ────────────
  useEffect(() => {
    if (!isTauri) return
    let unlisten: (() => void) | undefined
    ;(async () => {
      try {
        const { getCurrentWindow } = await import('@tauri-apps/api/window')
        unlisten = await getCurrentWindow().listen<number>('tray-caret', ({ payload }) => {
          if (typeof payload === 'number' && isFinite(payload)) setCaretX(payload)
        })
      } catch (err) { console.error('caret listener error', err) }
    })()
    return () => { if (unlisten) unlisten() }
  }, [])

  useEffect(() => {
    if (showTextDrawer) setTimeout(() => inputRef.current?.focus(), 40)
  }, [showTextDrawer])

  const handleTextSubmit = () => {
    const query = textInput.trim()
    if (!query) return
    setTextInput('')
    void sendCommand(query)
  }

  const handleVoiceTrigger = () => {
    unlockAudio()
    if (isRecording) stopRecording()
    else startRecording()
  }

  // Connection state (UN3) supersedes the orb status when the backend is unhealthy.
  const connectionDown = connection === 'disconnected' || connection === 'degraded'
  const statusColor = connectionDown
    ? (connection === 'disconnected' ? 'bg-rose-500' : 'bg-amber-400')
    : { idle: 'bg-emerald-400', listening: 'bg-cyan-400', thinking: 'bg-indigo-400',
        speaking: 'bg-blue-400', error: 'bg-rose-500' }[orbState]

  const statusLabel = connection === 'disconnected'
    ? 'Offline'
    : connection === 'degraded'
    ? 'Reconnecting'
    : connection === 'connecting'
    ? 'Connecting'
    : orbState === 'idle'
    ? 'Ready'
    : orbState.charAt(0).toUpperCase() + orbState.slice(1)

  return (
    <div className="w-full h-full relative select-none overflow-hidden flex flex-col items-center pt-[10px]">
      {/* Caret points up at the tray icon; x-offset is emitted by Rust (UN1).
          Falls back to horizontal centering when no anchor is known yet. */}
      <div
        style={{
          position: caretX === null ? 'relative' : 'absolute',
          left: caretX === null ? undefined : Math.max(12, Math.min(caretX - 10, 338)),
          top: caretX === null ? undefined : 0,
          width: 0, height: 0,
          borderLeft: '10px solid transparent', borderRight: '10px solid transparent',
          borderBottom: '10px solid rgb(var(--lyra-surface-2) / 0.95)', flexShrink: 0,
          transition: 'left 0.18s ease',
          zIndex: 30,
        }}
      />

      <motion.div
        key="panel"
        variants={panelVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="w-full flex-1 flex flex-col rounded-2xl overflow-hidden"
        style={{
          background: 'rgb(var(--lyra-surface) / var(--lyra-panel-alpha))',
          border: '1px solid rgb(var(--lyra-border) / var(--lyra-border-alpha))',
          boxShadow: 'var(--lyra-elevation)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
        }}
      >
        <div
          className="absolute inset-0 pointer-events-none rounded-2xl transition-all duration-700"
          style={{ background: GLOW_CONFIG[orbState] }}
        />

        {/* Header */}
        <div
          data-tauri-drag-region
          className="flex items-center justify-between px-4 py-3 z-10 relative border-b border-white/[0.06] cursor-move select-none"
        >
          <span className="text-sm font-semibold tracking-widest text-white/80 uppercase">Lyra</span>

          <div
            data-tauri-no-drag
            className="flex items-center gap-1.5 bg-black/40 border border-white/[0.07] px-3 py-1 rounded-full text-[11px] font-medium text-neutral-300 cursor-default"
          >
            <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${statusColor}`} />
            <span>{statusLabel}</span>
          </div>

          <div className="flex items-center gap-1" data-tauri-no-drag>
            <button
              onClick={() => setShowHistory(true)}
              className="p-1.5 rounded-full hover:bg-white/8 text-neutral-500 hover:text-white transition-colors"
              title="History"
            >
              <Clock size={14} />
            </button>
            <button
              onClick={() => { unlockAudio(); setShowPalette(true) }}
              className="p-1.5 rounded-full hover:bg-white/8 text-neutral-500 hover:text-white transition-colors"
              title="Command palette (⌘K)"
            >
              <Command size={14} />
            </button>
            <button
              onClick={() => setShowSettings(true)}
              className="p-1.5 rounded-full hover:bg-white/8 text-neutral-500 hover:text-white transition-colors"
              title="Settings"
            >
              <SettingsIcon size={14} />
            </button>
            <button
              onClick={hideWindow}
              className="p-1.5 rounded-full hover:bg-white/8 text-neutral-500 hover:text-white transition-colors"
              title="Hide (⌥Space to reopen)"
            >
              <X size={15} />
            </button>
          </div>
        </div>

        {/* Centre: Orb + Transcript */}
        <div className="flex-1 flex flex-col items-center justify-center overflow-hidden z-10 relative px-2 py-2 gap-2">
          <div style={{ width: 110, height: 110, flexShrink: 0 }}>
            <OrbVisualizer width={110} height={110} />
          </div>
          <Transcript
            onConfirm={(id, action, approve) => confirmAction(id, action, approve)}
            onSpeakAgain={(text) => { unlockAudio(); playSpeech(text) }}
            onRegenerate={(text) => text && sendCommand(text)}
          />
        </div>

        {/* Bottom controls */}
        <div className="flex items-center justify-between w-full px-5 pb-4 pt-2 z-10 relative">
          <button
            onClick={toggleMute}
            className={`p-3 rounded-full border transition-all ${
              isMuted ? 'bg-rose-950/40 border-rose-800/50 text-rose-400'
                      : 'bg-white/[0.04] border-white/10 text-neutral-400 hover:text-white hover:bg-white/8'
            }`}
            title={isMuted ? 'Unmute Mic' : 'Mute Mic'}
          >
            {isMuted ? <MicOff size={18} /> : <Mic size={18} />}
          </button>

          <button
            onClick={handleVoiceTrigger}
            className={`w-[56px] h-[56px] rounded-full flex items-center justify-center shadow-lg transition-all duration-200 ${
              orbState === 'listening'
                ? 'bg-cyan-500 ring-2 ring-cyan-400/40 ring-offset-2 ring-offset-black animate-pulse'
                : 'bg-white hover:bg-neutral-100'
            }`}
            title="Click to Speak"
          >
            {orbState === 'listening' ? (
              <div className="flex gap-[3px] items-center">
                <span className="w-1 h-4 bg-white rounded-full animate-bounce" style={{ animationDelay: '0s' }} />
                <span className="w-1 h-6 bg-white rounded-full animate-bounce" style={{ animationDelay: '0.15s' }} />
                <span className="w-1 h-4 bg-white rounded-full animate-bounce" style={{ animationDelay: '0.3s' }} />
              </div>
            ) : (
              <div className="flex gap-[3px] items-center">
                <span className="w-[3px] h-3 bg-neutral-900 rounded-full" />
                <span className="w-[3px] h-4.5 bg-neutral-900 rounded-full" />
                <span className="w-[3px] h-3 bg-neutral-900 rounded-full" />
              </div>
            )}
          </button>

          <div className="flex gap-2">
            <button
              onClick={() => { unlockAudio(); setShowTextDrawer(!showTextDrawer) }}
              className={`p-3 rounded-full border transition-all ${
                showTextDrawer ? 'bg-blue-950/40 border-blue-700/40 text-blue-400'
                               : 'bg-white/[0.04] border-white/10 text-neutral-400 hover:text-white hover:bg-white/8'
              }`}
              title="Type a command"
            >
              <Keyboard size={18} />
            </button>
            <button
              onClick={toggleSpeaker}
              className={`p-3 rounded-full border transition-all ${
                !isSpeakerActive ? 'bg-rose-950/40 border-rose-800/50 text-rose-400'
                                 : 'bg-white/[0.04] border-white/10 text-neutral-400 hover:text-white hover:bg-white/8'
              }`}
              title={isSpeakerActive ? 'Mute Speaker' : 'Unmute Speaker'}
            >
              {isSpeakerActive ? <Volume2 size={18} /> : <VolumeX size={18} />}
            </button>
          </div>
        </div>

        {/* Keyboard drawer */}
        <AnimatePresence>
          {showTextDrawer && (
            <motion.div
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 30, stiffness: 260 }}
              className="absolute bottom-0 left-0 w-full bg-neutral-950/98 border-t border-white/8 p-4 z-20 flex flex-col gap-2 rounded-t-2xl"
            >
              <div className="flex justify-between items-center text-[10px] text-neutral-500 px-1">
                <span>Keyboard Input</span>
                <button onClick={() => setShowTextDrawer(false)} className="hover:text-neutral-200 transition-colors">Close</button>
              </div>
              <div className="flex gap-2">
                <input
                  ref={inputRef}
                  type="text"
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleTextSubmit()}
                  placeholder="Type a command…"
                  className="flex-1 bg-neutral-900 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-neutral-100 outline-none focus:border-blue-500/50 transition-colors"
                />
                <button
                  onClick={handleTextSubmit}
                  className="bg-white text-black font-semibold rounded-xl px-4 py-2 hover:bg-neutral-200 transition-colors"
                >
                  <Send size={15} />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Logs drawer */}
        <div className="absolute right-4 top-[52px] z-10 flex flex-col items-end">
          <button
            onClick={() => setShowLogsDrawer(!showLogsDrawer)}
            className="bg-black/50 border border-white/10 p-1.5 rounded-full text-neutral-500 hover:text-white transition-all flex items-center gap-1"
          >
            <Terminal size={11} />
            {showLogsDrawer ? <ChevronUp size={9} /> : <ChevronDown size={9} />}
          </button>

          <AnimatePresence>
            {showLogsDrawer && (
              <motion.div
                initial={{ opacity: 0, y: -8, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -8, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className="w-[200px] max-h-[130px] mt-2 bg-black/96 border border-white/8 rounded-xl p-3 shadow-xl overflow-y-auto text-[10px] font-mono text-neutral-400 flex flex-col gap-1"
                style={{ scrollbarWidth: 'none' }}
              >
                <div className="flex justify-between items-center border-b border-white/8 pb-1 mb-1 text-neutral-500 text-[9px] uppercase tracking-wider">
                  <span>Audit Trace</span>
                  <button onClick={clearLogs} className="hover:text-neutral-200">Clear</button>
                </div>
                {auditLogs.map((log, i) => (
                  <p key={i} className="leading-relaxed break-all">{log}</p>
                ))}
                <div ref={logsEndRef} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Overlays */}
        <AnimatePresence>
          {showPalette && (
            <CommandPalette
              onClose={() => setShowPalette(false)}
              onSend={(q) => sendCommand(q)}
              onOpenSettings={() => { setShowPalette(false); setShowSettings(true) }}
            />
          )}
        </AnimatePresence>
        <AnimatePresence>
          {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}
        </AnimatePresence>
        <AnimatePresence>
          {showHistory && (
            <HistoryDrawer
              onClose={() => setShowHistory(false)}
              onReuse={(q) => sendCommand(q)}
            />
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}

export default App
