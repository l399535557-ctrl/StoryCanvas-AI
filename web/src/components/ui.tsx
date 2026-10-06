import { useEffect, useRef, useState, type ReactNode } from 'react'
import { AlertCircle, ArrowUpRight, Check, LoaderCircle, Sparkles, X, ZoomIn } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useApp } from '../lib/context'
import { imageURL } from '../lib/utils'
import type { TaskStatus } from '../lib/types'

export function Brand({ compact = false }: { compact?: boolean }) {
  return <a href="#/" className={`brand ${compact ? 'compact' : ''}`} aria-label="StoryCanvas AI 首页">
    <span className="brand-mark"><Sparkles size={23} strokeWidth={1.5}/></span>
    <span>StoryCanvas<span className="brand-ai">AI</span></span>
  </a>
}
export function Badge({ children, tone = '' }: { children: ReactNode; tone?: string }) { return <span className={`badge ${tone}`}>{children}</span> }
export function Busy({ label = '加载中' }: { label?: string }) { return <span className="busy"><LoaderCircle size={16} className="spin" />{label}</span> }
export function Empty({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return <div className="empty-state"><div className="empty-icon">{icon || <Sparkles size={28}/>}</div><h3>{title}</h3><p>{children}</p></div>
}
export function ErrorNote({ text, retry }: { text: string; retry?: () => void }) {
  return <div role="alert" className="error-note"><AlertCircle size={18}/><span>{text}</span>{retry && <button className="text-button" onClick={retry}>重新加载</button>}</div>
}
export function PageHead({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: ReactNode }) {
  return <div className="page-head"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{actions && <div className="page-actions">{actions}</div>}</div>
}
export function ReadonlyNote() { return <div className="readonly-note"><span className="tiny-dot"/>公开示例 · 内容已预先准备，所有修改操作均已关闭。<a href="#/app/settings">连接网关，开始自己的故事 <ArrowUpRight size={13}/></a></div> }
export function Modal({ title, children, onClose, wide = false, busy = false }: {
  title: string; children: ReactNode; onClose: () => void; wide?: boolean; busy?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => { const dialog = ref.current; dialog?.showModal(); return () => { dialog?.close() } }, [])
  return <dialog ref={ref} className={`modal ${wide ? 'wide' : ''}`} aria-label={title} onCancel={e => { e.preventDefault(); if (!busy) onClose() }} onClick={e => { if (e.target === ref.current && !busy) onClose() }}>
    <div className="modal-head"><h2>{title}</h2><button className="icon-button" aria-label="关闭弹窗" disabled={busy} onClick={onClose}><X size={20}/></button></div>
    <div className="modal-body">{children}</div>
  </dialog>
}
export function Confirm({ title, message, label = '确认', onConfirm, onClose, danger = false, children }: {
  title: string; message: string; label?: string; onConfirm: () => Promise<unknown>; onClose: () => void; danger?: boolean; children?: ReactNode
}) {
  const { fail } = useApp()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const act = async () => {
    setBusy(true); setError('')
    try { await onConfirm(); onClose() } catch (e) { setError(e instanceof Error ? e.message : '操作失败。'); fail(e) }
    finally { setBusy(false) }
  }
  return <Modal title={title} onClose={onClose} busy={busy}><p className="confirm-copy">{message}</p>{children}{error && <ErrorNote text={error}/>}<div className="form-actions"><button className="button secondary" disabled={busy} onClick={onClose}>返回</button><button className={`button ${danger ? 'danger' : 'primary'}`} disabled={busy} onClick={() => void act()}>{busy ? <Busy label="处理中"/> : label}</button></div></Modal>
}
const taskLabels: Record<TaskStatus, string> = { queued: '排队中', running: '生成中', succeeded: '已完成', failed: '失败', cancelled: '已取消' }
export function TaskBadge({ status }: { status: TaskStatus }) { return <Badge tone={status === 'succeeded' ? 'success' : status === 'failed' ? 'error' : status === 'running' ? 'gold' : ''}>{['running', 'queued'].includes(status) && <LoaderCircle size={11} className="spin"/>}{taskLabels[status]}</Badge> }
export function StoryText({ text }: { text: string }) {
  const { api } = useApp()
  return <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{
    img: () => null,
    a: ({ href, children }) => {
      const safe = imageURL(href, api.base)
      return safe ? <a href={safe} target="_blank" rel="noopener noreferrer">{children}</a> : <span>{children}</span>
    },
  }}>{text.replace(/_Image generated locally[^\n]*_/g, '')}</ReactMarkdown></div>
}
export function SceneImage({ src, alt, caption }: { src: string; alt: string; caption?: string }) {
  const [open, setOpen] = useState(false)
  const [broken, setBroken] = useState(false)
  const [attempt, setAttempt] = useState(0)
  return <figure className="scene-figure">
    {broken ? <div className="image-error"><AlertCircle size={20}/><span>插图暂时无法加载</span><button className="text-button" onClick={() => { setBroken(false); setAttempt(n => n + 1) }}>重试加载</button></div> :
      <button className="scene-image-button" aria-label={`放大插图：${alt}`} onClick={() => setOpen(true)}><img key={attempt} src={src} alt={alt} loading="lazy" onError={() => setBroken(true)}/><span className="zoom-hint"><ZoomIn size={14}/>查看原图</span></button>}
    {caption && <figcaption>{caption}</figcaption>}
    {open && <Modal title={alt} wide onClose={() => setOpen(false)}><img className="lightbox-image" src={src} alt={alt}/></Modal>}
  </figure>
}
export function Notifications() {
  const { notices, dismissNotice } = useApp()
  return <div className="notifications" aria-live="polite">{notices.map(item => <div key={item.id} className={`notice ${item.kind}`} role={item.kind === 'error' ? 'alert' : 'status'}>{item.kind === 'error' ? <AlertCircle size={18}/> : <Check size={18}/>}<span>{item.text}</span><button className="icon-button" aria-label="关闭提示" onClick={() => dismissNotice(item.id)}><X size={16}/></button></div>)}</div>
}
