import type { Backup, ChatPayload, DataList, Diagnostics, Health, ImageTask, Memory, MemoryInput, Save, SaveList, Turn } from './types'

export class ApiError extends Error {
  constructor(message: string, public status = 0, public requestId?: string) { super(message); this.name = 'ApiError' }
}
export function normalizeBase(value: string): string {
  const input = value.trim().replace(/\/+$/, '')
  if (!input) return ''
  const url = new URL(input)
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error('请输入不含密钥、查询参数或片段的 HTTP(S) 网关地址。')
  }
  if (url.pathname !== '/' && url.pathname !== '') throw new Error('填写网关根地址，不要追加 /v1 或 /ui。')
  return url.origin
}

// Fetch POST SSE: supports fragmented UTF-8, CRLF, comments and multiple data lines.
export async function readSSE(response: Response, onContent?: (content: string) => void): Promise<string> {
  if (!response.body) throw new ApiError('服务没有返回可读取的流。')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = '', content = '', done = false
  const consume = (block: string) => {
    const data = block.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n').trim()
    if (!data) return
    if (data === '[DONE]') { done = true; return }
    let chunk: { choices?: { delta?: { content?: string } }[]; error?: { message?: string } }
    try { chunk = JSON.parse(data) } catch { throw new ApiError('流式响应格式异常，请重新加载历史检查本轮是否已保存。') }
    if (chunk.error) throw new ApiError('生成流返回错误，请检查任务和服务状态。')
    const text = chunk.choices?.[0]?.delta?.content
    if (typeof text === 'string') { content += text; onContent?.(content) }
  }
  try {
    while (!done) {
      const part = await reader.read()
      buffer += decoder.decode(part.value, { stream: !part.done })
      // Normalize only complete CRLF pairs; an unfinished trailing CR stays buffered.
      buffer = buffer.replace(/\r\n/g, '\n')
      let split = buffer.indexOf('\n\n')
      while (split >= 0 && !done) {
        consume(buffer.slice(0, split)); buffer = buffer.slice(split + 2); split = buffer.indexOf('\n\n')
      }
      if (part.done) {
        if (buffer.trim() && !done) consume(buffer.trim())
        break
      }
    }
    if (!done) throw new ApiError('连接在回复结束前中断。请先检查历史和任务，避免重复发送。')
    return content
  } finally { await reader.cancel().catch(() => undefined); reader.releaseLock() }
}

