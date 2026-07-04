import { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useAppStore } from '../store/useAppStore'

export function Transcript() {
  const messages = useAppStore((s) => s.messages)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className="w-full text-center text-[13px] font-light text-neutral-400 leading-relaxed px-4">
        How can I help you?
      </div>
    )
  }

  return (
    <div
      className="w-full flex flex-col gap-2 overflow-y-auto px-3"
      style={{ maxHeight: 150, scrollbarWidth: 'none' }}
    >
      {messages.map((m) => (
        <div
          key={m.id}
          className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div
            className={`max-w-[85%] rounded-2xl px-3 py-2 text-[12.5px] leading-relaxed ${
              m.role === 'user'
                ? 'bg-blue-600/25 border border-blue-500/25 text-blue-50'
                : 'bg-white/[0.05] border border-white/[0.07] text-neutral-200'
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
          </div>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  )
}
