import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App } from './App'
import type { ImageTask, Save, Turn } from './lib/types'
import { demoMemories, demoSave } from './lib/demo'

beforeEach(() => { history.replaceState(null, '', '/'); sessionStorage.clear(); localStorage.clear() })
afterEach(() => vi.unstubAllGlobals())
function at(hash: string) { history.replaceState(null, '', `/${hash}`) }
function json(data: unknown, status = 200) { return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } }) }
function liveFixture(options: { failChat?: boolean; unsaved?: boolean; secondSave?: boolean; task?: ImageTask } = {}) {
  let saves: Save[] = [{ ...demoSave, id: 'story-a', name: '故事甲' }]
  if (options.secondSave) saves.push({ ...demoSave, id: 'story-b', name: '故事乙' })
  const turns: Record<string, Turn[]> = { 'story-a': [{ id: 1, user_text: '甲的行动', assistant_text: '甲的剧情', created_at: 1, image_tasks: [] }], 'story-b': [{ id: 2, user_text: '乙的行动', assistant_text: '乙的剧情', created_at: 2, image_tasks: [] }] }
  let tasks = options.task ? [options.task] : []
  let memories = demoMemories.map(m => ({ ...m }))
  const fetcher = vi.fn(async (raw: string | URL | Request, init?: RequestInit) => {
    const path = String(raw), method = init?.method || 'GET'
    if (path === '/health') return json({ status: 'ok', configuration: { llm_api_key: true }, comfyui_ok: true, device: 'Fixture GPU', image_backend: 'comfy-sdxl', auto_image: false, memory: { enabled: true, extract_enabled: true, active_save_id: 'story-a', top_k: 8, context_max_chars: 6000 } })
    if (path === '/v1/models') return json({ data: [{ id: 'storycanvas' }] })
    if (path === '/v1/story/saves?include_archived=true') return json({ active_save_id: 'story-a', data: saves })
    if (path === '/v1/story/saves' && method === 'POST') {
      const body = JSON.parse(String(init?.body)); const save = { ...demoSave, id: body.id || 'new-story', name: body.name, turn_count: 0, memory_count: 0 }; saves = [...saves, save]; turns[save.id] = []; return json({ data: save }, 201)
    }
    if (path === '/v1/story/saves/story-a' && method === 'DELETE') {
      saves = saves.map(s => s.id === 'story-a' ? { ...s, archived_at: 10 } : s); return json({ data: saves[0] })
    }
    if (/\/turns\?/.test(path)) { const id = path.split('/')[4]; return json({ data: (turns[id] || []).map(turn => ({ ...turn, image_tasks: tasks.filter(task => task.turn_id === turn.id) })) }) }
    if (/\/memories\?/.test(path)) return json({ data: memories })
    if (path.includes('/v1/story/tasks?')) return json({ data: tasks })
    if (/\/memories\/\d+$/.test(path) && method === 'PATCH') {
      const body = JSON.parse(String(init?.body)); const id = Number(path.split('/').pop()); memories = memories.map(m => m.id === id ? { ...m, ...body, memory_type: body.type } : m); return json({ data: memories.find(m => m.id === id) })
    }
    if (path.endsWith('/retry')) { tasks = [...tasks, { ...tasks[0], id: 'retry-1', status: 'queued' as const, retry_of_task_id: tasks[0].id }]; return json({ data: tasks.at(-1) }, 202) }
    if (path.endsWith('/cancel')) { tasks = tasks.map(t => ({ ...t, status: 'cancelled' as const })); return json({ data: tasks[0] }) }
    if (path === '/v1/chat/completions') {
      if (options.failChat) return json({ detail: 'ComfyUI offline', request_id: 'fixture-trace' }, 502)
      const body = JSON.parse(String(init?.body)); const last = body.messages.at(-1).content
      if (!last.startsWith('/') && !options.unsaved) turns[body.story_save_id] = [...(turns[body.story_save_id] || []), { id: 3, user_text: last, assistant_text: '本轮完整剧情', created_at: 3, image_tasks: [] }]
      return json({ choices: [{ message: { content: '本轮完整剧情' } }] })
    }
    if (path === '/v1/story/diagnostics') return json({ version: '0.13.0', database: { integrity: 'ok', schema_version: 7, journal_mode: 'wal', database_size_bytes: 1024, fts_enabled: true, task_status_counts: { queued: 0, running: 0, succeeded: 1, failed: 0, cancelled: 0 }, counts: { memory_count: 3, turn_count: 1, save_count: 1 } } })
    if (path === '/v1/story/backups') return json({ data: [{ filename: 'storycanvas-fixture.sqlite3', size_bytes: 1024, created_at: 1 }] })
    if (path.endsWith('/storycanvas-fixture.sqlite3/restore')) return json({ data: { safety_backup: 'storycanvas-before-fixture.sqlite3' } })
    return json({ detail: `Unmatched fixture route: ${method} ${path}` }, 404)
  })
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}
function connected() { sessionStorage.setItem('storycanvas.token', 'fixture-only-token'); localStorage.setItem('storycanvas.save', 'story-a') }

