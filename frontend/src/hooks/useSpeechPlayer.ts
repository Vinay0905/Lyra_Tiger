import { useEffect, useRef } from 'react'
import { useAppStore } from '../store/useAppStore'
import { useSettingsStore } from '../store/useSettingsStore'

// ─── Singleton AudioContext (persists across renders) ──────────────────────────
let _ctx: AudioContext | null = null
let _analyser: AnalyserNode | null = null
let _bufferSource: AudioBufferSourceNode | null = null
let _gainNode: GainNode | null = null
let _rafId: number | null = null

// Sentence-chunked streaming TTS queue (A2)
const _queue: string[] = []
let _isPlaying = false

function getOrCreateContext(): { ctx: AudioContext; analyser: AnalyserNode } {
  if (!_ctx || _ctx.state === 'closed') {
    const Ctx = window.AudioContext || (window as any).webkitAudioContext
    _ctx = new Ctx()
    _analyser = _ctx.createAnalyser()
    _analyser.fftSize = 256
    _analyser.smoothingTimeConstant = 0.82
    _analyser.connect(_ctx.destination)
  }
  return { ctx: _ctx!, analyser: _analyser! }
}

export function useSpeechPlayer() {
  const { setOrbState, setVolumeLevel, addAuditLog } = useAppStore()
  const speakerActiveRef = useRef(useAppStore.getState().isSpeakerActive)

  useEffect(() => {
    return useAppStore.subscribe((s) => {
      speakerActiveRef.current = s.isSpeakerActive
      if (_gainNode) _gainNode.gain.value = s.isSpeakerActive ? 1.0 : 0.0
    })
  }, [])

  const unlockAudio = () => {
    const { ctx } = getOrCreateContext()
    if (ctx.state === 'suspended') ctx.resume().catch(() => {})
  }

  const _startSampleLoop = (analyser: AnalyserNode) => {
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
      const alpha = rms > smoothedRMS ? 0.3 : 0.08
      smoothedRMS += (rms - smoothedRMS) * alpha
      setVolumeLevel(Math.min(smoothedRMS * 4.0, 1.0))
      _rafId = requestAnimationFrame(sampleLoop)
    }
    sampleLoop()
  }

  const _playNext = async () => {
    if (_queue.length === 0) {
      _isPlaying = false
      if (_rafId) {
        cancelAnimationFrame(_rafId)
        _rafId = null
      }
      setOrbState('idle')
      setVolumeLevel(0)
      return
    }
    _isPlaying = true
    const text = _queue.shift()!
    if (!text.trim()) return _playNext()

    try {
      const { ctx, analyser } = getOrCreateContext()
      if (ctx.state === 'suspended') await ctx.resume()
      if (ctx.state !== 'running') {
        addAuditLog('Audio blocked — tap the orb first to unlock.')
        _isPlaying = false
        return
      }

      const { backendUrl, voice } = useSettingsStore.getState()
      const resp = await fetch(
        `${backendUrl}/tts?text=${encodeURIComponent(text)}&voice=${encodeURIComponent(voice)}`,
      )
      if (!resp.ok) throw new Error(`TTS HTTP ${resp.status}`)
      const audioBuf = await ctx.decodeAudioData(await resp.arrayBuffer())

      const source = ctx.createBufferSource()
      source.buffer = audioBuf
      const gainNode = ctx.createGain()
      gainNode.gain.value = speakerActiveRef.current ? 1.0 : 0.0
      source.connect(gainNode)
      gainNode.connect(analyser)
      _bufferSource = source
      _gainNode = gainNode

      if (_rafId === null) _startSampleLoop(analyser)
      setOrbState('speaking')

      source.onended = () => {
        _bufferSource = null
        _gainNode = null
        void _playNext()
      }
      source.start(0)
    } catch (err) {
      console.error('[Speech] Playback error:', err)
      addAuditLog(`TTS error: ${String(err)}`)
      _isPlaying = false
      setOrbState('idle')
      setVolumeLevel(0)
    }
  }

  /** Queue a chunk of text for sequential playback (used by streaming). */
  const enqueueSpeech = (text: string) => {
    const { ttsEnabled } = useSettingsStore.getState()
    if (!ttsEnabled || !text.trim()) return
    _queue.push(text.trim())
    if (!_isPlaying) void _playNext()
  }

  /** Replace any pending speech with a single utterance. */
  const playSpeech = (text: string) => {
    _interrupt()
    enqueueSpeech(text)
  }

  const interrupt = () => _interrupt()

  return { playSpeech, enqueueSpeech, interrupt, unlockAudio }
}

function _interrupt() {
  _queue.length = 0
  _isPlaying = false
  if (_rafId) {
    cancelAnimationFrame(_rafId)
    _rafId = null
  }
  if (_bufferSource) {
    try {
      _bufferSource.onended = null
      _bufferSource.stop()
    } catch {
      /* already stopped */
    }
    _bufferSource = null
  }
}
