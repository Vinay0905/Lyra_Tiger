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
  X,
} from 'lucide-react'
import { useAppStore } from './store/useAppStore'
import { OrbVisualizer } from './components/OrbVisualizer'
import { useWindowResizer } from './hooks/useWindowResizer'
import { useVoiceCapture } from './hooks/useVoiceCapture'
import { useSpeechPlayer } from './hooks/useSpeechPlayer'

// ─── Ambient glow config per state ────────────────────────────────────────────
const GLOW_CONFIG = {
  idle:      'radial-gradient(ellipse at 50% 40%, rgba(0,100,255,0.16) 0%, transparent 70%)',
  listening: 'radial-gradient(ellipse at 50% 40%, rgba(0,220,255,0.20) 0%, transparent 65%)',
  thinking:  'radial-gradient(ellipse at 50% 40%, rgba(80,80,255,0.16) 0%, transparent 70%)',
  speaking:  'radial-gradient(ellipse at 50% 40%, rgba(30,120,255,0.20) 0%, transparent 65%)',
  error:     'radial-gradient(ellipse at 50% 40%, rgba(200,30,30,0.18) 0%, transparent 70%)',
}

// ─── Panel entry animation ────────────────────────────────────────────────────
const panelVariants = {
  hidden:  { opacity: 0, y: -10, scale: 0.97 },
  visible: { opacity: 1, y: 0,   scale: 1,
    transition: { type: 'spring' as const, damping: 28, stiffness: 300, duration: 0.25 } },
  exit:    { opacity: 0, y: -10, scale: 0.97,
    transition: { duration: 0.15, ease: 'easeIn' as const } },
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
  // no-op since Rust owns the window now
  useWindowResizer()

  const { playSpeech, interrupt, unlockAudio } = useSpeechPlayer()
  const { isRecording, startRecording, stopRecording } = useVoiceCapture(playSpeech, interrupt)

  const {
    orbState,
    isMuted,
    isSpeakerActive,
    commandReply,
    auditLogs,
    setOrbState,
    toggleMute,
    toggleSpeaker,
    addAuditLog,
    setCommandReply,
    clearLogs,
  } = useAppStore()

  const [textInput, setTextInput]         = useState('')
  const [showTextDrawer, setShowTextDrawer]   = useState(false)
  const [showLogsDrawer, setShowLogsDrawer]   = useState(false)
  const logsEndRef        = useRef<HTMLDivElement>(null)
  const replyContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => { logsEndRef.current?.scrollIntoView({ behavior: 'smooth' }) },
    [auditLogs, showLogsDrawer])

  useEffect(() => {
    if (replyContainerRef.current) replyContainerRef.current.scrollTop = 0
  }, [commandReply])

  const handleTextSubmit = async () => {
    const query = textInput.trim()
    if (!query) return
    setTextInput('')
    unlockAudio()
    interrupt()
    setCommandReply(`"${query}"`)
    setOrbState('thinking')
    addAuditLog(`Sent: "${query}"`)

    try {
      const r = await fetch('http://127.0.0.1:8000/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: query }),
      })
      const data = await r.json()
      setCommandReply(data.reply)
      playSpeech(data.reply)
      addAuditLog(`Reply [${data.route}] received.`)
    } catch (err) {
      addAuditLog(`Error: ${err}`)
      setOrbState('error')
      setCommandReply('API connection failed.')
    }
  }

  const handleVoiceTrigger = () => {
    unlockAudio()
    if (isRecording) stopRecording()
    else startRecording()
  }

  const statusColor = {
    idle:      'bg-emerald-400',
    listening: 'bg-cyan-400',
    thinking:  'bg-indigo-400',
    speaking:  'bg-blue-400',
    error:     'bg-rose-500',
  }[orbState]

  const statusLabel = orbState === 'idle' ? 'Ready'
    : orbState.charAt(0).toUpperCase() + orbState.slice(1)

  return (
    // Full viewport — transparent background, click-through safe
    <div className="w-full h-full relative select-none overflow-hidden flex flex-col items-center pt-[10px]">

      {/* ── Notch / caret pointing up to the menu bar icon ────────────── */}
      <div
        style={{
          width: 0,
          height: 0,
          borderLeft: '10px solid transparent',
          borderRight: '10px solid transparent',
          borderBottom: '10px solid rgba(20,20,25,0.95)',
          flexShrink: 0,
        }}
      />

      {/* ── Main panel ──────────────────────────────────────────────────── */}
      <motion.div
        key="panel"
        variants={panelVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="w-full flex-1 flex flex-col rounded-2xl overflow-hidden"
        style={{
          background: 'rgba(12,12,16,0.96)',
          border: '1px solid rgba(255,255,255,0.08)',
          boxShadow: '0 24px 64px rgba(0,0,0,0.7)',
          backdropFilter: 'blur(24px)',
        }}
      >
        {/* Ambient glow overlay */}
        <div
          className="absolute inset-0 pointer-events-none rounded-2xl transition-all duration-700"
          style={{ background: GLOW_CONFIG[orbState] }}
        />

        {/* ── Header ──────────────────────────────────────────────────── */}
        <div
          data-tauri-drag-region
          className="flex items-center justify-between px-4 py-3 z-10 relative border-b border-white/[0.06] cursor-move select-none"
        >
          {/* Lyra wordmark */}
          <span className="text-sm font-semibold tracking-widest text-white/80 uppercase">
            Lyra
          </span>

          {/* Status pill */}
          <div
            data-tauri-no-drag
            className="flex items-center gap-1.5 bg-black/40 border border-white/[0.07] px-3 py-1 rounded-full text-[11px] font-medium text-neutral-300 cursor-default"
          >
            <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${statusColor}`} />
            <span>{statusLabel}</span>
          </div>

          {/* Close → hides the window (tray icon remains) */}
          <button
            data-tauri-no-drag
            onClick={hideWindow}
            className="p-1.5 rounded-full hover:bg-white/8 text-neutral-500 hover:text-white transition-colors"
            title="Hide (click menu bar icon to reopen)"
          >
            <X size={15} />
          </button>
        </div>

        {/* ── Centre: Orb + Reply text ─────────────────────────────────── */}
        <div className="flex-1 flex flex-col items-center justify-center overflow-hidden z-10 relative px-4">
          {/* Fixed-size orb */}
          <div style={{ width: 130, height: 130, flexShrink: 0 }}>
            <OrbVisualizer width={130} height={130} />
          </div>

          <div
            ref={replyContainerRef}
            className="w-full text-center text-[13px] font-light text-neutral-300 mt-3 overflow-y-auto leading-relaxed"
            style={{ maxHeight: 72, scrollbarWidth: 'none' }}
          >
            {commandReply || 'How can I help you?'}
          </div>
        </div>

        {/* ── Bottom controls ──────────────────────────────────────────── */}
        <div className="flex items-center justify-between w-full px-5 pb-4 pt-2 z-10 relative">
          {/* Mic mute toggle */}
          <button
            onClick={toggleMute}
            className={`p-3 rounded-full border transition-all ${
              isMuted
                ? 'bg-rose-950/40 border-rose-800/50 text-rose-400'
                : 'bg-white/[0.04] border-white/10 text-neutral-400 hover:text-white hover:bg-white/8'
            }`}
            title={isMuted ? 'Unmute Mic' : 'Mute Mic'}
          >
            {isMuted ? <MicOff size={18} /> : <Mic size={18} />}
          </button>

          {/* Central voice trigger */}
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

          {/* Right action cluster */}
          <div className="flex gap-2">
            <button
              onClick={() => { unlockAudio(); setShowTextDrawer(!showTextDrawer) }}
              className={`p-3 rounded-full border transition-all ${
                showTextDrawer
                  ? 'bg-blue-950/40 border-blue-700/40 text-blue-400'
                  : 'bg-white/[0.04] border-white/10 text-neutral-400 hover:text-white hover:bg-white/8'
              }`}
              title="Type a command"
            >
              <Keyboard size={18} />
            </button>
            <button
              onClick={toggleSpeaker}
              className={`p-3 rounded-full border transition-all ${
                !isSpeakerActive
                  ? 'bg-rose-950/40 border-rose-800/50 text-rose-400'
                  : 'bg-white/[0.04] border-white/10 text-neutral-400 hover:text-white hover:bg-white/8'
              }`}
              title={isSpeakerActive ? 'Mute Speaker' : 'Unmute Speaker'}
            >
              {isSpeakerActive ? <Volume2 size={18} /> : <VolumeX size={18} />}
            </button>
          </div>
        </div>

        {/* ── Keyboard drawer ─────────────────────────────────────────── */}
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
                  type="text"
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleTextSubmit()}
                  placeholder="Type a command..."
                  autoFocus
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

        {/* ── Logs drawer ─────────────────────────────────────────────── */}
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
                animate={{ opacity: 1, y: 0,  scale: 1 }}
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
      </motion.div>
    </div>
  )
}

export default App
