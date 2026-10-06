import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { ApiError, Gateway } from './api'
import { AppContext } from './context'
import { demoMemories, demoSave, demoTask, demoTurns } from './demo'
import type { Backup, Diagnostics, Health, ImageTask, Memory, Route, Save, Turn } from './types'
import { buildMessages, navigate, readStored, routeFromHash, writeStored } from './utils'

interface Connection { base: string; token: string }
interface Pending { saveId: string; text: string; content: string; requestId: string; startedAt: number }
interface Notice { id: number; text: string; kind: 'success' | 'error' }
function useAppState() {
  const [route, setRoute] = useState<Route>(() => routeFromHash(window.location.hash))
  const [connection, setConnection] = useState<Connection>(() => ({
    base: readStored('local', 'storycanvas.gateway'), token: readStored('session', 'storycanvas.token'),
  }))
  const api = useMemo(() => new Gateway(connection.base, connection.token), [connection])
  const [liveSaves, setLiveSaves] = useState<Save[]>([])
  const [selected, setSelected] = useState(() => readStored('local', 'storycanvas.save'))
  const [liveTurns, setLiveTurns] = useState<Turn[]>([])
  const [liveMemories, setLiveMemories] = useState<Memory[]>([])
  const [liveTasks, setLiveTasks] = useState<ImageTask[]>([])
  const taskStates = useRef(new Map<string, string>())
  useEffect(() => { taskStates.current = new Map(liveTasks.map(task => [task.id, task.status])) }, [liveTasks])
  const [health, setHealth] = useState<Health | null>(null)
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null)
  const [backups, setBackups] = useState<Backup[]>([])
  const [loading, setLoading] = useState(false)
  const [resourceError, setResourceError] = useState('')
  const [pending, setPending] = useState<Pending | null>(null)
  const [unconfirmedReply, setUnconfirmedReply] = useState<{ saveId: string; text: string; content: string } | null>(null)
  const pendingRef = useRef(false)
  const [canLoadTurns, setCanLoadTurns] = useState(false)
  const [canLoadMemories, setCanLoadMemories] = useState(false)
  const [canLoadTasks, setCanLoadTasks] = useState(false)
  const [notices, setNotices] = useState<Notice[]>([])
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const setDraft = (id: string, value: string) => setDrafts(old => ({ ...old, [id]: value }))
  const noticeId = useRef(0)
  const demo = route.mode === 'demo'
  const connected = !!connection.token
  const notify = useCallback((text: string, kind: Notice['kind'] = 'success') => {
    setNotices(items => [...items.slice(-3), { id: ++noticeId.current, text, kind }])
  }, [])
  const dismissNotice = (id: number) => setNotices(items => items.filter(item => item.id !== id))
  const fail = useCallback((error: unknown) => {
    const text = error instanceof Error ? error.message : '操作失败，请重试。'
    const trace = error instanceof ApiError && error.requestId ? ` 请求编号：${error.requestId}` : ''
    notify(text + trace, 'error')
  }, [notify])
  useEffect(() => {
    const change = () => setRoute(routeFromHash(window.location.hash))
    window.addEventListener('hashchange', change); return () => window.removeEventListener('hashchange', change)
  }, [])
  useEffect(() => {
    const viewport = window.visualViewport
    const resize = () => document.documentElement.style.setProperty('--viewport-height', `${viewport?.height || window.innerHeight}px`)
    resize(); viewport?.addEventListener('resize', resize); window.addEventListener('resize', resize)
    return () => { viewport?.removeEventListener('resize', resize); window.removeEventListener('resize', resize); document.documentElement.style.removeProperty('--viewport-height') }
  }, [])
  useEffect(() => { writeStored('local', 'storycanvas.save', selected) }, [selected])

  const refreshSaves = useCallback(async () => {
    const result = await api.saves()
    setLiveSaves(result.data)
    setSelected(previous => result.data.some(s => s.id === previous && !s.archived_at) ? previous :
      result.data.find(s => s.id === result.active_save_id && !s.archived_at)?.id || result.data.find(s => !s.archived_at)?.id || '')
    return result
  }, [api])
  const refreshHealth = useCallback(async () => { const result = await api.health(); setHealth(result); return result }, [api])
  const refreshSystem = useCallback(async () => {
    const results = await Promise.allSettled([api.diagnostics(), api.backups(), api.health()])
    if (results[0].status === 'fulfilled') setDiagnostics(results[0].value); else fail(results[0].reason)
    if (results[1].status === 'fulfilled') setBackups(results[1].value.data); else fail(results[1].reason)
    if (results[2].status === 'fulfilled') setHealth(results[2].value); else fail(results[2].reason)
  }, [api, fail])

  useEffect(() => {
    if (demo || route.home || !connected) return
    let stopped = false
    setResourceError('')
    Promise.all([api.saves(), api.health()]).then(([result, h]) => {
      if (stopped) return
      setLiveSaves(result.data); setHealth(h)
      setSelected(previous => result.data.some(s => s.id === previous && !s.archived_at) ? previous :
        result.data.find(s => s.id === result.active_save_id && !s.archived_at)?.id || result.data.find(s => !s.archived_at)?.id || '')
    }).catch(error => { if (!stopped) { setResourceError(error.message); fail(error) } })
    return () => { stopped = true }
  }, [api, connected, demo, route.home, fail])

  useEffect(() => {
    if (demo || !connected || !selected) return
    let stopped = false
    setLoading(true); setResourceError(''); setLiveTurns([]); setLiveMemories([]); setLiveTasks([])
    setCanLoadTurns(false); setCanLoadMemories(false); setCanLoadTasks(false)
    Promise.allSettled([api.turns(selected), api.memories(selected), api.tasks(selected)]).then(results => {
      if (stopped) return
      const [ts, ms, jobs] = results
      if (ts.status === 'fulfilled') { setLiveTurns(ts.value.data.sort((a, b) => a.id - b.id)); setCanLoadTurns(ts.value.data.length === 30) }
      if (ms.status === 'fulfilled') { setLiveMemories(ms.value.data); setCanLoadMemories(ms.value.data.length === 100) }
      if (jobs.status === 'fulfilled') { setLiveTasks(jobs.value.data); setCanLoadTasks(jobs.value.data.length === 50) }
      const bad = results.find(r => r.status === 'rejected')
      if (bad?.status === 'rejected') { setResourceError(bad.reason.message); fail(bad.reason) }
      setLoading(false)
    })
    return () => { stopped = true }
  }, [api, connected, demo, selected, fail])

  const refreshStory = useCallback(async () => {
    if (!selected || demo) return
    const [ts, ms, jobs] = await Promise.all([api.turns(selected), api.memories(selected), api.tasks(selected)])
    // Preserve already-loaded older pages while refreshing the latest page.
    setLiveTurns(old => Array.from(new Map([...old, ...ts.data].map(t => [t.id, t])).values()).sort((a, b) => a.id - b.id))
    setLiveMemories(ms.data); setLiveTasks(jobs.data)
    setCanLoadMemories(ms.data.length === 100); setCanLoadTasks(jobs.data.length === 50)
    return ts.data
  }, [api, demo, selected])
  const pollingNeeded = !demo && connected && !!selected && (pending !== null || liveTasks.some(t => ['queued', 'running'].includes(t.status)))
  useEffect(() => {
    if (!pollingNeeded) return
    let stopped = false, fetching = false
    let failed = false
    const poll = async () => {
      if (fetching) return
      fetching = true
      try {
        const result = await api.tasks(selected)
        const completed = result.data.some(task => ['queued', 'running'].includes(taskStates.current.get(task.id) || '') && !['queued', 'running'].includes(task.status))
        if (completed) {
          const history = await api.turns(selected)
          if (!stopped) setLiveTurns(old => Array.from(new Map([...old, ...history.data].map(turn => [turn.id, turn])).values()).sort((a, b) => a.id - b.id))
        }
        if (!stopped) {
          setLiveTasks(old => Array.from(new Map([...old, ...result.data].map(task => [task.id, task])).values()).sort((a, b) => b.created_at - a.created_at || b.id.localeCompare(a.id)))
          failed = false
        }
      } catch { if (!stopped && !failed) { notify('任务状态暂时无法更新，连接恢复后继续检查。', 'error'); failed = true } }
      finally { fetching = false }
    }
    void poll()
    const timer = setInterval(() => { void poll() }, 3000)
    return () => { stopped = true; clearInterval(timer) }
  }, [api, notify, pollingNeeded, selected])

  const connect = async (base: string, token: string) => {
    if (!token.trim()) throw new Error('请填写网关 API 密钥。')
    const gateway = new Gateway(base, token.trim())
    const [h, models] = await Promise.all([gateway.health(), gateway.models()])
    if (!models.data.some(model => model.id === 'storycanvas')) throw new Error('此地址没有提供 storycanvas 模型，请检查是否连接了正确的网关。')
    writeStored('session', 'storycanvas.token', token.trim()); writeStored('local', 'storycanvas.gateway', gateway.base)
    setConnection({ base: gateway.base, token: token.trim() }); setHealth(h)
    notify(h.comfyui_ok ? '已连接网关，插图服务可用。' : '已连接网关；ComfyUI 当前不可用，文字与管理功能仍可使用。')
    navigate('app', 'chat')
  }
  const disconnect = () => {
    if (pendingRef.current) { notify('本轮仍在运行，请等待完成或先取消插图任务。', 'error'); return }
    writeStored('session', 'storycanvas.token', ''); setConnection(old => ({ ...old, token: '' }))
    setDrafts({}); setLiveSaves([]); setLiveTurns([]); setLiveTasks([]); setLiveMemories([]); setHealth(null); setDiagnostics(null); setBackups([])
    notify('网关密钥已从当前会话清除。'); navigate('app', 'settings')
  }
  const chooseSave = (id: string) => {
    if (demo) return
    if (pendingRef.current) { notify('请等待当前回复完成后再切换存档。', 'error'); return }
    setSelected(id)
  }
  const send = async (text: string, forceImage = false, stream = true): Promise<boolean> => {
    if (demo || !connected || !selected || pendingRef.current) return false
    const message = forceImage && !/^\s*(\/|#)(图|image)/i.test(text) ? `/图 ${text}` : text
    const requestId = `web-${crypto.randomUUID()}`
    pendingRef.current = true
    setPending({ saveId: selected, text, content: '', requestId, startedAt: Date.now() })
    try {
      // Legacy memory commands use the server's active save rather than request fields.
      if (/^\s*\/记忆(?:状态)?(?:\s|$)/.test(message)) {
        await api.chat({ model: 'storycanvas', stream: false, story_save_id: selected, messages: [{ role: 'user', content: `/存档 ${selected}` }] }, `web-${crypto.randomUUID()}`)
      }
      const content = await api.chat({ model: 'storycanvas', stream, story_save_id: selected,
        messages: buildMessages(liveTurns, message) }, requestId, partial => setPending(old => old ? { ...old, content: partial } : old))
      // Control commands do not create persisted turns; show their response separately.
      const control = /^\s*(?:\/|#)(图开|图关|image-on|image-off|存档|存档列表|记忆|记忆状态)(?:\s|$)/i.test(message)
      if (control) {
        notify(content)
        if (/^\s*\/存档\s+/.test(message)) {
          const result = await api.saves(); setLiveSaves(result.data); setSelected(result.active_save_id)
        }
      }
      try {
        const refreshed = await refreshStory()
        await refreshSaves(); await refreshHealth()
        const latestId = Math.max(0, ...liveTurns.map(turn => turn.id))
        if (!control && !refreshed?.some(turn => turn.id > latestId && content.startsWith(turn.assistant_text))) {
          setUnconfirmedReply({ saveId: selected, text, content })
          notify('已收到回复，但尚未在历史中确认保存。请检查诊断或刷新历史，本页暂时保留回复。', 'error')
        } else setUnconfirmedReply(null)
      }
      catch { setUnconfirmedReply({ saveId: selected, text, content }); notify('回复已完成，但历史刷新失败。请重新加载历史检查是否已保存。', 'error') }
      return true
    } catch (error) { fail(error); return false }
    finally { pendingRef.current = false; setPending(null) }
  }
  const loadMoreTurns = async () => {
    const result = await api.turns(selected, liveTurns.length)
    setLiveTurns(old => Array.from(new Map([...result.data, ...old].map(t => [t.id, t])).values()).sort((a, b) => a.id - b.id))
    setCanLoadTurns(result.data.length === 30)
  }
  const loadMoreMemories = async () => {
    const result = await api.memories(selected, liveMemories.length)
    setLiveMemories(old => Array.from(new Map([...old, ...result.data].map(m => [m.id, m])).values()))
    setCanLoadMemories(result.data.length === 100)
  }
  const loadMoreTasks = async () => {
    const result = await api.tasks(selected, liveTasks.length)
    setLiveTasks(old => Array.from(new Map([...old, ...result.data].map(t => [t.id, t])).values()))
    setCanLoadTasks(result.data.length === 50)
  }
  return {
    route, demo, connected, api, connection, connect, disconnect,
    saves: demo ? [demoSave] : liveSaves, selected: demo ? demoSave.id : selected, chooseSave,
    turns: demo ? demoTurns : liveTurns, memories: demo ? demoMemories : liveMemories,
    tasks: demo ? [demoTask] : liveTasks, health, diagnostics, backups,
    drafts, setDraft, loading: !demo && loading, resourceError: demo ? '' : resourceError, pending, unconfirmedReply,
    notify, fail, notices, dismissNotice, refreshSaves, refreshHealth, refreshStory, refreshSystem,
    send, canLoadTurns, canLoadMemories, canLoadTasks, loadMoreTurns, loadMoreMemories, loadMoreTasks,
  }
}
export type AppState = ReturnType<typeof useAppState>
export function AppProvider({ children }: { children: ReactNode }) { const state = useAppState(); return <AppContext.Provider value={state}>{children}</AppContext.Provider> }
