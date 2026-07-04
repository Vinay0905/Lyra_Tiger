import { Check, ExternalLink, FileText, FolderOpen, Image as ImageIcon, X } from 'lucide-react'

interface Props {
  skillResult?: Record<string, unknown> | null
  pendingAction?: Record<string, unknown> | null
  resolved?: boolean
  onConfirm?: (approve: boolean) => void
  onRevealFinder?: (path: string) => void
}

// ── Typed result cards (UN4) ──────────────────────────────────────────────────
// Renders skill output as structured, actionable UI keyed off the discriminated
// SkillResult.kind, plus an inline Approve/Deny gate for pending actions (L4).
export function ResultCard({ skillResult, pendingAction, resolved, onConfirm, onRevealFinder }: Props) {
  const kind = skillResult?.kind as string | undefined

  return (
    <div className="flex flex-col gap-1.5 mt-1.5">
      {kind === 'browser' && Boolean(skillResult?.target) && (
        <a
          href={String(skillResult!.target)}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1.5 text-[11px] bg-black/30 border border-white/10 rounded-lg px-2 py-1 text-blue-300 hover:bg-black/50 transition-colors truncate"
        >
          <ExternalLink size={11} className="shrink-0" />
          <span className="truncate">
            {String((skillResult as any)?.page?.title || skillResult!.target)}
          </span>
        </a>
      )}

      {kind === 'vision' && Boolean((skillResult as any)?.screenshot_path) && (
        <div className="flex items-center gap-1.5 text-[11px] text-neutral-400">
          <ImageIcon size={11} /> Screen captured
        </div>
      )}

      {kind === 'developer' && Boolean(skillResult?.path) && (
        <button
          onClick={() => onRevealFinder?.(String(skillResult!.path))}
          className="flex items-center gap-1.5 text-[11px] bg-black/30 border border-white/10 rounded-lg px-2 py-1 text-neutral-300 hover:bg-black/50 transition-colors"
        >
          <FileText size={11} />
          <span className="truncate">{String(skillResult!.path)}</span>
          <FolderOpen size={11} className="ml-auto shrink-0 opacity-60" />
        </button>
      )}

      {pendingAction && !resolved && (
        <div className="flex items-center gap-2 mt-1">
          <button
            onClick={() => onConfirm?.(true)}
            className="flex items-center gap-1 text-[11px] font-medium bg-emerald-600/80 hover:bg-emerald-600 text-white rounded-lg px-2.5 py-1 transition-colors"
          >
            <Check size={11} /> Approve
          </button>
          <button
            onClick={() => onConfirm?.(false)}
            className="flex items-center gap-1 text-[11px] font-medium bg-white/[0.06] hover:bg-white/[0.12] text-neutral-300 rounded-lg px-2.5 py-1 transition-colors"
          >
            <X size={11} /> Deny
          </button>
        </div>
      )}
    </div>
  )
}
