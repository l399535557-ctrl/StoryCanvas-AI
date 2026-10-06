import { Component, type ReactNode } from 'react'
import { AppProvider } from './lib/store'
import { useApp } from './lib/context'
import { ConnectionRequired, Shell } from './components/Shell'
import { Home } from './features/Home'
import { Chat } from './features/Chat'
import { Saves } from './features/Saves'
import { Memories } from './features/Memories'
import { Gallery, Tasks } from './features/Tasks'
import { Settings } from './features/Settings'
import { Status } from './features/Status'
function Routes() {
  const { route, demo, connected } = useApp()
  if (route.home) return <Home/>
  const views = { chat: <Chat/>, saves: <Saves/>, memories: <Memories/>, tasks: <Tasks/>, gallery: <Gallery/>, settings: <Settings/>, status: <Status/> }
  return <Shell>{!demo && !connected && route.view !== 'settings' ? <ConnectionRequired/> : views[route.view]}</Shell>
}
class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch() { /* No content, credentials or headers are logged. */ }
  render() {
    return this.state.failed ? <div className="fatal-error"><h1>页面遇到问题</h1><p>请重新加载页面。后端存档不会因此被删除。</p><button className="button primary" onClick={() => window.location.reload()}>重新加载</button></div> : this.props.children
  }
}
export function App() { return <ErrorBoundary><AppProvider><a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus() }}>跳到主要内容</a><Routes/></AppProvider></ErrorBoundary> }
