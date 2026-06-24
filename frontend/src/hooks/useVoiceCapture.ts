import { useState, useRef } from 'react'
import { useAppStore } from '../store/useAppStore'

export function useVoiceCapture(playSpeech: (text: string) => void, interruptSpeech: () => void) {
  const { setOrbState, setVolumeLevel, addAuditLog, setCommandReply } = useAppStore()
  
  const [isRecording, setIsRecording] = useState(false)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const audioChunksRef = useRef<Float32Array[]>([])
  const animationFrameRef = useRef<number | null>(null)

  const startRecording = async () => {
    try {
      interruptSpeech()
      audioChunksRef.current = []
      
      // 1. Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
      mediaStreamRef.current = stream

      // 2. Initialize AudioContext and Analyser
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext
      const audioContext = new AudioContextClass({ sampleRate: 16000 })
      audioContextRef.current = audioContext

      const analyser = audioContext.createAnalyser()
      analyser.fftSize = 256
      // smoothingTimeConstant = 0.82 matches the TTS analyser for consistent frame averaging
      analyser.smoothingTimeConstant = 0.82
      analyserRef.current = analyser

      const source = audioContext.createMediaStreamSource(stream)
      sourceRef.current = source
      source.connect(analyser)

      // 3. Set up ScriptProcessor to capture raw PCM audio chunks (16kHz Mono)
      const bufferSize = 4096
      const processor = audioContext.createScriptProcessor(bufferSize, 1, 1)
      processorRef.current = processor
      
      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0)
        // Store a copy of the float array
        audioChunksRef.current.push(new Float32Array(inputData))
      }
      
      source.connect(processor)
      processor.connect(audioContext.destination)

      setIsRecording(true)
      setOrbState('listening')
      addAuditLog('Microphone recording started.')
      setCommandReply('Listening to your voice...')

      // 4. Start volume analysis loop for WebGL Orb ripple animation
      const dataArray = new Uint8Array(analyser.frequencyBinCount)
      
      const updateVolume = () => {
        if (!analyserRef.current) return
        analyserRef.current.getByteFrequencyData(dataArray)
        
        // Calculate average amplitude (RMS)
        let total = 0
        for (let i = 0; i < dataArray.length; i++) {
          total += dataArray[i]
        }
        const average = total / dataArray.length
        
        // Map average frequency (0-255) to volumeLevel (0-1)
        const mappedVolume = Math.min(average / 120, 1.0)
        setVolumeLevel(mappedVolume)
        
        animationFrameRef.current = requestAnimationFrame(updateVolume)
      }
      
      updateVolume()

    } catch (err) {
      console.error('Failed to access microphone:', err)
      addAuditLog(`Mic access error: ${err}`)
      setOrbState('error')
      setCommandReply('Microphone access denied or failed.')
    }
  }

  const stopRecording = () => {
    if (!isRecording) return

    // 1. Cancel volume animation loop
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = null
    }

    // 2. Stop audio processor and source connections
    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current = null
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect()
      sourceRef.current = null
    }

    // 3. Stop all media stream tracks
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop())
      mediaStreamRef.current = null
    }

    // 4. Close AudioContext
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close()
      audioContextRef.current = null
    }

    setIsRecording(false)
    setOrbState('thinking')
    setVolumeLevel(0)
    addAuditLog('Microphone recording stopped.')
    setCommandReply('Processing voice...')

    // 5. Compile floats to WAV blob
    const sampleRate = 16000
    const wavBlob = exportWAV(audioChunksRef.current, sampleRate)
    addAuditLog(`WAV Audio compiled successfully. Size: ${(wavBlob.size / 1024).toFixed(1)} KB`)
    
    // Upload WAV to FastAPI /voice_command
    const sendVoiceCommand = async () => {
      try {
        const formData = new FormData()
        formData.append('file', wavBlob, 'command.wav')
        
        const response = await fetch('http://127.0.0.1:8000/voice_command', {
          method: 'POST',
          body: formData
        })
        const data = await response.json()
        
        setCommandReply(data.reply)
        playSpeech(data.reply)
        addAuditLog(`Voice execution completed [${data.route}].`)
      } catch (err) {
        console.error('Failed to process voice command on backend:', err)
        addAuditLog(`Voice command error: ${err}`)
        setOrbState('idle')
        setCommandReply('Voice processing failed on local backend.')
      }
    }
    
    sendVoiceCommand()
  }

  return {
    isRecording,
    startRecording,
    stopRecording,
  }
}

// WAV Exporter helper function
function exportWAV(chunks: Float32Array[], sampleRate: number): Blob {
  // 1. Merge chunks
  let totalLength = 0
  for (let i = 0; i < chunks.length; i++) {
    totalLength += chunks[i].length
  }
  const result = new Float32Array(totalLength)
  let offset = 0
  for (let i = 0; i < chunks.length; i++) {
    result.set(chunks[i], offset)
    offset += chunks[i].length
  }

  // 2. Create WAV buffer
  const buffer = new ArrayBuffer(44 + result.length * 2)
  const view = new DataView(buffer)

  // Write WAV header
  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + result.length * 2, true)
  writeString(view, 8, 'WAVE')
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true) // PCM format
  view.setUint16(22, 1, true) // Mono channel
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // Byte rate
  view.setUint16(32, 2, true) // Block align
  view.setUint16(34, 16, true) // 16 bits per sample
  writeString(view, 36, 'data')
  view.setUint32(40, result.length * 2, true)

  // Write PCM audio data
  let index = 44
  for (let i = 0; i < result.length; i++) {
    const s = Math.max(-1, Math.min(1, result[i]))
    const val = s < 0 ? s * 0x8000 : s * 0x7FFF
    view.setInt16(index, val, true)
    index += 2
  }

  return new Blob([view], { type: 'audio/wav' })
}

function writeString(view: DataView, offset: number, string: string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i))
  }
}
