import { useState, useRef } from 'react'
import { useAppStore } from '../store/useAppStore'
import { useSettingsStore } from '../store/useSettingsStore'

const SAMPLE_RATE = 16000

export function useVoiceCapture(
  enqueueSpeech: (text: string) => void,
  interruptSpeech: () => void,
) {
  const { setOrbState, setVolumeLevel, addAuditLog, addMessage } = useAppStore()

  const [isRecording, setIsRecording] = useState(false)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const workletRef = useRef<AudioWorkletNode | null>(null)
  const scriptNodeRef = useRef<ScriptProcessorNode | null>(null)
  const chunksRef = useRef<Float32Array[]>([])
  const rafRef = useRef<number | null>(null)

  const startRecording = async () => {
    try {
      interruptSpeech()
      chunksRef.current = []

      const { micDeviceId } = useSettingsStore.getState()
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: micDeviceId ? { deviceId: { exact: micDeviceId } } : true,
        video: false,
      })
      mediaStreamRef.current = stream

      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext
      const audioContext = new AudioContextClass({ sampleRate: SAMPLE_RATE })
      audioContextRef.current = audioContext

      const analyser = audioContext.createAnalyser()
      analyser.fftSize = 256
      analyser.smoothingTimeConstant = 0.82
      analyserRef.current = analyser

      const source = audioContext.createMediaStreamSource(stream)
      sourceRef.current = source
      source.connect(analyser)

      // ── Prefer AudioWorklet; gracefully fall back to ScriptProcessor ──────
      let usedWorklet = false
      try {
        if (audioContext.audioWorklet) {
          await audioContext.audioWorklet.addModule('/pcm-recorder.js')
          const worklet = new AudioWorkletNode(audioContext, 'pcm-recorder')
          worklet.port.onmessage = (e) => chunksRef.current.push(e.data as Float32Array)
          source.connect(worklet)
          worklet.connect(audioContext.destination)
          workletRef.current = worklet
          usedWorklet = true
        }
      } catch (werr) {
        console.warn('[Voice] AudioWorklet unavailable, falling back:', werr)
      }

      if (!usedWorklet) {
        const processor = audioContext.createScriptProcessor(4096, 1, 1)
        processor.onaudioprocess = (e) => {
          chunksRef.current.push(new Float32Array(e.inputBuffer.getChannelData(0)))
        }
        source.connect(processor)
        processor.connect(audioContext.destination)
        scriptNodeRef.current = processor
      }

      setIsRecording(true)
      setOrbState('listening')
      addAuditLog(`Recording started (${usedWorklet ? 'AudioWorklet' : 'ScriptProcessor'}).`)

      const dataArray = new Uint8Array(analyser.frequencyBinCount)
      const updateVolume = () => {
        if (!analyserRef.current) return
        analyserRef.current.getByteFrequencyData(dataArray)
        let total = 0
        for (let i = 0; i < dataArray.length; i++) total += dataArray[i]
        setVolumeLevel(Math.min(total / dataArray.length / 120, 1.0))
        rafRef.current = requestAnimationFrame(updateVolume)
      }
      updateVolume()
    } catch (err) {
      console.error('Failed to access microphone:', err)
      addAuditLog(`Mic access error: ${err}`)
      setOrbState('error')
    }
  }

  const stopRecording = () => {
    if (!isRecording) return

    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
    workletRef.current?.disconnect()
    workletRef.current = null
    scriptNodeRef.current?.disconnect()
    scriptNodeRef.current = null
    sourceRef.current?.disconnect()
    sourceRef.current = null
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop())
    mediaStreamRef.current = null
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close()
      audioContextRef.current = null
    }

    setIsRecording(false)
    setOrbState('thinking')
    setVolumeLevel(0)

    const wavBlob = exportWAV(chunksRef.current, SAMPLE_RATE)
    addAuditLog(`WAV compiled (${(wavBlob.size / 1024).toFixed(1)} KB). Transcribing…`)
    void sendVoiceCommand(wavBlob)
  }

  const sendVoiceCommand = async (wavBlob: Blob) => {
    const { backendUrl, sessionId } = useSettingsStore.getState()
    try {
      const formData = new FormData()
      formData.append('file', wavBlob, 'command.wav')
      const url = `${backendUrl}/voice_command?session_id=${encodeURIComponent(sessionId)}`
      const response = await fetch(url, { method: 'POST', body: formData })
      const data = await response.json()

      if (data.transcription) addMessage('user', data.transcription)
      addMessage('assistant', data.reply, { route: data.route })
      addAuditLog(`Voice execution completed [${data.route}].`)
      enqueueSpeech(data.reply)
    } catch (err) {
      console.error('Voice command failed:', err)
      addAuditLog(`Voice command error: ${err}`)
      setOrbState('idle')
      addMessage('assistant', 'Voice processing failed on the local backend.')
    }
  }

  return { isRecording, startRecording, stopRecording }
}

// ─── WAV Exporter ──────────────────────────────────────────────────────────────
function exportWAV(chunks: Float32Array[], sampleRate: number): Blob {
  let totalLength = 0
  for (let i = 0; i < chunks.length; i++) totalLength += chunks[i].length
  const result = new Float32Array(totalLength)
  let offset = 0
  for (let i = 0; i < chunks.length; i++) {
    result.set(chunks[i], offset)
    offset += chunks[i].length
  }

  const buffer = new ArrayBuffer(44 + result.length * 2)
  const view = new DataView(buffer)
  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + result.length * 2, true)
  writeString(view, 8, 'WAVE')
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(view, 36, 'data')
  view.setUint32(40, result.length * 2, true)

  let index = 44
  for (let i = 0; i < result.length; i++) {
    const s = Math.max(-1, Math.min(1, result[i]))
    view.setInt16(index, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    index += 2
  }
  return new Blob([view], { type: 'audio/wav' })
}

function writeString(view: DataView, offset: number, str: string) {
  for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
}
