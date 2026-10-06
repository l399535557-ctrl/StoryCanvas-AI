import { useState, type FormEvent } from 'react'
import { ArrowRight, Check, ChevronRight, Eye, EyeOff, Unplug } from 'lucide-react'
import { Busy, ErrorNote, PageHead } from '../components/ui'
import { useApp } from '../lib/context'

export function Settings() {
  const { connection, connect, disconnect, connected, demo, health, pending } = useApp()
  const [base, setBase] = useState(connection.base)
  const [token, setToken] = useState(connection.token)
  const [visible, setVisible] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError('')
    try { await connect(base, token) } catch (err) { setError(err instanceof Error ? err.message : '连接失败。') }
    finally { setBusy(false) }
  }
  return <div className="standard-page settings-page"><PageHead title="设置" description="连接 StoryCanvas 服务。"/>
    <section className="settings-card"><h2>服务连接</h2><form onSubmit={submit}>
      <label className="field">服务地址<input aria-label="服务地址" value={base} type="text" inputMode="url" placeholder="留空使用当前网站的服务" onChange={e => setBase(e.target.value)} disabled={busy || !!pending}/></label>
      <label className="field">网关 API 密钥<span className="password-field"><input aria-label="网关 API 密钥" value={token} type={visible ? 'text' : 'password'} autoComplete="off" spellCheck={false} placeholder="填写网关密钥" onChange={e => setToken(e.target.value)} disabled={busy || !!pending}/><button type="button" className="icon-button" aria-label={visible ? '隐藏密钥' : '显示密钥'} onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={17}/> : <Eye size={17}/>}</button></span><small>密钥仅保存在当前浏览器会话，可随时断开连接清除。</small></label>
      {error && <ErrorNote text={error}/>}<div className="form-actions">{connected && <button type="button" className="button secondary" disabled={busy || !!pending} onClick={() => { disconnect(); setToken('') }}><Unplug size={15}/>断开连接</button>}<button className="button primary" disabled={busy || !token.trim() || !!pending}>{busy ? <Busy label="连接中…"/> : <>连接服务 <ArrowRight size={16}/></>}</button></div>
    </form></section>
    {!demo && connected && health && <section className="connection-summary"><h2>连接状态</h2><div className="connection-checks"><span><Check size={15}/>网关已连接</span><span className={health.comfyui_ok ? '' : 'warning'}>{health.comfyui_ok ? <Check size={15}/> : <Unplug size={15}/>}插图服务{health.comfyui_ok ? '可用' : '不可用'}</span></div></section>}
    <details className="settings-advanced"><summary>高级与帮助</summary><div className="advanced-body"><a href={`#/${demo ? 'demo' : 'app'}/status`} className="setting-row"><div><strong>系统管理</strong><span>服务诊断、数据库备份与恢复</span></div><ChevronRight size={18}/></a><details className="connection-help"><summary>如何连接服务</summary><p>先启动后端。开发时通过 .env.local 中的 VITE_DEV_PROXY_TARGET 配置代理，页面服务地址留空。直接填写地址时，需要部署者提供 HTTPS 和跨域配置。</p><p>使用独立的 GATEWAY_API_KEY。模型和 ComfyUI 的配置继续由后端管理。关闭标签页通常会清除密钥，浏览器恢复会话可能保留。</p></details><a href="#/demo/chat" className="text-button">浏览示例 <ArrowRight size={14}/></a></div></details>
  </div>
}
