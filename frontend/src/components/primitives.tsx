import type { ButtonHTMLAttributes, ReactNode } from 'react'

// ── Design-system primitives (UN2) ────────────────────────────────────────────
// Thin, token-driven components so surfaces/buttons/pills stay consistent and
// theme-aware instead of relying on scattered inline literals.

interface SurfaceProps {
  children: ReactNode
  className?: string
  elevated?: boolean
}

export function Surface({ children, className = '', elevated = false }: SurfaceProps) {
  return (
    <div
      className={className}
      style={{
        background: `rgb(var(--lyra-surface) / var(--lyra-panel-alpha))`,
        border: `1px solid rgb(var(--lyra-border) / var(--lyra-border-alpha))`,
        borderRadius: 'var(--lyra-radius-lg)',
        boxShadow: elevated ? 'var(--lyra-elevation)' : undefined,
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
      }}
    >
      {children}
    </div>
  )
}

type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  active?: boolean
  tone?: 'default' | 'danger'
  children: ReactNode
}

export function IconButton({ active, tone = 'default', children, className = '', ...rest }: IconButtonProps) {
  const toneClass =
    tone === 'danger'
      ? 'bg-rose-950/40 border-rose-800/50 text-rose-400'
      : active
      ? 'bg-blue-950/40 border-blue-700/40 text-blue-400'
      : 'text-neutral-400 hover:text-white hover:bg-white/8'
  return (
    <button
      {...rest}
      className={`p-3 rounded-full border transition-all ${
        tone === 'default' && !active ? 'bg-white/[0.04] border-white/10' : ''
      } ${toneClass} ${className}`}
    >
      {children}
    </button>
  )
}

interface PillProps {
  children: ReactNode
  dotClassName?: string
}

export function Pill({ children, dotClassName }: PillProps) {
  return (
    <div
      className="flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-medium cursor-default"
      style={{
        background: 'rgb(0 0 0 / 0.35)',
        border: `1px solid rgb(var(--lyra-border) / 0.07)`,
        color: `rgb(var(--lyra-text-muted))`,
      }}
    >
      {dotClassName && <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${dotClassName}`} />}
      <span>{children}</span>
    </div>
  )
}
