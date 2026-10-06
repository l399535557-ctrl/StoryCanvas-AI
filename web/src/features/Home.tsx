import { ArrowRight, Github } from 'lucide-react'
import { Brand } from '../components/ui'
import { asset } from '../lib/utils'

export function Home() {
  return <div className="home">
    <header className="home-header"><Brand/><nav aria-label="首页导航"><a href="#/demo/chat">浏览示例</a><a className="button small secondary" href="#/app/settings">开始使用</a></nav></header>
    <main id="main-content" tabIndex={-1}>
      <section className="hero">
        <div className="hero-copy"><h1>输入行动，<br/>生成故事与插图。</h1><p>与 AI 进行连续对话。<br/>故事独立保存，重要经历随对话保留。</p>
          <div className="hero-actions"><a className="button primary" href="#/app/settings">开始使用 <ArrowRight size={17}/></a><a className="text-button" href="#/demo/chat">浏览示例 <ArrowRight size={15}/></a></div>
        </div>
        <a href="#/demo/chat" className="hero-art" aria-label="浏览星海观测站示例故事"><img src={asset('observatory.webp')} alt="云海之上，旅人仰望星空中的巨大观测装置" fetchPriority="high"/><div className="art-caption"><span>示例故事</span><h2>星海观测站</h2><ArrowRight size={20}/></div></a>
      </section>
      <details className="home-about"><summary>关于 StoryCanvas</summary><p>一个将文本生成、长期记忆与场景配图结合的互动故事系统。输入行动后，系统生成下一段剧情；选择配图时，文字与插图完成后一起返回。</p></details>
    </main>
    <footer className="home-footer"><span>StoryCanvas AI</span><a href="https://github.com/l399535557-ctrl/StoryCanvas-AI" target="_blank" rel="noopener noreferrer"><Github size={15}/>项目源码</a></footer>
  </div>
}
