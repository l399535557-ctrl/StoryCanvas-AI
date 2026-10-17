import { describe, expect, it, vi, afterEach } from 'vitest'
import { ApiError, Gateway, normalizeBase, readSSE } from './api'
import { buildMessages, imageURL, routeFromHash } from './utils'
import type { Turn } from './types'

afterEach(() => vi.unstubAllGlobals())
function streamResponse(text: string, byteSize = 1) {
  const bytes = new TextEncoder().encode(text)
  return new Response(new ReadableStream({ start(controller) {
    for (let n = 0; n < bytes.length; n += byteSize) controller.enqueue(bytes.slice(n, n + byteSize))
    controller.close()
  } }), { headers: { 'Content-Type': 'text/event-stream' } })
}
const event = (content: string) => `data: ${JSON.stringify({ choices: [{ delta: { content } }] })}\r\n\r\n`
describe('SSE compatibility', () => {
  it('handles fragmented Chinese UTF-8, CRLF, comments and DONE', async () => {
    const updates: string[] = []
    const response = streamResponse(': keepalive\r\n\r\n' + event('你推开') + event('铜门。') + 'data: [DONE]\r\n\r\n')
    expect(await readSSE(response, value => updates.push(value))).toBe('你推开铜门。')
    expect(updates).toEqual(['你推开', '你推开铜门。'])
  })
  it('accepts a terminal DONE without an empty trailing line', async () => {
    expect(await readSSE(streamResponse(event('结束') + 'data: [DONE]'))).toBe('结束')
  })
  it('reports a truncated response rather than marking it successful', async () => {
    await expect(readSSE(streamResponse(event('未完成')))).rejects.toThrow('连接在回复结束前中断')
  })
  it('reports malformed events', async () => {
    await expect(readSSE(streamResponse('data: {bad}\n\ndata: [DONE]\n\n'))).rejects.toThrow('流式响应格式异常')
  })
})
describe('gateway contract and credentials', () => {
  it('sends explicit save IDs, bearer token and request tracing for POST SSE', async () => {
    const fetcher = vi.fn().mockResolvedValue(streamResponse(event('故事') + 'data: [DONE]\n\n'))
    vi.stubGlobal('fetch', fetcher)
    const api = new Gateway('', 'fixture-token')
    const content = await api.chat({ model: 'storycanvas', stream: true, story_save_id: 'save-b', messages: [{ role: 'user', content: '开门' }] }, 'web-test')
    const [url, options] = fetcher.mock.calls[0]
    expect(url).toBe('/v1/chat/completions')
    expect(new Headers(options.headers).get('Authorization')).toBe('Bearer fixture-token')
    expect(new Headers(options.headers).get('X-Request-ID')).toBe('web-test')
    expect(JSON.parse(options.body).story_save_id).toBe('save-b')
    expect(content).toBe('故事')
  })
  it('supports non-streaming responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ choices: [{ message: { content: '文字回复' } }] }))))
    expect(await new Gateway('', 'fixture').chat({ model: 'storycanvas', stream: false, story_save_id: 'a', messages: [{ role: 'user', content: '你好' }] }, 'request')).toBe('文字回复')
  })
  it('hides gateway credentials in errors and keeps a request ID', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'problem fixture-secret', request_id: 'trace-1' }), { status: 502 })))
    try { await new Gateway('', 'fixture-secret').saves(); throw new Error('must fail') }
    catch (error) { expect(error).toBeInstanceOf(ApiError); expect((error as ApiError).message).not.toContain('fixture-secret'); expect((error as ApiError).requestId).toBe('trace-1') }
  })
  it('does not send authorization to health', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response('{}'))
    vi.stubGlobal('fetch', fetcher); await new Gateway('', 'fixture').health()
    expect(new Headers(fetcher.mock.calls[0][1].headers).has('Authorization')).toBe(false)
  })
  it('uses save_id returned by import and copy, and encodes path IDs', async () => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ data: { save_id: 'imported' } }))))
    vi.stubGlobal('fetch', fetcher)
    const api = new Gateway('', 'fixture')
    expect((await api.copySave('a/b', 'imported', '副本')).data.save_id).toBe('imported')
    expect(fetcher.mock.calls[0][0]).toBe('/v1/story/saves/a%2Fb/copy')
    expect((await api.importSave({ format: 'storycanvas-save' })).data.save_id).toBe('imported')
  })
  it('rejects credentials or /v1 embedded in a gateway address', () => {
    expect(normalizeBase('https://example.com/')).toBe('https://example.com')
    expect(() => normalizeBase('https://user:secret@example.com')).toThrow()
    expect(() => normalizeBase('https://example.com/v1')).toThrow()
    expect(() => normalizeBase('https://example.com?token=secret')).toThrow()
    expect(() => normalizeBase('javascript:alert(1)')).toThrow()
  })
})
describe('history and image isolation', () => {
  const turns: Turn[] = [
    { id: 2, user_text: '第二次行动', assistant_text: '新剧情\n![scene](http://localhost:8000/images/a.webp)\n_Image generated locally in 25s._', created_at: 1, image_tasks: [] },
    { id: 1, user_text: '第一次行动', assistant_text: '旧剧情', created_at: 0, image_tasks: [] },
  ]
  it('reconstructs chronological messages without image URLs or timing text', () => {
    const messages = buildMessages(turns, '第三次行动')
    expect(messages.map(m => m.content)).toEqual(['第一次行动', '旧剧情', '第二次行动', '新剧情', '第三次行动'])
    expect(messages.map(m => m.role)).toEqual(['user', 'assistant', 'user', 'assistant', 'user'])
  })
  it('bounds recent context without breaking a turn pair', () => {
    expect(buildMessages(turns, '继续', 2)).toEqual([{ role: 'user', content: '继续' }])
  })
  it('resolves old Windows localhost image URLs through the current gateway', () => {
    expect(imageURL('http://127.0.0.1:8000/images/a.webp', '')).toBe('/images/a.webp')
    expect(imageURL('http://127.0.0.1:8000/images/a.webp', 'https://gateway.example')).toBe('https://gateway.example/images/a.webp')
    expect(imageURL('javascript:alert(1)', '')).toBeUndefined()
  })
  it('uses hash routes so static hosts and /ui/ do not require path rewrites', () => {
    expect(routeFromHash('#/app/memories')).toEqual({ home: false, mode: 'app', view: 'memories' })
    expect(routeFromHash('#/demo/chat')).toEqual({ home: false, mode: 'demo', view: 'chat' })
  })
})
