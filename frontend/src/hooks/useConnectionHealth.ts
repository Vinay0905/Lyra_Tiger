import { useEffect, useRef } from 'react'
import { useAppStore } from '../store/useAppStore'
import { useSettingsStore } from '../store/useSettingsStore'

const POLL_MS = 5000
const TIMEOUT_MS = 3000

/**
 * Polls the backend /health endpoint and drives the connection state machine
 * (connecting -> ready -> degraded/disconnected) so the UI always reflects
 * backend availability instead of failing silently (UN3).
 */
export function useConnectionHealth() {
  const setConnection = useAppStore((s) => s.setConnection)
  const failuresRef = useRef(0)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    const poll = async () => {
      const { backendUrl } = useSettingsStore.getState()
      const controller = new AbortController()
      const to = setTimeout(() => controller.abort(), TIMEOUT_MS)
      try {
        const r = await fetch(`${backendUrl}/health`, { signal: controller.signal })
        clearTimeout(to)
        if (cancelled) return
        if (r.ok) {
          failuresRef.current = 0
          setConnection('ready')
        } else {
          failuresRef.current += 1
          setConnection('degraded')
        }
      } catch {
        clearTimeout(to)
        if (cancelled) return
        failuresRef.current += 1
        setConnection(failuresRef.current >= 2 ? 'disconnected' : 'degraded')
      } finally {
        if (!cancelled) timer = setTimeout(poll, POLL_MS)
      }
    }

    poll()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [setConnection])
}
