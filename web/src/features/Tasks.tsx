import { useState } from 'react'
import { Ban, ChevronRight, Clock, RefreshCw, Sparkles } from 'lucide-react'
import { Busy, Confirm, Empty, ErrorNote, PageHead, ReadonlyNote, SceneImage, TaskBadge } from '../components/ui'
import { useApp } from '../lib/context'
import type { ImageTask } from '../lib/types'
import { asset, imageURL, timestamp } from '../lib/utils'

export function Tasks() {
  const app = useApp()
  const { demo, tasks, api, fail, notify } = app
  const [filter, setFilter] = useState('all')
  const [confirmation, setConfirmation] = useState<{ task: ImageTask; action: 'cancel' | 'retry' } | null>(null)
  const [busy, setBusy] = useState(false)
  const shown = tasks.filter(t => filter === 'all' || (filter === 'active' ? ['queued', 'running'].includes(t.status) : t.status === filter))
  return <div className="standard-page"><PageHead eyebrow="GENERATION QUEUE" title="让想象，慢慢显影。" description="查看当前故事的插图任务。排队和生成状态来自后端，不代表采样进度。" actions={<button className="button secondary" disabled={demo || busy} onClick={async () => { setBusy(true); try { await app.refreshStory(); notify('任务列表已刷新。') } catch (e) { fail(e) } finally { setBusy(false) } }}><RefreshCw size={15}/>刷新任务</button>}/>{demo && <ReadonlyNote/>}
    {app.resourceError && <ErrorNote text={app.resourceError}/>}
    <div className="list-toolbar"><div className="tabs">{[['all', '全部'], ['active', '处理中'], ['succeeded', '已完成'], ['failed', '失败'], ['cancelled', '已取消']].map(([value, label]) => <button className={filter === value ? 'active' : ''} key={value} onClick={() => setFilter(value)}>{label}</button>)}</div></div>
    <div className="task-list">{shown.map(task => <article className="task-card" key={task.id}><div className="task-symbol"><Sparkles size={21}/></div><div className="task-content"><div className="task-title"><h2>{task.turn_id ? `故事轮次 #${task.turn_id} · 场景插图` : '场景插图任务'}</h2><TaskBadge status={task.status}/></div><p>{task.backend} <span>·</span> {timestamp(task.created_at)} {task.duration_seconds !== null && <span>· {task.duration_seconds.toFixed(1)} 秒</span>}</p><div className="task-identifiers"><span>任务：{task.id}</span><span>请求：{task.request_id}</span>{task.retry_of_task_id && <span>重试自：{task.retry_of_task_id}</span>}</div>{task.error && <div className="task-error">{task.error}</div>}{['queued', 'running'].includes(task.status) && <p className="task-wait"><Clock size={13}/>状态每 3 秒检查一次，插图任务由后端串行处理。</p>}</div>
      <div className="task-actions">{['queued', 'running'].includes(task.status) && <button className="button secondary small" disabled={demo} onClick={() => setConfirmation({ task, action: 'cancel' })}><Ban size={14}/>取消任务</button>}{['failed', 'cancelled'].includes(task.status) && <button className="button secondary small" disabled={demo} onClick={() => setConfirmation({ task, action: 'retry' })}><RefreshCw size={14}/>重试插图</button>}</div>
    </article>)}</div>{!shown.length && <Empty title="没有相关插图任务">开启本轮配图或自动插图后，任务将显示在这里。</Empty>}
    {!demo && app.canLoadTasks && <button className="button secondary load-more" disabled={busy} onClick={async () => { setBusy(true); try { await app.loadMoreTasks() } catch (e) { fail(e) } finally { setBusy(false) } }}>{busy ? <Busy/> : <>加载更多任务 <ChevronRight size={15}/></>}</button>}
    {confirmation && <Confirm title={confirmation.action === 'cancel' ? '取消这个插图任务？' : '重新生成这张插图？'} message={confirmation.action === 'cancel' ? '后端会记录取消状态，并尝试中断正在运行的插图。这可能使当前整轮对话返回失败，输入会保留。' : '使用后端保留的原始视觉描述创建新的插图任务，不会重新调用故事续写。若原任务没有可用提示词，后端会拒绝重试。'} label={confirmation.action === 'cancel' ? '取消插图任务' : '重试插图'} onClose={() => setConfirmation(null)} onConfirm={async () => { await api.taskAction(confirmation.task.id, confirmation.action); await app.refreshStory(); notify(confirmation.action === 'cancel' ? '取消请求已提交。' : '新的重试任务已创建。') }}/>}</div>
}

export function Gallery() {
  const app = useApp()
  const { demo, turns, api, fail } = app
  const [busy, setBusy] = useState(false)
  const pictures = turns.flatMap((turn, index) => turn.image_tasks.filter(task => task.status === 'succeeded' && (demo || task.image_filename)).map(task => ({ task, turn, index })))
  return <div className="standard-page"><PageHead eyebrow="SCENES FROM YOUR JOURNEY" title="那些被看见的瞬间。" description="每张插图都关联对应的故事轮次，重试生成的图片也保留在该轮次。"/>{demo && <ReadonlyNote/>}{app.resourceError && <ErrorNote text={app.resourceError}/>}
    <div className="gallery-grid">{pictures.map(({ task, turn, index }) => <article className="gallery-card" key={task.id}><SceneImage src={demo ? asset('observatory.webp') : imageURL(`/images/${task.image_filename}`, api.base)!} alt={`故事轮次 #${turn.id} 的插图`}/><div className="gallery-copy"><span className="eyebrow">SCENE {String(index + 1).padStart(2, '0')}</span><h2>{turn.user_text}</h2><p>{demo ? '公开示例插图' : `${task.backend}${task.duration_seconds !== null ? ` · ${task.duration_seconds.toFixed(1)} 秒` : ''}`}</p></div></article>)}</div>
    {!pictures.length && <Empty title="还没有可展示的插图">当前已加载历史中没有完成的插图。你可以开启配图，或加载更早的历史。</Empty>}
    {!demo && app.canLoadTurns && <button className="button secondary load-more" disabled={busy} onClick={async () => { setBusy(true); try { await app.loadMoreTurns() } catch (e) { fail(e) } finally { setBusy(false) } }}>{busy ? <Busy/> : '加载更早历史中的插图'}</button>}
  </div>
}