const enc = encodeURIComponent
export class Gateway {
  readonly base: string
  constructor(base: string, private token: string) { this.base = normalizeBase(base) }
  private async request<T>(path: string, options: RequestInit = {}, parse?: (response: Response) => Promise<T>, timeout = 20_000): Promise<T> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeout)
    const headers = new Headers(options.headers)
    if (path.startsWith('/v1')) headers.set('Authorization', `Bearer ${this.token}`)
    if (options.body) headers.set('Content-Type', 'application/json')
    try {
      const response = await fetch(`${this.base}${path}`, { ...options, headers, signal: controller.signal, cache: 'no-store' })
      if (!response.ok) {
        const data = await response.json().catch(() => ({})) as { detail?: unknown; request_id?: string }
        const descriptions: Record<number, string> = {
          401: '网关密钥无效，请在连接设置中重新填写。', 404: '记录不存在，可能已被另一端修改。',
          409: '当前状态不允许此操作，请刷新列表或先恢复归档记录。', 422: '输入不符合接口要求，请检查字段。',
          502: '生成服务返回错误，请检查模型连接和插图任务。',
        }
        let detail = typeof data.detail === 'string' ? data.detail.slice(0, 350) : ''
        if (this.token) detail = detail.split(this.token).join('[已隐藏]')
        const message = descriptions[response.status] || `请求失败（${response.status}）。`
        throw new ApiError(`${message}${detail && response.status !== 401 ? ` ${detail}` : ''}`, response.status, data.request_id || response.headers.get('X-Request-ID') || undefined)
      }
      return parse ? await parse(response) : await response.json() as T
    } catch (error) {
      if (error instanceof ApiError) throw error
      if (controller.signal.aborted) throw new ApiError('请求超时。生成可能仍在后端继续，请先检查历史和任务，避免重复发送。')
      throw new ApiError('无法连接网关。请检查服务地址、开发代理、网络和跨域配置。')
    } finally { clearTimeout(timer) }
  }
  private mutate<T>(path: string, method: string, body?: unknown) {
    return this.request<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) })
  }
  health = () => this.request<Health>('/health')
  models = () => this.request<{ data: { id: string }[] }>('/v1/models')
  diagnostics = () => this.request<Diagnostics>('/v1/story/diagnostics')
  saves = () => this.request<SaveList>('/v1/story/saves?include_archived=true')
  createSave = (name: string, id?: string) => this.mutate<{ data: Save }>('/v1/story/saves', 'POST', { name, ...(id ? { id } : {}) })
  renameSave = (id: string, name: string) => this.mutate(`/v1/story/saves/${enc(id)}`, 'PATCH', { name })
  saveAction = (id: string, action: 'archive' | 'restore') => this.mutate(`/v1/story/saves/${enc(id)}${action === 'restore' ? '/restore' : ''}`, action === 'archive' ? 'DELETE' : 'POST')
  copySave = (source: string, id: string, name: string) => this.mutate<{ data: { save_id: string } }>(`/v1/story/saves/${enc(source)}/copy`, 'POST', { id, name })
  importSave = (bundle: unknown, target_id?: string, target_name?: string) => this.mutate<{ data: { save_id: string } }>('/v1/story/saves/import', 'POST', { bundle, ...(target_id ? { target_id } : {}), ...(target_name ? { target_name } : {}) })
  exportSave = (id: string) => this.request<unknown>(`/v1/story/saves/${enc(id)}/export?include_archived=true`)
  publication = (id: string) => this.request<Blob>(`/v1/story/saves/${enc(id)}/publication`, {}, res => res.blob(), 60_000)
  turns = (id: string, offset = 0, limit = 30) => this.request<DataList<Turn>>(`/v1/story/saves/${enc(id)}/turns?limit=${limit}&offset=${offset}`)
  memories = (id: string, offset = 0) => this.request<DataList<Memory>>(`/v1/story/saves/${enc(id)}/memories?include_archived=true&limit=100&offset=${offset}`)
  addMemory = (id: string, memory: MemoryInput) => this.mutate(`/v1/story/saves/${enc(id)}/memories`, 'POST', memory)
  editMemory = (id: string, memoryId: number, memory: MemoryInput) => this.mutate(`/v1/story/saves/${enc(id)}/memories/${memoryId}`, 'PATCH', memory)
  memoryAction = (id: string, memoryId: number, action: 'archive' | 'restore' | 'conflict' | 'activate') => this.mutate(`/v1/story/saves/${enc(id)}/memories/${memoryId}${action === 'archive' ? '' : `/${action}`}`, action === 'archive' ? 'DELETE' : 'POST')
  supersedeMemory = (id: string, memoryId: number, memory: MemoryInput) => this.mutate(`/v1/story/saves/${enc(id)}/memories/${memoryId}/supersede`, 'POST', memory)
  tasks = (id?: string, offset = 0) => this.request<DataList<ImageTask>>(`/v1/story/tasks?limit=50&offset=${offset}${id ? `&save_id=${enc(id)}` : ''}`)
  taskAction = (id: string, action: 'cancel' | 'retry') => this.mutate<{ data: ImageTask }>(`/v1/story/tasks/${enc(id)}/${action}`, 'POST')
  backups = () => this.request<DataList<Backup>>('/v1/story/backups')
  createBackup = (label: string) => this.mutate<{ data: Backup }>('/v1/story/backups', 'POST', { label: label || undefined })
  restoreBackup = (filename: string) => this.mutate<{ data: { safety_backup: string } }>(`/v1/story/backups/${enc(filename)}/restore`, 'POST', undefined)
  async chat(payload: ChatPayload, requestId: string, onContent?: (content: string) => void) {
    return this.request<string>('/v1/chat/completions', {
      method: 'POST', body: JSON.stringify(payload), headers: { 'X-Request-ID': requestId },
    }, async res => {
      if ((res.headers.get('Content-Type') || '').includes('text/event-stream')) return readSSE(res, onContent)
      const body = await res.json() as { choices?: { message?: { content?: string } }[] }
      const result = body.choices?.[0]?.message?.content
      if (typeof result !== 'string') throw new ApiError('回复结构异常，请检查历史是否已保存。')
      onContent?.(result); return result
    }, 720_000)
  }
}
