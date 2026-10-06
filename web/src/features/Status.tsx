import { useEffect, useState } from 'react'
import { Activity, CheckCircle2, Database, Download, HardDrive, RefreshCw, RotateCcw, ShieldCheck } from 'lucide-react'
import { Badge, Confirm, Empty, PageHead, ReadonlyNote } from '../components/ui'
import { useApp } from '../lib/context'
import type { Backup } from '../lib/types'
import { sizeLabel, timestamp } from '../lib/utils'

export function Status() {
  const app = useApp()
  const { demo, health, diagnostics, backups, api, fail, notify, pending, refreshSystem } = app
  const [busy, setBusy] = useState(false)
  const [label, setLabel] = useState('')
  const [restore, setRestore] = useState<Backup | null>(null)
  const [confirmText, setConfirmText] = useState('')
  useEffect(() => { if (!demo) void refreshSystem() }, [demo, refreshSystem])
  const database = diagnostics?.database
  const refresh = async () => { setBusy(true); try { await refreshSystem() } finally { setBusy(false) } }
  const cards = demo ? [
    { icon: BookIcon, label: '示例故事', value: '1', caption: '公开展示存档' }, { icon: Database, label: '示例记忆', value: '3', caption: '世界 · 物品 · 事件' },
    { icon: Activity, label: '示例对话', value: '3', caption: '预先准备的故事轮次' }, { icon: HardDrive, label: '示例插图', value: '1', caption: '来自公开仓库' },
  ] : [
    { icon: ShieldCheck, label: '数据库完整性', value: database?.integrity || '待检查', caption: database ? `Schema ${database.schema_version} · ${database.journal_mode}` : '等待诊断结果' },
    { icon: Database, label: '长期记忆', value: String(database?.counts.memory_count ?? '—'), caption: database?.fts_enabled ? 'FTS5 检索可用' : 'FTS5 未启用或待检查' },
    { icon: Activity, label: '故事轮次', value: String(database?.counts.turn_count ?? '—'), caption: `${database?.counts.save_count ?? '—'} 个有效存档` },
    { icon: HardDrive, label: '数据库大小', value: database ? sizeLabel(database.database_size_bytes) : '—', caption: `后端版本 ${diagnostics?.version || '待检查'}` },
  ]
  return <div className="standard-page"><PageHead title="系统管理" description={demo ? '以下为公开示例统计，不代表任何正在运行的服务。' : '检查服务、数据库与任务状态，并管理后端整库备份。'} actions={<button className="button secondary" disabled={demo || busy} onClick={() => void refresh()}><RefreshCw size={15}/>{busy ? '检查中…' : '重新检查'}</button>}/>{demo && <ReadonlyNote/>}
    <div className="stats-grid">{cards.map(({ icon: Icon, label: title, value, caption }) => <article className="stat-card" key={title}><div><Icon size={18}/><span>{title}</span></div><strong>{value}</strong><p>{caption}</p></article>)}</div>
    <div className="status-grid"><section className="status-card"><h2><Activity size={19}/>服务状态</h2><div className="status-row"><span>StoryCanvas 网关</span><Badge tone={!demo && health ? 'success' : ''}>{demo ? '示例模式' : health ? '可访问' : '待检查'}</Badge></div><div className="status-row"><span>ComfyUI 插图服务</span><Badge tone={!demo && health?.comfyui_ok ? 'success' : ''}>{demo ? '未连接' : health?.comfyui_ok ? '可用' : '离线或待检查'}</Badge></div><div className="status-row"><span>图像后端</span><span>{demo ? 'comfy-sdxl（示例）' : health?.image_backend || '—'}</span></div><div className="status-row"><span>运行设备</span><span>{demo ? '未连接' : health?.device || '未检测到'}</span></div><div className="status-row"><span>自动插图</span><span>{demo ? '未连接' : health ? health.auto_image ? '开启（网关共享）' : '关闭' : '—'}</span></div><div className="status-row"><span>长期记忆 / 自动提取</span><span>{demo ? '示例数据' : health ? `${health.memory.enabled ? '开启' : '关闭'} / ${health.memory.extract_enabled ? '开启' : '关闭'}` : '—'}</span></div></section>
      <section className="status-card"><h2><CheckCircle2 size={19}/>插图任务统计</h2>{(['queued', 'running', 'succeeded', 'failed', 'cancelled'] as const).map((status, i) => <div className="status-row" key={status}><span>{['排队中', '生成中', '已完成', '失败', '已取消'][i]}</span><strong>{demo ? status === 'succeeded' ? '1（示例）' : '0（示例）' : database?.task_status_counts[status] ?? '—'}</strong></div>)}<p className="subtle">{demo ? '公开示例不调用诊断接口。' : '统计覆盖后端全部存档，不包含内部图像提示词。'}</p></section></div>
    <section className="backup-section"><div className="section-row"><div><h2>数据库备份与恢复</h2><p>备份保存在后端设备。恢复前，后端自动创建安全快照。</p></div><div className="backup-create"><input aria-label="备份标签" value={label} maxLength={80} disabled={demo || busy || !!pending} placeholder="备份标签（可选）" onChange={e => setLabel(e.target.value)}/><button className="button secondary" disabled={demo || busy || !!pending} onClick={async () => { setBusy(true); try { const result = await api.createBackup(label); notify(`备份已创建：${result.data.filename}`); setLabel(''); await refreshSystem() } catch (e) { fail(e) } finally { setBusy(false) } }}><Download size={15}/>{busy ? '处理中…' : '创建备份'}</button></div></div>
      {demo ? <Empty title="备份功能在连接网关后启用">公开示例不会创建或恢复真实数据库。</Empty> : backups.length ? <div className="backup-list">{backups.map(backup => <div key={backup.filename} className="backup-row"><Database size={18}/><div><strong>{backup.filename}</strong><small>{timestamp(backup.created_at)} · {sizeLabel(backup.size_bytes)}</small></div><button className="text-button" disabled={busy || !!pending} onClick={() => { setRestore(backup); setConfirmText('') }}><RotateCcw size={14}/>恢复</button></div>)}</div> : <Empty title="尚无数据库备份">可在升级或演示前创建一次快照。</Empty>}
    </section>
    {restore && <Confirm title="恢复整库备份" message={`将恢复 ${restore.filename}。所有存档、历史、记忆和任务将回到备份时的状态，影响整个后端。后端会自动保留恢复前安全快照。`} label="我已了解，继续恢复" danger onClose={() => setRestore(null)} onConfirm={async () => {
      // Require the exact filename to confirm a whole-database operation.
      if (confirmText !== restore.filename) throw new Error('请在备份列表下方输入完整备份文件名，再确认恢复。')
      const result = await api.restoreBackup(restore.filename); await app.refreshSaves(); await app.refreshStory(); await refreshSystem(); notify(`数据库已恢复，恢复前快照：${result.data.safety_backup}`)
    }}><label className="field">输入完整备份文件名确认整库恢复<input value={confirmText} autoComplete="off" placeholder={restore.filename} onChange={e => setConfirmText(e.target.value)}/></label></Confirm>}
  </div>
}
const BookIcon = Database
