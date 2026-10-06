import { useEffect, useRef, useState } from 'react'
import { ArrowRight, ArrowUp, BookOpen, ImagePlus, LoaderCircle, MoreHorizontal, RefreshCw } from 'lucide-react'
import { Busy, Empty, ErrorNote, Modal, SceneImage, StoryText, TaskBadge } from '../components/ui'
import { TaskAction } from '../components/TaskAction'
import { useApp } from '../lib/context'
import { asset, imageURL } from '../lib/utils'
import type { ImageTask } from '../lib/types'

export function Chat() {
  const app = useApp()
  const { demo, turns, tasks, selected, saves, api, loading, pending, health, send, notify, fail } = app
  const draft = app.drafts[selected] || ''
  const [forceImage, setForceImage] = useState(false)
  const [optionsOpen, setOptionsOpen] = useState(false)
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
    if (await send(sent, forceImage, true)) { updateDraft(''); setForceImage(false); area.current?.focus() }
  }
  const imageForTask = (task: ImageTask) => demo ? asset('observatory.webp') : task.image_filename ? imageURL(`/images/${task.image_filename}`, api.base) : undefined
  return <div className="chat-layout"><div className="chat-main">
    {app.resourceError && <ErrorNote text={app.resourceError} retry={() => app.refreshStory().catch(fail)}/>}
    <div className="chat-scroll" ref={scroll}><div className="conversation">
      {app.canLoadTurns && !demo && <button className="button ghost load-history" disabled={moreBusy} onClick={async () => { setMoreBusy(true); const oldHeight = scroll.current?.scrollHeight || 0; try { await app.loadMoreTurns(); requestAnimationFrame(() => { if (scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight - oldHeight }) } catch (e) { fail(e) } finally { setMoreBusy(false) } }}>{moreBusy ? <Busy label="加载中"/> : '更早的对话'}</button>}
      {loading ? <div className="chat-skeleton" aria-label="正在加载故事"><div/><div/><div/></div> : turns.length === 0 && <Empty title={selected ? '输入你的行动' : '新建一个故事'}>{selected ? '描述你想做什么，系统会生成下一段剧情。' : <a href="#/app/saves" className="button primary">新建故事 <ArrowRight size={15}/></a>}</Empty>}
      {turns.map((turn, index) => <div className="story-turn" key={turn.id}>
        <div className="user-message"><div className="user-bubble">{turn.user_text}</div></div>
        <div className="assistant-message"><div className="assistant-body"><div className="message-label"><strong>StoryCanvas</strong><small>第 {firstTurn + index + 1} 轮</small></div><StoryText text={turn.assistant_text}/>
          {turn.image_tasks.filter(t => t.status === 'succeeded').map(task => { const src = imageForTask(task); return src ? <SceneImage key={task.id} src={src} alt={`第 ${firstTurn + index + 1} 轮场景`}/> : null })}
          {turn.image_tasks.filter(t => t.status !== 'succeeded').map(task => <div key={task.id} className="inline-task"><TaskBadge status={task.status}/><span>插图</span><TaskAction task={task}/></div>)}
        </div></div>
      </div>)}
      {app.unconfirmedReply?.saveId === selected && <div className="unconfirmed-reply"><ErrorNote text="回复尚未确认保存，请刷新历史后再继续。"/><p className="user-bubble">{app.unconfirmedReply.text}</p><StoryText text={app.unconfirmedReply.content}/></div>}
      {pending?.saveId === selected && <div className="story-turn"><div className="user-message"><div className="user-bubble">{pending.text}</div></div><div className="assistant-message"><div className="assistant-body"><div className="message-label"><strong>StoryCanvas</strong></div>{pending.content ? <StoryText text={pending.content}/> : <div className="waiting-state" role="status"><LoaderCircle size={18} className="spin"/><div><strong>{pendingTask ? pendingTask.status === 'failed' ? '插图生成失败，等待回复…' : pendingTask.status === 'cancelled' ? '插图已取消，等待回复…' : '正在生成插图…' : '正在生成回复…'}</strong><p>本轮完成后显示文字与插图。</p>{pendingTask && <TaskAction task={pendingTask}/>}</div></div>}</div></div></div>}
    </div></div>
    <div className="composer-wrap"><div className={`composer ${demo ? 'disabled' : ''}`}>
      {demo ? <div className="demo-composer"><BookOpen size={18}/><span>示例仅供浏览。</span><a href="#/app/settings" className="text-button">开始使用 <ArrowRight size={15}/></a></div> : <>
        <textarea ref={area} aria-label="输入你的行动或决策" placeholder={selected ? '输入你的行动…' : '先新建或选择故事'} value={draft} maxLength={12000} disabled={!selected || !!pending || loading} onChange={e => updateDraft(e.target.value)} onKeyDown={e => {
          const touch = matchMedia('(pointer: coarse)').matches
          if (e.key === 'Enter' && !e.nativeEvent.isComposing && (!touch && !e.shiftKey || e.ctrlKey || e.metaKey)) { e.preventDefault(); void submit() }
        }}/>
        <div className="composer-controls"><div><button className={`composer-toggle ${forceImage ? 'selected' : ''}`} aria-pressed={forceImage} disabled={!!pending || !selected} onClick={() => setForceImage(!forceImage)}><ImagePlus size={17}/><span>配图</span></button><button className="icon-button" onClick={() => setOptionsOpen(true)} aria-label="更多发送选项"><MoreHorizontal size={20}/></button></div><button className="send-button" aria-label="发送行动" disabled={!draft.trim() || !selected || !!pending || loading} onClick={() => void submit()}>{pending ? <LoaderCircle size={19} className="spin"/> : <ArrowUp size={20}/>}</button></div>
      </>}
    </div>{!demo && <p className="composer-footnote">Enter 发送 · Shift + Enter 换行</p>}</div>
  </div>
  {optionsOpen && <Modal title="发送选项" onClose={() => setOptionsOpen(false)}><div className="send-options"><p className="subtle">自动配图{health?.auto_image ? '已开启' : '已关闭'}，此设置对整个服务生效。</p><button className="button secondary" disabled={loading || !!pending} onClick={() => { setOptionsOpen(false); void app.refreshStory().catch(fail) }}><RefreshCw size={15}/>刷新对话</button><details className="command-help"><summary>指令帮助</summary><div className="command-list">{[
    ['/图 ', '本轮配图'], ['/图开', '开启自动配图'], ['/图关', '关闭自动配图'], ['/存档 ', '创建或切换故事'], ['/存档列表', '查看故事列表'], ['/记忆 ', '添加记忆'], ['/记忆状态', '查看记忆状态'],
  ].map(([cmd, desc]) => <button key={cmd} onClick={() => { if (pending) { notify('请等待当前回复完成。', 'error'); return } updateDraft(cmd); setOptionsOpen(false); area.current?.focus() }}><code>{cmd.trim()}</code><span>{desc}</span><ArrowRight size={14}/></button>)}</div><p className="subtle">支持 /image、/image-on、/image-off 和 #图 等现有指令。</p></details></div></Modal>}
  </div>
}
