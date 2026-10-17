import { useState, type ReactNode } from 'react'
import { Archive, ArrowLeft, BookOpen, Brain, ChevronRight, Images, Info, Menu, Settings, Sparkles, X } from 'lucide-react'
import { useApp } from '../lib/context'
import { navigate } from '../lib/utils'
import type { View } from '../lib/types'
import { Brand, Modal, Notifications } from './ui'

const titles: Record<View, string> = { chat: '故事', saves: '故事', memories: '记忆', gallery: '插图', tasks: '插图任务', status: '系统管理', settings: '设置' }
const storyViews: View[] = ['chat', 'memories', 'gallery', 'tasks']
export function Shell({ children }: { children: ReactNode }) {
  const { route, demo, saves, selected, chooseSave, health, connected, pending, memories } = useApp()
  const [drawer, setDrawer] = useState(false)
  const [info, setInfo] = useState(false)
  const current = saves.find(s => s.id === selected)
  const go = (view: View) => { navigate(route.mode, view); setDrawer(false); setInfo(false) }
  const nav = <>
    <div className="sidebar-brand"><Brand compact/></div>
    {!demo && <button className="new-story button secondary" disabled={!!pending} onClick={() => go('saves')}><Archive size={17}/>全部故事</button>}
    <nav className="story-navigation" aria-label="故事导航"><div className="sidebar-section-label">{demo ? '示例' : '故事'}</div>
      {saves.filter(s => !s.archived_at).slice(0, 5).map(save => <button key={save.id} className={`story-link ${save.id === selected && storyViews.includes(route.view) ? 'selected' : ''}`} disabled={!demo && !!pending} onClick={() => { chooseSave(save.id); go('chat') }}><BookOpen size={16}/><span>{save.name}</span></button>)}
      {!saves.length && <span className="sidebar-empty">连接后显示故事列表。</span>}
    </nav>
    <div className="sidebar-bottom"><a href={`#/${route.mode}/settings`} className={['settings', 'status'].includes(route.view) ? 'active' : ''} onClick={() => setDrawer(false)}><Settings size={17}/>设置</a><a href="#/" onClick={() => setDrawer(false)}><ArrowLeft size={16}/>首页</a></div>
  </>
  return <div className={`app-shell view-${route.view}`}>
    <aside className="sidebar">{nav}</aside>
    {drawer && <Modal title="导航与故事" onClose={() => setDrawer(false)}><div className="mobile-sidebar">{nav}</div></Modal>}
    <div className="main-column"><header className="app-header"><div className="header-left"><button className="icon-button mobile-menu" aria-label="打开导航菜单" onClick={() => setDrawer(true)}><Menu size={21}/></button>{storyViews.includes(route.view) && route.view !== 'chat' && <a className="icon-button" aria-label="返回对话" href={`#/${route.mode}/chat`}><ArrowLeft size={18}/></a>}{route.view === 'status' && <a className="icon-button" aria-label="返回设置" href={`#/${route.mode}/settings`}><ArrowLeft size={18}/></a>}<span className="header-title">{storyViews.includes(route.view) ? current?.name || '故事' : titles[route.view]}</span>{demo && <span className="mode-label">示例 · 只读</span>}</div>
      <div className="header-right">{!demo && <span className={`service-dot ${connected && health?.status === 'ok' ? 'online' : ''}`} title={!connected ? '未连接服务' : health?.comfyui_ok ? '服务已连接' : '插图服务不可用'}><span className="tiny-dot"/><span className="service-label">{!connected ? '未连接' : '已连接'}</span></span>}{storyViews.includes(route.view) && current && <button className="story-info-button" aria-label="查看故事信息" onClick={() => setInfo(true)}><Info size={17}/><span>故事信息</span></button>}</div>
    </header>
    {['memories', 'gallery', 'tasks'].includes(route.view) && <nav className="story-tabs" aria-label="当前故事"><a href={`#/${route.mode}/chat`}>对话</a>{(['memories', 'gallery', 'tasks'] as const).map(view => <a key={view} href={`#/${route.mode}/${view}`} aria-current={route.view === view ? 'page' : undefined}>{titles[view]}</a>)}</nav>}
    <main className="app-main" id="main-content" tabIndex={-1}>{children}</main></div>
    {info && <Modal title="故事信息" onClose={() => setInfo(false)}><div className="story-details"><h3>{current?.name}</h3><p>{current?.turn_count || 0} 轮对话 · {current?.memory_count || 0} 条记忆</p><nav aria-label="故事详情">{[{ view: 'memories', label: '记忆', detail: '人物、物品与经历', icon: Brain }, { view: 'gallery', label: '插图', detail: '查看已生成的场景', icon: Images }, ...(!demo ? [{ view: 'tasks', label: '插图任务', detail: '状态、取消与重试', icon: Sparkles }] : [])].map(({ view, label, detail, icon: Icon }) => <a key={view} href={`#/${route.mode}/${view}`} onClick={() => setInfo(false)}><Icon size={19}/><div><strong>{label}</strong><span>{detail}</span></div><ChevronRight size={17}/></a>)}</nav>{memories.some(m => !m.archived_at && m.status === 'active') && <div className="memory-preview"><h4>近期记忆</h4>{memories.filter(m => !m.archived_at && m.status === 'active').slice(0, 2).map(m => <p key={m.id}>{m.content}</p>)}</div>}</div></Modal>}
    <Notifications/>
  </div>
}
export function ConnectionRequired() {
  return <div className="connection-required"><BookOpen size={36} strokeWidth={1.3}/><h1>连接服务</h1><p>填写服务地址和网关密钥，开始对话。</p><a className="button primary" href="#/app/settings">设置连接 <ChevronRight size={17}/></a><a className="text-button" href="#/demo/chat">浏览示例</a></div>
}
export function DismissibleHelp({ children }: { children: ReactNode }) { const [show, setShow] = useState(true); return show ? <div className="help-note"><div>{children}</div><button className="icon-button" aria-label="关闭说明" onClick={() => setShow(false)}><X size={15}/></button></div> : null }
