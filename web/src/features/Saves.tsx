import { useRef, useState, type FormEvent } from 'react'
import { Archive, ArrowRight, BookOpen, Copy, Download, FileArchive, MoreHorizontal, Pencil, Plus, RotateCcw, Upload } from 'lucide-react'
import { Busy, Confirm, Empty, ErrorNote, Modal, PageHead, ReadonlyNote } from '../components/ui'
import { useApp } from '../lib/context'
import type { Save } from '../lib/types'
import { download, navigate, timestamp } from '../lib/utils'

export function Saves() {
  const app = useApp()
  const { demo, saves, selected, chooseSave, api, notify, fail, pending } = app
  const [filter, setFilter] = useState('active')
  const [search, setSearch] = useState('')
  const [form, setForm] = useState<{ kind: 'create' | 'rename' | 'copy' | 'import'; save?: Save; bundle?: unknown } | null>(null)
  const [name, setName] = useState('')
  const [id, setId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirm, setConfirm] = useState<Save | null>(null)
  const [menu, setMenu] = useState<string | null>(null)
  const file = useRef<HTMLInputElement>(null)
  const shown = saves.filter(s => (filter === 'archived' ? !!s.archived_at : !s.archived_at) && (s.name + s.id).toLowerCase().includes(search.toLowerCase()))
  const open = (kind: NonNullable<typeof form>['kind'], save?: Save, bundle?: unknown) => {
    setName(kind === 'rename' ? save?.name || '' : kind === 'copy' ? `${save?.name} · 新分支` : '')
    setId(''); setError(''); setForm({ kind, save, bundle }); setMenu(null)
  }
  const submit = async (event: FormEvent) => {
    event.preventDefault(); if (!form) return
    setBusy(true); setError('')
    try {
      if (form.kind === 'create') { const result = await api.createSave(name.trim(), id.trim() || undefined); await app.refreshSaves(); chooseSave(result.data.id) }
      if (form.kind === 'rename') { await api.renameSave(form.save!.id, name.trim()); await app.refreshSaves() }
      if (form.kind === 'copy') { const result = await api.copySave(form.save!.id, id.trim(), name.trim()); await app.refreshSaves(); chooseSave(result.data.save_id) }
      if (form.kind === 'import') { const result = await api.importSave(form.bundle, id.trim() || undefined, name.trim() || undefined); await app.refreshSaves(); chooseSave(result.data.save_id) }
      notify({ create: '故事已创建。', rename: '故事名称已更新。', copy: '故事分支已创建。', import: '存档已导入，原存档不会被覆盖。' }[form.kind]); setForm(null)
    } catch (e) { setError(e instanceof Error ? e.message : '操作失败。') }
    finally { setBusy(false) }
  }
  const exportFile = async (save: Save, publication = false) => {
    setMenu(null); setBusy(true)
    try {
      if (publication) download(await api.publication(save.id), `${save.id}-story.zip`)
      else download(new Blob([JSON.stringify(await api.exportSave(save.id), null, 2)], { type: 'application/json' }), `${save.id}.json`)
      notify(publication ? '作品 ZIP 已准备下载。' : '存档 JSON 已准备下载。')
    } catch (e) { fail(e) } finally { setBusy(false) }
  }
  return <div className="standard-page"><PageHead title="故事" description="选择一个故事继续对话。" actions={!demo && <><button className="button secondary" disabled={demo || busy || !!pending} onClick={() => file.current?.click()}><Upload size={16}/>导入存档</button><button className="button primary" disabled={demo || !!pending} onClick={() => open('create')}><Plus size={17}/>新建故事</button></>}/>
    {demo && <ReadonlyNote/>}{app.resourceError && <ErrorNote text={app.resourceError} retry={() => app.refreshSaves().catch(fail)}/>}
    <div className="list-toolbar"><div className="tabs"><button className={filter === 'active' ? 'active' : ''} onClick={() => setFilter('active')}>我的故事 <span>{saves.filter(s => !s.archived_at).length}</span></button><button className={filter === 'archived' ? 'active' : ''} onClick={() => setFilter('archived')}>已归档 <span>{saves.filter(s => !!s.archived_at).length}</span></button></div><input className="search-input" aria-label="搜索故事" placeholder="搜索故事名称…" value={search} onChange={e => setSearch(e.target.value)}/></div>
    <div className="save-grid">{shown.map(save => <article className={`save-card ${save.id === selected ? 'current' : ''}`} key={save.id}><div className="save-card-top"><span className="save-icon"><BookOpen size={23} strokeWidth={1.4}/></span>{save.id === selected ? <span className="current-label">当前故事</span> : null}{!demo && <button className="icon-button" aria-label={`${save.name} 更多操作`} onClick={() => setMenu(menu === save.id ? null : save.id)}><MoreHorizontal size={20}/></button>}</div><h2>{save.name}</h2><p className="save-id">{save.id}</p><div className="save-counts"><span>{save.turn_count} 轮对话</span><span>{save.memory_count} 条记忆</span></div><div className="save-card-foot"><span>{timestamp(save.updated_at)}</span>{save.archived_at ? <button className="text-button" disabled={demo || busy || !!pending} onClick={async () => { setBusy(true); try { await api.saveAction(save.id, 'restore'); await app.refreshSaves(); notify('故事已恢复。') } catch (e) { fail(e) } finally { setBusy(false) } }}><RotateCcw size={14}/>恢复</button> : <button className="text-button" disabled={!!pending} onClick={() => { chooseSave(save.id); navigate(demo ? 'demo' : 'app', 'chat') }}>继续故事 <ArrowRight size={15}/></button>}</div>
      {menu === save.id && <div className="card-menu"><button disabled={demo || !!save.archived_at || !!pending} onClick={() => open('rename', save)}><Pencil size={14}/>重命名</button><button disabled={demo || !!save.archived_at || !!pending} onClick={() => open('copy', save)}><Copy size={14}/>复制为新分支</button><button disabled={demo || busy} onClick={() => void exportFile(save)}><Download size={14}/>导出存档 JSON</button><button disabled={demo || busy} onClick={() => void exportFile(save, true)}><FileArchive size={14}/>导出图文作品 ZIP</button><button disabled={demo || !!save.archived_at || save.id === selected || save.id === 'default' || !!pending} title={save.id === selected ? '请先切换到其他故事' : '归档后可以恢复'} onClick={() => { setConfirm(save); setMenu(null) }}><Archive size={14}/>归档故事</button><button className="menu-dismiss" onClick={() => setMenu(null)}>收起菜单</button></div>}
    </article>)}</div>
    {!shown.length && <Empty title={filter === 'archived' ? '没有归档的故事' : '这里还没有故事'}>{search ? '试试其他搜索词。' : '新建一个故事，开始你的第一次选择。'}</Empty>}
    <input type="file" ref={file} accept=".json,application/json" hidden onChange={async e => {
      const selectedFile = e.target.files?.[0]; e.target.value = ''; if (!selectedFile) return
      if (selectedFile.size > 20 * 1024 * 1024) { notify('存档文件超过 20 MB，请检查文件。', 'error'); return }
      try { const bundle = JSON.parse(await selectedFile.text()); if (bundle.format !== 'storycanvas-save' || !Array.isArray(bundle.turns) || !Array.isArray(bundle.memories)) throw new Error('请选择 StoryCanvas 导出的存档 JSON 文件。'); open('import', undefined, bundle) } catch (err) { fail(err) }
    }}/>
    {form && <Modal title={{ create: '新建故事', rename: '重命名故事', copy: '复制故事', import: '导入故事存档' }[form.kind]} onClose={() => setForm(null)} busy={busy}><form onSubmit={submit}><label className="field">故事名称<input autoFocus value={name} maxLength={120} required={form.kind !== 'import'} placeholder={form.kind === 'import' ? '留空保留原名称' : '输入故事名称'} onChange={e => setName(e.target.value)}/></label>{form.kind !== 'rename' && <label className="field">存档 ID {form.kind === 'copy' ? '（必填）' : '（可选）'}<input value={id} maxLength={120} placeholder={form.kind === 'import' ? '原 ID 已存在时，请填写新 ID' : '如 moon-observatory'} onChange={e => setId(e.target.value)} required={form.kind === 'copy'}/><small>稳定的存档标识。重命名不会改变 ID。</small></label>}{form.kind === 'copy' && <p className="subtle">复制当前历史与有效记忆，原故事保留。</p>}{form.kind === 'import' && <p className="subtle">导入创建新的存档，后端不会覆盖已存在的 ID。</p>}{error && <ErrorNote text={error}/>}<div className="form-actions"><button type="button" className="button secondary" disabled={busy} onClick={() => setForm(null)}>取消</button><button className="button primary" disabled={busy || (form.kind !== 'import' && !name.trim()) || (form.kind === 'copy' && !id.trim())}>{busy ? <Busy label="处理中"/> : '确认'}</button></div></form></Modal>}
    {confirm && <Confirm title="归档这个故事？" message={`“${confirm.name}”将移到已归档列表，历史和记忆会保留，可以随时恢复。若它仍是后端活动存档，会先切换到当前选中的其他故事，再进行归档。`} label="确认归档" onClose={() => setConfirm(null)} onConfirm={async () => {
      const state = await api.saves()
      if (state.active_save_id === confirm.id) {
        if (!selected || selected === confirm.id) throw new Error('请先选择另一个有效故事。')
        await api.chat({ model: 'storycanvas', stream: false, story_save_id: selected, messages: [{ role: 'user', content: `/存档 ${selected}` }] }, `web-${crypto.randomUUID()}`)
      }
      await api.saveAction(confirm.id, 'archive'); await app.refreshSaves(); notify('故事已归档，可以从已归档列表恢复。') }}/>}</div>
}