describe('public, read-only demonstration', () => {
  it('renders the homepage without contacting a gateway', () => {
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); render(<App/>)
    expect(screen.getByRole('heading', { name: /输入行动，\s*生成故事与插图。/ })).toBeInTheDocument()
    screen.getAllByRole('link', { name: '浏览示例' }).forEach(link => expect(link).toHaveAttribute('href', '#/demo/chat'))
    expect(fetcher).not.toHaveBeenCalled()
  })
  it('shows the sample conversation and related illustration without a composer or network', () => {
    at('#/demo/chat'); const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); render(<App/>)
    expect(screen.getByText('我拿起月纹钥匙，尝试启动控制台。')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: '第 3 轮场景' })).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: '输入你的行动或决策' })).not.toBeInTheDocument()
    expect(fetcher).not.toHaveBeenCalled()
  })
  it('omits memory mutation actions in demonstration mode', () => {
    at('#/demo/memories'); const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); render(<App/>)
    expect(screen.queryByRole('button', { name: '新增记忆' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '编辑' })).not.toBeInTheDocument()
    expect(fetcher).not.toHaveBeenCalled()
  })
  it('opens and closes the mobile navigation and image viewer', async () => {
    at('#/demo/chat'); render(<App/>); const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: '打开导航菜单' }))
    expect(screen.getByRole('dialog', { name: '导航与故事' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '关闭弹窗' }))
    await user.click(screen.getByRole('button', { name: '放大插图：第 3 轮场景' }))
    expect(screen.getByRole('dialog', { name: '第 3 轮场景' })).toBeInTheDocument()
  })
  it('reveals story details only when requested and keeps its memory route reachable', async () => {
    at('#/demo/chat'); const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); render(<App/>); const user = userEvent.setup()
    expect(screen.queryByRole('navigation', { name: '故事详情' })).not.toBeInTheDocument()
    expect(screen.queryByRole('complementary')).not.toHaveClass('context-panel')
    await user.click(screen.getByRole('button', { name: '查看故事信息' }))
    const dialog = screen.getByRole('dialog', { name: '故事信息' })
    await user.click(within(dialog).getByRole('link', { name: /记忆 人物/ }))
    await screen.findByRole('heading', { name: '记忆' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(fetcher).not.toHaveBeenCalled()
  })
})
describe('live-mode API contract fixtures', () => {
  it('keeps system management discoverable under advanced settings', async () => {
    at('#/app/settings'); connected(); liveFixture(); render(<App/>); const user = userEvent.setup()
    expect(screen.getByRole('link', { name: /系统管理 服务诊断/ })).not.toBeVisible()
    await user.click(screen.getByText('高级与帮助'))
    await user.click(screen.getByRole('link', { name: /系统管理 服务诊断/ }))
    await screen.findByText('storycanvas-fixture.sqlite3')
    expect(window.location.hash).toBe('#/app/status')
  })
  it('reveals command options on demand and returns the selected command to the composer', async () => {
    at('#/app/chat'); connected(); liveFixture(); render(<App/>); const user = userEvent.setup()
    await screen.findByText('甲的剧情')
    expect(screen.queryByRole('checkbox', { name: '分块返回' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '更多发送选项' }))
    const dialog = screen.getByRole('dialog', { name: '发送选项' })
    await user.click(within(dialog).getByText('指令帮助'))
    await user.click(within(dialog).getByRole('button', { name: '/图 本轮配图' }))
    expect(screen.getByLabelText('输入你的行动或决策')).toHaveValue('/图 ')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
  it('validates a gateway and stores only its token in session storage', async () => {
    at('#/app/settings'); liveFixture(); render(<App/>); const user = userEvent.setup()
    await user.type(screen.getByLabelText('网关 API 密钥'), 'fixture-only-token')
    await user.click(screen.getByRole('button', { name: '连接服务' }))
    await screen.findByText('甲的剧情')
    expect(sessionStorage.getItem('storycanvas.token')).toBe('fixture-only-token')
    expect(localStorage.getItem('storycanvas.token')).toBeNull()
    expect(window.location.hash).toBe('#/app/chat')
  })
  it('isolates the selected save and submits only that save context', async () => {
    at('#/app/chat'); connected(); const fetcher = liveFixture({ secondSave: true }); render(<App/>); const user = userEvent.setup()
    await screen.findByText('甲的剧情')
    await user.click(screen.getByRole('button', { name: '故事乙' }))
    await screen.findByText('乙的剧情'); expect(screen.queryByText('甲的剧情')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('输入你的行动或决策'), '向前走')
    await user.click(screen.getByRole('button', { name: '发送行动' }))
    await screen.findByText('本轮完整剧情')
    const call = fetcher.mock.calls.find(([url]) => String(url) === '/v1/chat/completions')!
    const body = JSON.parse(String(call[1]?.body))
    expect(body.story_save_id).toBe('story-b')
    expect(body.messages.map((m: { content: string }) => m.content)).toEqual(['乙的行动', '乙的剧情', '向前走'])
    expect(localStorage.getItem('storycanvas.save')).toBe('story-b')
  })
  it('preserves input after a failed generation and exposes the request trace', async () => {
    at('#/app/chat'); connected(); liveFixture({ failChat: true }); render(<App/>); const user = userEvent.setup()
    await screen.findByText('甲的剧情')
    await user.type(screen.getByLabelText('输入你的行动或决策'), '不要丢掉我的行动')
    await user.click(screen.getByRole('button', { name: '发送行动' }))
    await screen.findByText(/fixture-trace/)
    expect(screen.getByLabelText('输入你的行动或决策')).toHaveValue('不要丢掉我的行动')
  })
  it('creates a save through the real route and selects the returned ID', async () => {
    at('#/app/saves'); connected(); const fetcher = liveFixture(); render(<App/>); const user = userEvent.setup()
    await screen.findByRole('heading', { name: '故事甲' })
    await user.click(screen.getByRole('button', { name: '新建故事' }))
    const dialog = screen.getByRole('dialog')
    await user.type(within(dialog).getByLabelText('故事名称'), '新的世界')
    await user.click(within(dialog).getByRole('button', { name: '确认' }))
    await screen.findByRole('heading', { name: '新的世界' })
    expect(localStorage.getItem('storycanvas.save')).toBe('new-story')
    expect(fetcher.mock.calls.some(([url, init]) => String(url) === '/v1/story/saves' && init?.method === 'POST')).toBe(true)
  })
  it('edits memory with the API type alias and refreshes the displayed fact', async () => {
    at('#/app/memories'); connected(); const fetcher = liveFixture(); render(<App/>); const user = userEvent.setup()
    await screen.findByText(demoMemories[0].content)
    await user.click(screen.getAllByRole('button', { name: '编辑' })[0])
    const dialog = screen.getByRole('dialog'); const content = within(dialog).getByLabelText(/记忆内容/)
    await user.clear(content); await user.type(content, '修正后的观测站事实')
    await user.click(within(dialog).getByRole('button', { name: '保存记忆' }))
    await screen.findByText('修正后的观测站事实')
    const call = fetcher.mock.calls.find(([, init]) => init?.method === 'PATCH')!
    expect(JSON.parse(String(call[1]?.body)).type).toBe('world')
  })
  it('requires exact filename confirmation before whole-database restore', async () => {
    at('#/app/status'); connected(); const fetcher = liveFixture(); render(<App/>); const user = userEvent.setup()
    await screen.findByText('storycanvas-fixture.sqlite3')
    await user.click(screen.getByRole('button', { name: '恢复' }))
    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: '我已了解，继续恢复' }))
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/storycanvas-fixture.sqlite3/restore'))).toBe(false)
    const input = within(dialog).getByLabelText('输入完整备份文件名确认整库恢复')
    fireEvent.change(input, { target: { value: 'storycanvas-fixture.sqlite3' } })
    await user.click(within(dialog).getByRole('button', { name: '我已了解，继续恢复' }))
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/storycanvas-fixture.sqlite3/restore'))).toBe(true))
  })
  it('keeps a received reply visible if the backend did not persist a turn', async () => {
    at('#/app/chat'); connected(); liveFixture({ unsaved: true }); render(<App/>); const user = userEvent.setup()
    await screen.findByText('甲的剧情')
    await user.type(screen.getByLabelText('输入你的行动或决策'), '还没有保存的行动')
    await user.click(screen.getByRole('button', { name: '发送行动' }))
    await screen.findByText('本轮完整剧情')
    expect(await screen.findByText(/已收到回复，但尚未在历史中确认保存/)).toBeInTheDocument()
    expect(screen.getByText('还没有保存的行动')).toBeInTheDocument()
  })
  it('cancels a running illustration through its task ID', async () => {
    at('#/app/tasks'); connected()
    const task: ImageTask = { id: 'running-1', save_id: 'story-a', turn_id: 1, request_id: 'fixture-request', status: 'running', image_filename: null, error: null, created_at: 1, started_at: 1, finished_at: null, duration_seconds: null, retry_of_task_id: null, backend: 'comfy-sdxl' }
    const fetcher = liveFixture({ task }); render(<App/>); const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: '取消任务' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '取消插图任务' }))
    await waitFor(() => expect(document.querySelector('.badge')?.textContent).toBe('已取消'))
    expect(fetcher.mock.calls.some(([url, init]) => String(url) === '/v1/story/tasks/running-1/cancel' && init?.method === 'POST')).toBe(true)
  })
  it('cancels an illustration directly beside its story reply', async () => {
    at('#/app/chat'); connected()
    const task: ImageTask = { id: 'inline-1', save_id: 'story-a', turn_id: 1, request_id: 'fixture-request', status: 'running', image_filename: null, error: null, created_at: 1, started_at: 1, finished_at: null, duration_seconds: null, retry_of_task_id: null, backend: 'comfy-sdxl' }
    const fetcher = liveFixture({ task }); render(<App/>); const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: '取消任务' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '取消插图任务' }))
    await screen.findByText('已取消')
    expect(fetcher.mock.calls.some(([url]) => String(url) === '/v1/story/tasks/inline-1/cancel')).toBe(true)
    expect(window.location.hash).toBe('#/app/chat')
  })
  it('retries a failed illustration without sending another story generation request', async () => {
    at('#/app/tasks'); connected()
    const task: ImageTask = { id: 'failed-1', save_id: 'story-a', turn_id: 1, request_id: 'fixture-request', status: 'failed', image_filename: null, error: 'fixture failure', created_at: 1, started_at: 1, finished_at: 2, duration_seconds: null, retry_of_task_id: null, backend: 'comfy-sdxl' }
    const fetcher = liveFixture({ task }); render(<App/>); const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: '重试插图' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '重试插图' }))
    await screen.findByText('排队中')
    expect(fetcher.mock.calls.some(([url]) => String(url) === '/v1/story/tasks/failed-1/retry')).toBe(true)
    expect(fetcher.mock.calls.some(([url]) => String(url) === '/v1/chat/completions')).toBe(false)
  })
  it('aligns the backend active save before archiving a different selected story', async () => {
    at('#/app/saves'); connected(); localStorage.setItem('storycanvas.save', 'story-b')
    const fetcher = liveFixture({ secondSave: true }); render(<App/>); const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: '故事甲 更多操作' }))
    await user.click(screen.getByRole('button', { name: '归档故事' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '确认归档' }))
    await waitFor(() => expect(screen.queryByRole('heading', { name: '故事甲' })).not.toBeInTheDocument())
    const calls = fetcher.mock.calls
    const switchIndex = calls.findIndex(([url, init]) => String(url) === '/v1/chat/completions' && JSON.parse(String(init?.body)).messages[0].content === '/存档 story-b')
    const archiveIndex = calls.findIndex(([url, init]) => String(url) === '/v1/story/saves/story-a' && init?.method === 'DELETE')
    expect(switchIndex).toBeGreaterThan(-1); expect(archiveIndex).toBeGreaterThan(switchIndex)
  })

})
