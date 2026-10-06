import { useState } from 'react'
import { Ban, RefreshCw } from 'lucide-react'
import { useApp } from '../lib/context'
import type { ImageTask } from '../lib/types'
import { Confirm } from './ui'

export function TaskAction({ task }: { task: ImageTask }) {
  const app = useApp()
  const [confirm, setConfirm] = useState(false)
  const action = ['queued', 'running'].includes(task.status) ? 'cancel' : ['failed', 'cancelled'].includes(task.status) ? 'retry' : null
  if (app.demo || !action) return null
  return <><button className="text-button task-action" onClick={() => setConfirm(true)}>{action === 'cancel' ? <Ban size={14}/> : <RefreshCw size={14}/>} {action === 'cancel' ? '取消任务' : '重试插图'}</button>
    {confirm && <Confirm title={action === 'cancel' ? '取消插图任务？' : '重试插图？'} message={action === 'cancel' ? '取消插图可能使本轮回复失败，输入会保留。' : '使用原始场景描述重新生成插图，故事正文保持不变。'} label={action === 'cancel' ? '取消插图任务' : '重试插图'} onClose={() => setConfirm(false)} onConfirm={async () => { await app.api.taskAction(task.id, action); await app.refreshStory(); app.notify(action === 'cancel' ? '取消请求已提交。' : '重试任务已创建。') }}/>}</>
}
