import { useState, type ReactNode } from 'react'
import { Activity, Archive, ArrowLeft, BookOpen, Brain, ChevronRight, Images, Menu, MessageCircle, Plus, Settings, Sparkles, X } from 'lucide-react'
import { useApp } from '../lib/context'
import { navigate } from '../lib/utils'
import type { View } from '../lib/types'
import { Badge, Brand, Modal, Notifications } from './ui'

const links = [
  { view: 'chat', label: '故事工作台', icon: MessageCircle },
  { view: 'saves', label: '故事存档', icon: Archive },
  { view: 'memories', label: '长期记忆', icon: Brain },
  { view: 'gallery', label: '插图画廊', icon: Images },
  { view: 'tasks', label: '生成任务', icon: Sparkles },
  { view: 'status', label: '系统状态', icon: Activity },
] as const
export function Shell({ children }: { children: ReactNode }) {
  const { route, demo, saves, selected, chooseSave, health, connected, pending } = useApp()
  const [drawer, setDrawer] = useState(false)
  const current = saves.find(s => s.id === selected)
  const go = (view: View) => { navigate(route.mode, view); setDrawer(false) }
  const nav = <>
    <div className="sidebar-brand"><Brand compact/></div>
    <div className={`mode-label ${demo ? '' : 'live'}`}><span className="tiny-dot"/>{demo ? '公开示例 · 只读浏览' : connected ? '我的故事空间' : '等待连接网关'}</div>
    <nav className="side-nav" aria-label="工作台导航">{links.map(({ view, label, icon: Icon }) => <a key={view} href={`#/${route.mode}/${view}`} onClick={() => setDrawer(false)} aria-current={view === route.view ? 'page' : undefined} className={view === route.view ? 'active' : ''}><Icon size={18} strokeWidth={1.6}/><span>{label}</span>{view === route.view && <span className="nav-dot"/>}</a>)}</nav>
    <div className="sidebar-stories"><div className="sidebar-section-label"><span>{demo ? '示例故事' : '最近的故事'}</span>{!demo && <button className="icon-button" aria-label="管理或新建故事" onClick={() => go('saves')}><Plus size={16}/></button>}</div>
      {saves.filter(s => !s.archived_at).slice(0, 5).map(save => <button key={save.id} className={`story-link ${save.id === selected ? 'selected' : ''}`} disabled={!demo && !!pending} onClick={() => { chooseSave(save.id); go('chat') }}><BookOpen size={15}/><span>{save.name}</span></button>)}
      {!saves.length && <span className="sidebar-empty">连接网关后，你的故事会显示在这里。</span>}
    </div>
    <div className="sidebar-bottom"><a href={`#/${route.mode}/settings`} className={route.view === 'settings' ? 'active' : ''} onClick={() => setDrawer(false)}><Settings size={17}/>连接设置</a><a href="#/" onClick={() => setDrawer(false)}><ArrowLeft size={16}/>回到首页</a><div className="sidebar-footnote">STORYCANVAS AI <span>WEB 0.1</span></div></div>
  </>
  return <div className={`app-shell view-${route.view}`}>
    <aside className="sidebar">{nav}</aside>
    {drawer && <Modal title="导航与故事" onClose={() => setDrawer(false)}><div className="mobile-sidebar">{nav}</div></Modal>}
    <div className="main-column"><header className="app-header"><div className="header-left"><button className="icon-button mobile-menu" aria-label="打开导航菜单" onClick={() => setDrawer(true)}><Menu size={21}/></button><span className="breadcrumb">故事空间 <ChevronRight size={13}/></span><span className="header-title">{route.view === 'chat' ? current?.name || '新的冒险' : links.find(l => l.view === route.view)?.label || '连接设置'}</span></div>
      <div className="header-right">{demo ? <Badge tone="gold">只读示例</Badge> : <span className={`service-dot ${connected && health?.status === 'ok' ? 'online' : ''}`}><span className="tiny-dot"/>{!connected ? '未连接' : !health ? '待检测' : health.comfyui_ok ? '网关已连接' : '插图服务离线'}</span>}<button className="icon-button header-settings" aria-label="打开连接设置" onClick={() => go('settings')}><Settings size={18}/></button></div>
    </header>
    <main className="app-main" id="main-content" tabIndex={-1}>{children}</main></div>
    <Notifications/>
  </div>
}
export function ConnectionRequired() {
  return <div className="connection-required"><span className="large-brand"><Sparkles size={35}/></span><span className="eyebrow">YOUR NEXT ADVENTURE</span><h1>连接网关，<br/>开始你的故事。</h1><p>故事与插图由你的后端生成。<br/>填写网关地址和密钥，即可进入工作台。</p><a className="button primary" href="#/app/settings">设置连接 <ChevronRight size={17}/></a><a className="text-button" href="#/demo/chat">先浏览示例 <ChevronRight size={14}/></a></div>
}
export function DismissibleHelp({ children }: { children: ReactNode }) { const [show, setShow] = useState(true); return show ? <div className="help-note"><div>{children}</div><button className="icon-button" aria-label="关闭说明" onClick={() => setShow(false)}><X size={15}/></button></div> : null }
