import { useEffect, useRef, useState } from 'react'
import { ArrowRight, ArrowUp, BookOpen, Brain, ChevronRight, ImagePlus, Info, LoaderCircle, RefreshCw, Sparkles, User } from 'lucide-react'
import { Badge, Busy, Empty, ErrorNote, Modal, ReadonlyNote, SceneImage, StoryText, TaskBadge } from '../components/ui'
import { useApp } from '../lib/context'
import { asset, imageURL } from '../lib/utils'
import type { ImageTask } from '../lib/types'

export function Chat() {
  const app = useApp()
  const { demo, turns, memories, tasks, selected, saves, api, loading, pending, health, send, notify, fail } = app
  const draft = app.drafts[selected] || ''
  const [forceImage, setForceImage] = useState(false)
  const [stream, setStream] = useState(true)
  const [infoOpen, setInfoOpen] = useState(false)
  const [commandsOpen, setCommandsOpen] = useState(false)
  const [moreBusy, setMoreBusy] = useState(false)
  const scroll = useRef<HTMLDivElement>(null)
  const area = useRef<HTMLTextAreaElement>(null)
  const current = saves.find(s => s.id === selected)
  const firstTurn = Math.max(0, (current?.turn_count || turns.length) - turns.length)
  const pendingTask = pending ? tasks.find(task => task.request_id === pending.requestId) : undefined
  const updateDraft = (value: string) => app.setDraft(selected, value)
  useEffect(() => {
    const box = scroll.current
    if (box) box.scrollTop = demo ? 0 : box.scrollHeight
  }, [selected, turns.length, pending?.content, demo])
  const submit = async () => {
    if (!draft.trim() || pending || demo) return
    const sent = draft.trim()
    if (await send(sent, forceImage, stream)) { updateDraft(''); setForceImage(false); area.current?.focus() }
  }
  const imageForTask = (task: ImageTask) => demo ? asset('observatory.webp') : task.image_filename ? imageURL(`/images/${task.image_filename}`, api.base) : undefined
  const panel = <div className="context-panel-content"><div className="context-heading"><span className="eyebrow">STORY CONTEXT</span><h2>故事正在记住</h2><p>重要经历，留在这个故事里。</p></div><div className="context-stat"><span>当前存档</span><strong>{current?.name || '未选择'}</strong><div><span><BookOpen size={13}/>{current?.turn_count || 0} 轮对话</span><span><Brain size={13}/>{current?.memory_count || 0} 条记忆</span></div></div>
    <div className="context-section-title"><span>长期记忆</span><a href={`#/${demo ? 'demo' : 'app'}/memories`}>全部 <ChevronRight size={12}/></a></div>
    {memories.filter(m => !m.archived_at && m.status === 'active').slice(0, 3).map(m => <div className="context-memory" key={m.id}><span className="memory-type-label">{{ world: '世界设定', item: '物品', event: '事件', note: '记事', fact: '事实' }[m.memory_type] || m.memory_type}</span><p>{m.content}</p><div className="mini-tags">{m.tags.slice(0, 2).map(tag => <span key={tag}>{tag}</span>)}</div></div>)}
    {!memories.some(m => !m.archived_at && m.status === 'active') && <p className="subtle">故事开始后，重要记忆会出现在这里。</p>}
    <div className="context-section-title"><span>最近的插图任务</span><a href={`#/${demo ? 'demo' : 'app'}/tasks`}>全部 <ChevronRight size={12}/></a></div>
    {tasks.slice(0, 2).map(task => <div className="context-task" key={task.id}><Sparkles size={15}/><div><strong>{task.turn_id ? `轮次 #${task.turn_id} 插图` : '场景插图'}</strong><small>{demo ? '公开示例' : task.backend}</small></div><TaskBadge status={task.status}/></div>)}
    {!tasks.length && <p className="subtle">需要配图时，任务会显示在这里。</p>}
    <div className="context-bottom"><Info size={14}/><p>{demo ? '这里是预先准备的示例。连接网关后，系统会读取你自己的存档和记忆。' : '每轮发送近期对话，并由后端检索当前存档的相关记忆。'}</p></div>
  </div>
  return <div className="chat-layout">
    <div className="chat-main"><div className="chat-toolbar"><div><span className="chapter-label">{demo ? '公开示例 / 第一章' : '互动故事'}</span><Badge tone={demo ? '' : health?.auto_image ? 'gold' : ''}>{demo ? '星海观测站' : health?.auto_image ? '自动插图已开启 · 网关共享' : '自动插图已关闭'}</Badge></div><div><button className="icon-button" aria-label="查看故事记忆和任务" onClick={() => setInfoOpen(true)}><Brain size={18}/></button>{!demo && <button className="icon-button" aria-label="刷新故事历史" disabled={loading || !!pending} onClick={() => app.refreshStory().catch(fail)}><RefreshCw size={16}/></button>}</div></div>
      {demo && <ReadonlyNote/>}
      {app.resourceError && <ErrorNote text={app.resourceError} retry={() => app.refreshStory().catch(fail)}/>}
      <div className="chat-scroll" ref={scroll}>
        <div className="conversation">
          <div className="story-intro"><span className="intro-star">✦</span><span>{demo ? '星海观测站 · 一个关于未知与选择的故事' : '每一次选择，都是新的开始'}</span><div className="intro-line"/></div>
          {app.canLoadTurns && !demo && <button className="button ghost load-history" disabled={moreBusy} onClick={async () => { setMoreBusy(true); const oldHeight = scroll.current?.scrollHeight || 0; try { await app.loadMoreTurns(); requestAnimationFrame(() => { if (scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight - oldHeight }) } catch (e) { fail(e) } finally { setMoreBusy(false) } }}>{moreBusy ? <Busy label="加载中"/> : '加载更早的对话'}</button>}
          {loading ? <div className="chat-skeleton" aria-label="正在加载故事"><div/><div/><div/></div> : turns.length === 0 && <Empty title={selected ? '你的冒险，从一句行动开始。' : '先创建一个故事存档。'}>{selected ? '描述你想做什么，AI 会接续剧情。需要场景插图时，可以开启本轮配图。' : <a href="#/app/saves" className="button primary">创建故事 <ArrowRight size={15}/></a>}</Empty>}
          {turns.map((turn, index) => <div className="story-turn" key={turn.id}>
            <div className="user-message"><div className="user-bubble">{turn.user_text}</div><span className="avatar user-avatar"><User size={15}/></span></div>
            <div className="assistant-message"><span className="avatar ai-avatar"><Sparkles size={16}/></span><div className="assistant-body"><div className="message-label"><strong>StoryCanvas</strong><span>AI</span><small>第 {firstTurn + index + 1} 轮</small></div><StoryText text={turn.assistant_text}/>
              {turn.image_tasks.filter(t => t.status === 'succeeded').map(task => { const src = imageForTask(task); return src ? <SceneImage key={task.id} src={src} alt={`第 ${firstTurn + index + 1} 轮场景`} caption={demo ? '公开仓库示例插图 · 点击查看原图' : `${task.backend}${task.duration_seconds === null ? '' : ` · ${task.duration_seconds.toFixed(1)} 秒`}`}/> : null })}
              {turn.image_tasks.filter(t => t.status !== 'succeeded').map(task => <div key={task.id} className="inline-task"><TaskBadge status={task.status}/><span>本轮插图</span><a href={`#/${demo ? 'demo' : 'app'}/tasks`}>查看任务 <ChevronRight size={12}/></a></div>)}
            </div></div>
          </div>)}
          {app.unconfirmedReply?.saveId === selected && <div className="unconfirmed-reply"><ErrorNote text="已收到回复，但历史刷新失败。下方内容仅在当前页面保留；请先刷新历史确认保存状态，避免重复发送。"/><p className="user-bubble">{app.unconfirmedReply.text}</p><StoryText text={app.unconfirmedReply.content}/></div>}
          {pending?.saveId === selected && <div className="story-turn"><div className="user-message"><div className="user-bubble">{pending.text}</div><span className="avatar user-avatar"><User size={15}/></span></div><div className="assistant-message"><span className="avatar ai-avatar"><Sparkles size={16}/></span><div className="assistant-body"><div className="message-label"><strong>StoryCanvas</strong><span>AI</span></div>{pending.content ? <StoryText text={pending.content}/> : <div className="waiting-state" role="status"><LoaderCircle size={18} className="spin"/><div><strong>{pendingTask ? pendingTask.status === 'failed' ? '插图任务失败，等待网关返回结果…' : pendingTask.status === 'cancelled' ? '插图已取消，等待网关结束本轮…' : '本轮插图正在处理…' : '正在准备这一轮故事…'}</strong><p>文字和插图完成后会一起返回。你可以到任务中心查看状态。</p></div></div>}</div></div></div>}
          {demo && <div className="demo-ending"><span>✦</span><p>故事在这里暂告一段落。<br/><strong>接下来，你会做出怎样的选择？</strong></p><a href="#/app/settings" className="button secondary small">连接网关，开始自己的故事 <ArrowRight size={14}/></a></div>}
        </div>
      </div>
      <div className="composer-wrap"><div className={`composer ${demo ? 'disabled' : ''}`}>
        {demo ? <div className="demo-composer"><BookOpen size={19}/><span>你正在浏览示例，连接网关后即可输入行动。</span><a href="#/app/settings" className="icon-button" aria-label="连接网关开始对话"><ArrowUpRightIcon/></a></div> : <>
          <textarea ref={area} aria-label="输入你的行动或决策" placeholder={selected ? '下一步，你想做什么？' : '创建或选择故事后，输入你的行动…'} value={draft} maxLength={12000} disabled={!selected || !!pending || loading} onChange={e => updateDraft(e.target.value)} onKeyDown={e => {
            // Enter inserts a newline on touch devices; Ctrl/Cmd+Enter always submits.
            const touch = matchMedia('(pointer: coarse)').matches
            if (e.key === 'Enter' && !e.nativeEvent.isComposing && (!touch && !e.shiftKey || e.ctrlKey || e.metaKey)) { e.preventDefault(); void submit() }
          }}/>
          <div className="composer-controls"><div><button className={`composer-toggle ${forceImage ? 'selected' : ''}`} aria-pressed={forceImage} disabled={!!pending || !selected} onClick={() => setForceImage(!forceImage)}><ImagePlus size={16}/><span>本轮配图</span></button><button className="composer-toggle command-button" onClick={() => setCommandsOpen(true)} aria-label="查看可用指令">/<span>指令</span></button><label className="stream-toggle"><input type="checkbox" checked={stream} disabled={!!pending} onChange={e => setStream(e.target.checked)}/>分块返回</label></div><button className="send-button" aria-label="发送行动" disabled={!draft.trim() || !selected || !!pending || loading} onClick={() => void submit()}>{pending ? <LoaderCircle size={20} className="spin"/> : <ArrowUp size={21}/>}</button></div>
        </>}
      </div><p className="composer-footnote">{demo ? '只读示例 · 不调用模型，不保存你的输入' : 'AI 生成内容 · Enter 发送，Shift + Enter 换行；手机回车换行'}</p></div>
    </div>
    <aside className="context-panel">{panel}</aside>
    {infoOpen && <Modal title="故事记忆与任务" onClose={() => setInfoOpen(false)}>{panel}</Modal>}
    {commandsOpen && <Modal title="现有故事指令" onClose={() => setCommandsOpen(false)}><p className="subtle">这些指令由现有后端处理。插图开关是网关共享设置。</p><div className="command-list">{[
      ['/图 ', '本轮强制配图，请在后面填写行动'], ['/图开', '开启自动插图'], ['/图关', '关闭自动插图'],
      ['/存档 ', '按 ID 或名称创建、切换存档'], ['/存档列表', '查看后端存档列表'], ['/记忆 ', '手动写入当前存档的长期事实'], ['/记忆状态', '查看记忆状态'],
    ].map(([cmd, desc]) => <button key={cmd} onClick={() => { if (pending) { notify('请等待当前回复完成。', 'error'); return } updateDraft(cmd); setCommandsOpen(false); area.current?.focus() }}><code>{cmd.trim()}</code><span>{desc}</span><ChevronRight size={14}/></button>)}</div><p className="subtle">也支持英文 /image、/image-on、/image-off，以及 #图、#图开、#图关。</p></Modal>}
  </div>
}
function ArrowUpRightIcon() { return <ArrowRight size={19}/> }
