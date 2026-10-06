import type { Message, Route, Turn } from './types'
export const asset = (name: string) => `${import.meta.env.BASE_URL}assets/${name}`
export const timestamp = (seconds: number) => new Date(seconds * 1000).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
export const sizeLabel = (bytes: number) => bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
export function routeFromHash(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/')
  const mode = parts[0] === 'app' ? 'app' : 'demo'
  const views = ['chat', 'saves', 'memories', 'tasks', 'gallery', 'status', 'settings'] as const
  const view = views.find(v => v === parts[1]) || 'chat'
  return { mode, view, home: !['demo', 'app'].includes(parts[0]) }
}
export function navigate(mode: 'demo' | 'app', view: string) { window.location.hash = `/${mode}/${view}` }
export function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename
  document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 10_000)
}
export function buildMessages(turns: Turn[], input: string, charBudget = 24_000): Message[] {
  let used = input.length
  const selected: Turn[] = []
  for (const turn of [...turns].sort((a, b) => b.id - a.id)) {
    // Generated URLs and timing boilerplate do not belong in narrative context.
    const clean = turn.assistant_text.replace(/!\[[^\]]*\]\([^)]*\)/g, '').replace(/_Image generated locally[^\n]*_/g, '').trim()
    const total = turn.user_text.length + clean.length
    if (used + total > charBudget) break
    selected.push({ ...turn, assistant_text: clean }); used += total
  }
  return selected.reverse().flatMap(turn => [
    { role: 'user' as const, content: turn.user_text },
    { role: 'assistant' as const, content: turn.assistant_text },
  ]).concat({ role: 'user', content: input })
}
export function imageURL(source: string | undefined, base: string): string | undefined {
  if (!source) return undefined
  // Known gateway image routes are resolved through the active gateway/proxy,
  // including old history containing Windows localhost absolute URLs.
  const match = source.match(/(?:^|\/)(images\/[^/?#]+\.webp)(?:[?#].*)?$/i)
  if (match) return `${base}/${match[1]}`
  if (/^https?:\/\//i.test(source) || source.startsWith('/') || source.startsWith('./')) return source
  return undefined
}
export function readStored(storage: 'local' | 'session', key: string): string { try { return (storage === 'local' ? window.localStorage : window.sessionStorage).getItem(key) || '' } catch { return '' } }
export function writeStored(kind: 'local' | 'session', key: string, value: string) { try { const storage = kind === 'local' ? window.localStorage : window.sessionStorage; if (value) storage.setItem(key, value); else storage.removeItem(key) } catch { /* Browsing still works when storage is unavailable. */ } }
