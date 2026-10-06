import { useState, type FormEvent } from 'react'
import { ArrowRight, Check, Eye, EyeOff, KeyRound, Link, LockKeyhole, Plug, Unplug } from 'lucide-react'
import { Badge, Busy, ErrorNote, PageHead } from '../components/ui'
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
  return <div className="standard-page settings-page"><PageHead eyebrow="CONNECT YOUR WORLD" title="把故事，连接到你的世界。" description="连接 StoryCanvas 网关，使用你的模型与 ComfyUI。上游模型密钥继续保留在后端。"/>
    <div className="settings-layout"><section className="settings-card"><div className="settings-card-heading"><span className="settings-symbol"><Plug size={23}/></span><div><h2>网关连接</h2><p>验证地址、网关密钥与可用模型。</p></div>{!demo && connected && <Badge tone="success">已配置</Badge>}</div>
      <form onSubmit={submit}><label className="field">服务地址<span className="input-icon"><Link size={16}/><input aria-label="服务地址" value={base} type="text" inputMode="url" placeholder="留空使用当前网站的网关代理" onChange={e => setBase(e.target.value)} disabled={busy || !!pending}/></span><small>开发时建议留空，通过 Vite 代理访问 Windows。直接填写跨域地址时，Windows 需配置 HTTPS 与跨域访问。</small></label>
        <label className="field">网关 API 密钥<span className="input-icon"><KeyRound size={16}/><input aria-label="网关 API 密钥" value={token} type={visible ? 'text' : 'password'} autoComplete="off" spellCheck={false} placeholder="填写 GATEWAY_API_KEY" onChange={e => setToken(e.target.value)} disabled={busy || !!pending}/><button type="button" className="icon-button" aria-label={visible ? '隐藏密钥' : '显示密钥'} onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={17}/> : <Eye size={17}/>}</button></span><small>仅保存在当前标签页会话（sessionStorage），不会写入源码或长期本地存储。关闭标签页后通常清除，浏览器恢复会话可能保留；可主动断开连接。</small></label>
        <div className="settings-policy"><LockKeyhole size={16}/><span>使用独立网关密钥，无需填写 DeepSeek 等上游模型密钥。</span></div>{error && <ErrorNote text={error}/>}
        <div className="form-actions">{connected && <button type="button" className="button secondary" disabled={busy || !!pending} onClick={() => { disconnect(); setToken('') }}><Unplug size={16}/>断开连接</button>}<button className="button primary" disabled={busy || !token.trim() || !!pending}>{busy ? <Busy label="验证连接…"/> : <><Plug size={16}/>验证并进入工作台 <ArrowRight size={16}/></>}</button></div>
      </form>
    </section><aside className="settings-aside"><span className="eyebrow">BEFORE YOU BEGIN</span><h3>让网关准备好</h3><ol><li><span>01</span><div><strong>启动 Windows 后端</strong><p>确保网关在运行，Mac 能通过可信网络或 Tailscale 访问。</p></div></li><li><span>02</span><div><strong>确认网关访问方式</strong><p>由部署者配置同源代理，或提供允许浏览器访问的网关地址。手机与电脑使用同一套页面。</p></div></li><li><span>03</span><div><strong>输入网关密钥</strong><p>使用 GATEWAY_API_KEY，验证成功后即可选择存档。</p></div></li></ol><a href="#/demo/chat" className="text-button">暂时没有后端？浏览公开示例 <ArrowRight size={14}/></a></aside></div>
    {!demo && connected && health && <section className="connection-summary"><h2>最近一次连接检查</h2><div className="connection-checks"><span><Check size={15}/>网关鉴权已验证</span><span className={health.comfyui_ok ? '' : 'warning'}>{health.comfyui_ok ? <Check size={15}/> : <Unplug size={15}/>}ComfyUI {health.comfyui_ok ? '可用' : '不可用'}</span><span><KeyRound size={15}/>后端 LLM 密钥{health.configuration.llm_api_key ? '已配置' : '未配置'}（未发起真实生成测试）</span></div></section>}
  </div>
}
