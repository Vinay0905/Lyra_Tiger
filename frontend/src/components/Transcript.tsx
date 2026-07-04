import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Copy, RotateCw, Volume2 } from 'lucide-react'
import { useAppStore } from '../store/useAppStore'
import { ResultCard } from './ResultCard'

interface Props {
  onConfirm: (messageId: string, action: Record<string, unknown>, approve: boolean) => void
  onSpeakAgain: (text: string) => void
  onRegenerate: (text: string) => void
}

const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

async function revealInFinder(path: string) {
  if (!isTauri) return
  try {
    const { revealItemInDir } = await import('@tauri-apps/plugin-opener')
    await revealItemInDir(path)
  } catch (err) {
    console.error('reveal error', err)
  }
}

export function Transcript({ onConfirm, onSpeakAgain, onRegenerate }: Props) {
  const messages = useAppStore((s) => s.messages)
  const endRef = useRef<HTMLDivElement>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const copy = (id: string, text: string) => {
    navigator.clipboard?.writeText(text).then(() => {
      setCopiedId(id)
      setTimeout(() => setCopiedId((c) => (c === id ? null : c)), 1200)
    })
  }

  const lastUserQuery = () => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') return messages[i].content
    }
    return ''
  }

  if (messages.length === 0) {
    return (
      <div
        className="w-full text-center text-[13px] font-light leading-relaxed px-4"
        style={{ color: 'rgb(var(--lyra-text-muted))' }}
      >
        How can I help you?
      </div>
    )
  }

  return (
    <div
      className="w-full flex flex-col gap-2 overflow-y-auto px-3"
      style={{ maxHeight: 150, scrollbarWidth: 'none' }}
    >
      {messages.map((m) => {
        const isAssistant = m.role === 'assistant'
        return (
          <div key={m.id} className={`flex ${isAssistant ? 'justify-start' : 'justify-end'}`}>
            <div
              className={`max-w-[88%] rounded-2xl px-3 py-2 text-[12.5px] leading-relaxed ${
                isAssistant
                  ? 'bg-white/[0.05] border border-white/[0.07] text-neutral-200'
                  : 'bg-blue-600/25 border border-blue-500/25 text-blue-50'
              }`}
            >
              <div className="lyra-markdown">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {m.content || (m.streaming ? '…' : '')}
                </ReactMarkdown>
              </div>

              {m.streaming && (
                <span className="inline-block w-1.5 h-3 ml-0.5 align-middle bg-cyan-300/70 animate-pulse rounded-sm" />
              )}

              {isAssistant && !m.streaming && (
                <>
                  <ResultCard
                    skillResult={m.skillResult}
                    pendingAction={m.pendingAction}
                    resolved={m.resolved}
                    onConfirm={(approve) => m.pendingAction && onConfirm(m.id, m.pendingAction, approve)}
                    onRevealFinder={revealInFinder}
                  />

                  {m.content && (
                    <div className="flex items-center gap-2 mt-1.5 text-neutral-500">
                      <button title="Copy" onClick={() => copy(m.id, m.content)} className="hover:text-neutral-200 transition-colors">
                        <Copy size={12} />
                      </button>
                      <button title="Speak again" onClick={() => onSpeakAgain(m.content)} className="hover:text-neutral-200 transition-colors">
                        <Volume2 size={12} />
                      </button>
                      <button title="Regenerate" onClick={() => onRegenerate(lastUserQuery())} className="hover:text-neutral-200 transition-colors">
                        <RotateCw size={12} />
                      </button>
                      {copiedId === m.id && <span className="text-[9px] text-emerald-400">copied</span>}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )
      })}
      <div ref={endRef} />
    </div>
  )
}
