import { useState, type FormEvent } from 'react'
import { Archive, Brain, Check, ChevronRight, GitBranch, Pencil, Plus, RefreshCw, RotateCcw, ShieldAlert } from 'lucide-react'
import { Badge, Busy, Confirm, Empty, ErrorNote, Modal, PageHead, ReadonlyNote } from '../components/ui'
import { useApp } from '../lib/context'
import type { Memory, MemoryInput } from '../lib/types'
import { timestamp } from '../lib/utils'
const types: Record<string, string> = { world: '世界设定', item: '物品', event: '事件', character: '人物', fact: '事实', note: '记事', relationship: '关系' }
const initial: MemoryInput = { type: 'note', content: '', tags: [], entities: [], importance: 3, story_time: null }

export function Memories() {
  const app = useApp()
  const { demo, memories, api, selected, fail, notify, loading, pending } = app
  const [filter, setFilter] = useState('active')
  const [search, setSearch] = useState('')
  const [editor, setEditor] = useState<{ kind: 'add' | 'edit' | 'supersede'; memory?: Memory } | null>(null)
  const [input, setInput] = useState<MemoryInput>(initial)
  const [tags, setTags] = useState('')
  const [entities, setEntities] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirmation, setConfirmation] = useState<{ memory: Memory; action: 'archive' | 'restore' | 'conflict' | 'activate' } | null>(null)
  const filtered = memories.filter(m => (filter === 'archived' ? !!m.archived_at : !m.archived_at && (filter === 'all' || m.status === filter)) && [m.content, ...m.tags, ...m.entities].join(' ').toLowerCase().includes(search.toLowerCase()))
  const open = (kind: NonNullable<typeof editor>['kind'], memory?: Memory) => {
    setEditor({ kind, memory }); setInput(memory ? { type: memory.memory_type, content: memory.content, tags: memory.tags, entities: memory.entities, importance: memory.importance, story_time: memory.story_time } : initial)
    setTags(memory?.tags.join('，') || ''); setEntities(memory?.entities.join('，') || ''); setError('')
  }
  const submit = async (e: FormEvent) => {
    e.preventDefault(); if (!editor) return
    const parse = (text: string) => [...new Set(text.split(/[,，]/).map(v => v.trim()).filter(Boolean))]
    const value = { ...input, content: input.content.trim(), tags: parse(tags), entities: parse(entities), story_time: input.story_time?.trim() || null }
    if (value.tags.length > 12 || value.entities.length > 10) { setError('最多填写 12 个标签、10 个实体。'); return }
    setBusy(true); setError('')
    try {
      if (editor.kind === 'add') await api.addMemory(selected, value)
      if (editor.kind === 'edit') await api.editMemory(selected, editor.memory!.id, value)
      if (editor.kind === 'supersede') await api.supersedeMemory(selected, editor.memory!.id, value)
      await app.refreshStory(); await app.refreshSaves(); setEditor(null); notify(editor.kind === 'supersede' ? '修订已保存，旧记忆保留修订链并退出检索。' : '记忆已保存。')
    } catch (err) { setError(err instanceof Error ? err.message : '保存失败。') }
    finally { setBusy(false) }
  }
  return <div className="standard-page"><PageHead title="记忆" description="当前故事中保存的人物、物品与经历。" actions={!demo && <><button className="button secondary" disabled={demo || busy || !!pending} onClick={async () => { setBusy(true); try { await app.refreshStory(); notify('记忆列表已刷新。') } catch (e) { fail(e) } finally { setBusy(false) } }}><RefreshCw size={15}/>刷新</button><button className="button primary" disabled={demo || !selected || !!pending} onClick={() => open('add')}><Plus size={17}/>新增记忆</button></>}/>
    {demo && <ReadonlyNote/>}{app.resourceError && <ErrorNote text={app.resourceError} retry={() => app.refreshStory().catch(fail)}/>}
    <div className="list-toolbar"><div className="tabs">{[['active', '有效'], ['conflicted', '待核实'], ['superseded', '已修订'], ['archived', '已归档']].map(([value, label]) => <button key={value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{label}</button>)}</div><input className="search-input" aria-label="搜索记忆" placeholder="搜索内容、标签或实体…" value={search} onChange={e => setSearch(e.target.value)}/></div>
    <div className="memory-list">{filtered.map(memory => <article key={memory.id} className="memory-card"><div className="memory-card-top"><span className="memory-type-label"><Brain size={13}/>{types[memory.memory_type] || memory.memory_type}</span><div><span className="importance" aria-label={`重要度 ${memory.importance} / 5`}>重要度 {memory.importance}</span><Badge tone={memory.archived_at ? '' : memory.status === 'active' ? 'success' : memory.status === 'conflicted' ? 'error' : 'gold'}>{memory.archived_at ? '已归档' : memory.status === 'active' ? '有效' : memory.status === 'conflicted' ? '待核实' : '已修订'}</Badge></div></div><p className="memory-content">{memory.content}</p><div className="mini-tags">{memory.tags.map(tag => <span key={tag}>{tag}</span>)}</div>{memory.entities.length > 0 && <p className="memory-entities">相关实体：{memory.entities.join('、')}</p>}
      <div className="memory-meta"><span>{memory.story_time || '未标注故事时间'}</span>{memory.source_turn_id && <span>来源轮次 #{memory.source_turn_id}</span>}{memory.supersedes_memory_id && <span>修订自记忆 #{memory.supersedes_memory_id}</span>}<span>{timestamp(memory.updated_at)}</span></div>
      {!demo && <div className="memory-actions">{memory.archived_at ? <button className="text-button" disabled={demo || !!pending} onClick={() => setConfirmation({ memory, action: 'restore' })}><RotateCcw size={14}/>恢复记忆</button> : <>
        <button className="text-button" disabled={demo || !!pending} onClick={() => open('edit', memory)}><Pencil size={14}/>编辑</button><details className="memory-more"><summary>更多操作</summary><div><button className="text-button" disabled={demo || !!pending || memory.status === 'superseded'} onClick={() => open('supersede', memory)}><GitBranch size={14}/>修订事实</button>
        <button className="text-button" disabled={demo || !!pending} onClick={() => setConfirmation({ memory, action: memory.status === 'active' ? 'conflict' : 'activate' })}>{memory.status === 'active' ? <ShieldAlert size={14}/> : <Check size={14}/>} {memory.status === 'active' ? '标记待核实' : '重新激活'}</button>
        <button className="text-button" disabled={demo || !!pending} onClick={() => setConfirmation({ memory, action: 'archive' })}><Archive size={14}/>归档</button></div></details></>}</div>}
    </article>)}</div>
    {loading && <Busy label="正在读取记忆"/>}{!loading && !filtered.length && <Empty title="这里还没有相关记忆">{search ? '试试其他搜索词。' : '更换筛选条件，或新增一条需要长期保留的事实。'}</Empty>}
    {!demo && app.canLoadMemories && <button className="button secondary load-more" disabled={busy} onClick={async () => { setBusy(true); try { await app.loadMoreMemories() } catch (e) { fail(e) } finally { setBusy(false) } }}>加载更多记忆 <ChevronRight size={15}/></button>}
    {editor && <Modal title={{ add: '新增长期记忆', edit: '编辑记忆', supersede: '修订事实并保留旧版本' }[editor.kind]} onClose={() => setEditor(null)} busy={busy}><form onSubmit={submit}>
      {editor.kind === 'supersede' && <p className="subtle">新事实会替代旧事实参与检索，旧记录保留供追溯。</p>}
      <div className="form-grid"><label className="field">类型<select value={input.type} onChange={e => setInput({ ...input, type: e.target.value })}>{Object.entries({ ...types, ...(types[input.type] ? {} : { [input.type]: input.type }) }).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="field">重要度<select value={input.importance} onChange={e => setInput({ ...input, importance: Number(e.target.value) })}>{[1, 2, 3, 4, 5].map(v => <option key={v} value={v}>{v} / 5</option>)}</select></label></div>
      <label className="field">记忆内容<textarea autoFocus rows={4} required maxLength={1000} value={input.content} onChange={e => setInput({ ...input, content: e.target.value })}/><small>{input.content.length} / 1000 字</small></label>
      <label className="field">标签<input value={tags} maxLength={1000} placeholder="用逗号分隔，如 观测站，星图" onChange={e => setTags(e.target.value)}/></label><label className="field">相关实体<input value={entities} maxLength={1000} placeholder="用逗号分隔，如 月纹钥匙，控制台" onChange={e => setEntities(e.target.value)}/></label><label className="field">故事时间（可选）<input value={input.story_time || ''} maxLength={120} placeholder="如 第一章、午夜之前" onChange={e => setInput({ ...input, story_time: e.target.value })}/></label>
      {error && <ErrorNote text={error}/>}<div className="form-actions"><button className="button secondary" type="button" disabled={busy} onClick={() => setEditor(null)}>取消</button><button className="button primary" disabled={busy || !input.content.trim()}>{busy ? <Busy label="保存中"/> : '保存记忆'}</button></div></form></Modal>}
    {confirmation && <Confirm title={{ archive: '归档这条记忆？', restore: '恢复这条记忆？', conflict: '将这条记忆标记为待核实？', activate: '让这条记忆重新参与检索？' }[confirmation.action]} message={{ archive: '归档后不再参与检索，可以从已归档列表恢复。', restore: '恢复后会保留原有的有效、冲突或修订状态。', conflict: '记录将保留供你核实，同时立即退出有效检索集合。', activate: '请确认内容准确。重新激活会让这条事实参与后续故事检索。' }[confirmation.action]} onClose={() => setConfirmation(null)} onConfirm={async () => { await api.memoryAction(selected, confirmation.memory.id, confirmation.action); await app.refreshStory(); await app.refreshSaves(); notify('记忆状态已更新。') }}/>}</div>
}
