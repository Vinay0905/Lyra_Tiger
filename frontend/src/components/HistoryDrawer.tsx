import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Search, X } from 'lucide-react'
import { useSettingsStore } from '../store/useSettingsStore'

interface AuditEntry {
  id: number
  query: string
  intent: string
  reply: string
  ts: string
}

export function HistoryDrawer({ onClose, onReuse }: { onClose: () => void; onReuse: (q: string) => void }) {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const { backendUrl, sessionId } = useSettingsStore.getState()
    fetch(`${backendUrl}/audit?session_id=${encodeURIComponent(sessionId)}&limit=100`)
      .then((r) => r.json())
      .then((d) => setEntries(d.entries || []))
      .catch(() => setEntries([]))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return entries
    return entries.filter(
      (e) => e.query?.toLowerCase().includes(q) || e.reply?.toLowerCase().includes(q),
    )
  }, [entries, query])

  return (
    <div className="absolute inset-0 z-40 flex items-stretch" style={{ background: 'rgba(0,0,0,0.5)' }} onClick={onClose}>
      <motion.div
        initial={{ x: '-100%' }}
        animate={{ x: 0 }}
        exit={{ x: '-100%' }}
        transition={{ type: 'spring', damping: 30, stiffness: 300 }}
        className="w-[300px] h-full bg-neutral-950/98 border-r border-white/10 p-4 overflow-y-auto flex flex-col gap-3"
        style={{ scrollbarWidth: 'none' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-widest text-neutral-300">History</span>
          <button onClick={onClose} className="text-neutral-500 hover:text-white"><X size={15} /></button>
        </div>

        <div className="flex items-center gap-2 bg-neutral-900 border border-white/10 rounded-lg px-2.5 py-1.5">
          <Search size={13} className="text-neutral-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search past commands…"
            className="flex-1 bg-transparent text-[12px] text-neutral-100 outline-none placeholder:text-neutral-600"
          />
        </div>

        {loading && <p className="text-[11px] text-neutral-600">Loading…</p>}
        {!loading && filtered.length === 0 && (
          <p className="text-[11px] text-neutral-600">No matching history.</p>
        )}

        <div className="flex flex-col gap-1.5">
          {filtered.map((e) => (
            <button
              key={e.id}
              onClick={() => { onReuse(e.query); onClose() }}
              className="text-left bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] rounded-lg px-2.5 py-1.5 transition-colors"
            >
              <div className="flex items-center justify-between">
                <span className="text-[9px] uppercase tracking-wide text-neutral-500">{e.intent}</span>
                <span className="text-[9px] text-neutral-600">{new Date(e.ts).toLocaleTimeString()}</span>
              </div>
              <p className="text-[12px] text-neutral-200 truncate">{e.query}</p>
            </button>
          ))}
        </div>
      </motion.div>
    </div>
  )
}
