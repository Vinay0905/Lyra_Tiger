import { useAppStore } from '../store/useAppStore'
import { useSettingsStore } from '../store/useSettingsStore'
import { useSpeechPlayer } from './useSpeechPlayer'

// Pull out complete sentences from a growing buffer so TTS can start early.
const SENTENCE_BOUNDARY = /([.!?…]+["')\]]?\s)|(\n+)/

function extractSentences(buffer: string): { sentences: string[]; rest: string } {
  const sentences: string[] = []
  let rest = buffer
  let match = rest.match(SENTENCE_BOUNDARY)
  while (match && match.index !== undefined) {
    const end = match.index + match[0].length
    sentences.push(rest.slice(0, end).trim())
    rest = rest.slice(end)
    match = rest.match(SENTENCE_BOUNDARY)
  }
  // Safety valve: flush very long runs with no punctuation.
  if (rest.length > 200) {
    sentences.push(rest.trim())
    rest = ''
  }
  return { sentences, rest }
}

export function useCommandStream() {
  const { addMessage, appendToMessage, updateMessage, setOrbState, addAuditLog } = useAppStore()
  const { enqueueSpeech, interrupt, unlockAudio } = useSpeechPlayer()

  const sendCommand = async (rawQuery: string) => {
    const query = rawQuery.trim()
    if (!query) return

    unlockAudio()
    interrupt()

    const { backendUrl, sessionId, streamingEnabled } = useSettingsStore.getState()

    addMessage('user', query)
    addAuditLog(`Sent: "${query}"`)
    setOrbState('thinking')

    if (!streamingEnabled) {
      return sendBuffered(query, backendUrl, sessionId)
    }

    const assistantId = addMessage('assistant', '', { streaming: true })
    let sentenceBuffer = ''

    try {
      const resp = await fetch(`${backendUrl}/command/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: query, session_id: sessionId }),
      })
      if (!resp.ok || !resp.body) throw new Error(`Stream HTTP ${resp.status}`)

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let sseBuffer = ''

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        sseBuffer += decoder.decode(value, { stream: true })

        const blocks = sseBuffer.split('\n\n')
        sseBuffer = blocks.pop() ?? ''

        for (const block of blocks) {
          const line = block.split('\n').find((l) => l.startsWith('data:'))
          if (!line) continue
          let evt: any
          try {
            evt = JSON.parse(line.slice(5).trim())
          } catch {
            continue
          }

          if (evt.type === 'intent') {
            updateMessage(assistantId, { route: evt.intent })
            addAuditLog(`Routed → ${evt.intent} (${Number(evt.confidence).toFixed(2)})`)
          } else if (evt.type === 'token') {
            appendToMessage(assistantId, evt.text)
            sentenceBuffer += evt.text
            const { sentences, rest } = extractSentences(sentenceBuffer)
            sentenceBuffer = rest
            sentences.forEach((s) => enqueueSpeech(s))
          } else if (evt.type === 'done') {
            if (sentenceBuffer.trim()) enqueueSpeech(sentenceBuffer)
            sentenceBuffer = ''
            updateMessage(assistantId, {
              streaming: false,
              route: evt.route,
              skillResult: evt.skill_result ?? null,
              pendingAction: evt.pending_action ?? null,
            })
            addAuditLog(`Reply [${evt.route}] complete.`)
          } else if (evt.type === 'error') {
            throw new Error(evt.message)
          }
        }
      }
    } catch (err) {
      console.error('Stream error:', err)
      addAuditLog(`Error: ${err}`)
      setOrbState('error')
      updateMessage(assistantId, {
        streaming: false,
        content: 'The resonance was disrupted. The local backend may be offline.',
      })
    }
  }

  const sendBuffered = async (query: string, backendUrl: string, sessionId: string) => {
    const assistantId = addMessage('assistant', '…', { streaming: true })
    try {
      const r = await fetch(`${backendUrl}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: query, session_id: sessionId }),
      })
      const data = await r.json()
      updateMessage(assistantId, {
        content: data.reply,
        route: data.route,
        streaming: false,
        skillResult: data.skill_result ?? null,
        pendingAction: data.pending_action ?? null,
      })
      addAuditLog(`Reply [${data.route}] received.`)
      enqueueSpeech(data.reply)
    } catch (err) {
      addAuditLog(`Error: ${err}`)
      setOrbState('error')
      updateMessage(assistantId, { content: 'API connection failed.', streaming: false })
    }
  }

  // ── Human-in-the-loop resolution (L4 / UN4) ──────────────────────────────
  const confirmAction = async (messageId: string, action: Record<string, unknown>, approve: boolean) => {
    const { backendUrl, sessionId } = useSettingsStore.getState()
    updateMessage(messageId, { resolved: true, pendingAction: null })
    try {
      const r = await fetch(`${backendUrl}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, approve, action }),
      })
      const data = await r.json()
      addMessage('assistant', data.reply, { route: data.route, skillResult: data.skill_result ?? null })
      if (approve) enqueueSpeech(data.reply)
      addAuditLog(approve ? 'Action approved and executed.' : 'Action denied.')
    } catch (err) {
      addAuditLog(`Confirm error: ${err}`)
      addMessage('assistant', 'The confirmation could not be processed.')
    }
  }

  return { sendCommand, confirmAction }
}
