import { useRef, useEffect } from 'react'
import { useAppStore } from '../store/useAppStore'

// ─── Singleton AudioContext (persists across renders, survives re-renders) ─────
let _ctx: AudioContext | null = null
let _analyser: AnalyserNode | null = null
// Track the active buffer source so we can stop it
let _bufferSource: AudioBufferSourceNode | null = null
let _rafId: number | null = null

function getOrCreateContext(): { ctx: AudioContext; analyser: AnalyserNode } {
  if (!_ctx || _ctx.state === 'closed') {
    const Ctx = window.AudioContext || (window as any).webkitAudioContext
    _ctx = new Ctx()
    _analyser = _ctx.createAnalyser()
    _analyser.fftSize = 256
    // 0.82 gives stable frame-to-frame averaging (MDN recommended range 0.8–0.9)
    _analyser.smoothingTimeConstant = 0.82
    _analyser.connect(_ctx.destination)
  }
  return { ctx: _ctx!, analyser: _analyser! }
}

export function useSpeechPlayer() {
  const { setOrbState, setVolumeLevel, addAuditLog } = useAppStore()
  // We keep isSpeakerActive in a ref so the async closure always reads latest
  const speakerActiveRef = useRef(useAppStore.getState().isSpeakerActive)
  useEffect(() => {
    return useAppStore.subscribe((s) => {
      speakerActiveRef.current = s.isSpeakerActive
    })
  }, [])

  /**
   * unlockAudio — MUST be called inside every synchronous user-gesture handler.
   * WKWebView only permits AudioContext.resume() from a direct user interaction.
   */
  const unlockAudio = () => {
    const { ctx } = getOrCreateContext()
    if (ctx.state === 'suspended') {
      ctx.resume().catch(() => {})
    }
  }

  const playSpeech = async (text: string) => {
    // Stop any active playback immediately
    _interrupt()

    if (!text) return

    try {
      const { ctx, analyser } = getOrCreateContext()

      // ── Ensure context is running before we do anything ─────────────────
      if (ctx.state === 'suspended') {
        await ctx.resume()
      }
      if (ctx.state !== 'running') {
        // Context still not running — autoplay fully blocked; bail gracefully
        console.warn('[Speech] AudioContext blocked, cannot play.')
        addAuditLog('Audio blocked — tap the orb first to unlock.')
        return
      }

      // ── Fetch WAV as ArrayBuffer (avoids HTMLAudioElement autoplay block) ─
      // This approach bypasses WKWebView's HTMLAudioElement play() restriction
      // entirely: BufferSourceNode playback is not gated by autoplay policy.
      addAuditLog('Fetching TTS audio...')
      const encodedText = encodeURIComponent(text)
      const resp = await fetch(`http://127.0.0.1:8000/tts?text=${encodedText}`)
      if (!resp.ok) throw new Error(`TTS HTTP ${resp.status}`)

      const arrayBuf = await resp.arrayBuffer()
      const audioBuf = await ctx.decodeAudioData(arrayBuf)

      // If something else started playing while we were fetching, stop it
      _interrupt()

      // ── Build BufferSource → Analyser → Destination ──────────────────────
      const source = ctx.createBufferSource()
      source.buffer = audioBuf

      // Honour mute state: insert a GainNode so we can silence without stopping
      const gainNode = ctx.createGain()
      gainNode.gain.value = speakerActiveRef.current ? 1.0 : 0.0

      source.connect(gainNode)
      gainNode.connect(analyser)
      // analyser already connected to destination in getOrCreateContext()

      _bufferSource = source

      // ── Render-loop: continuously sample analyser frame-by-frame ─────────
      const dataArray = new Uint8Array(analyser.frequencyBinCount)
      let smoothedRMS = 0

      const sampleLoop = () => {
        analyser.getByteFrequencyData(dataArray)

        let sumSq = 0
        for (let i = 0; i < dataArray.length; i++) {
          const v = dataArray[i] / 255
          sumSq += v * v
        }
        const rms = Math.sqrt(sumSq / dataArray.length)
        // Layered software smoothing: fast attack, slow decay
        const alpha = rms > smoothedRMS ? 0.3 : 0.08
        smoothedRMS += (rms - smoothedRMS) * alpha
        setVolumeLevel(Math.min(smoothedRMS * 4.0, 1.0))

        _rafId = requestAnimationFrame(sampleLoop)
      }

      source.onended = () => {
        if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null }
        _bufferSource = null
        setOrbState('idle')
        setVolumeLevel(0)
        addAuditLog('TTS playback completed.')
      }

      setOrbState('speaking')
      addAuditLog('TTS playback started.')
      source.start(0)
      sampleLoop()

      // Keep gain in sync with speaker toggle while playing
      const unsubscribe = useAppStore.subscribe((s) => {
        gainNode.gain.value = s.isSpeakerActive ? 1.0 : 0.0
      })
      source.addEventListener('ended', unsubscribe, { once: true })

    } catch (err) {
      console.error('[Speech] Playback error:', err)
      setOrbState('error')
      setVolumeLevel(0)
      addAuditLog(`TTS error: ${String(err)}`)
    }
  }

  const interrupt = () => _interrupt()

  return { playSpeech, interrupt, unlockAudio }
}

// ─── Module-level stop helper ─────────────────────────────────────────────────
function _interrupt() {
  if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null }
  if (_bufferSource) {
    try { _bufferSource.stop() } catch (_) {}
    _bufferSource = null
  }
}
