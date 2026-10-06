import { ArrowRight, Github } from 'lucide-react'
import { Brand } from '../components/ui'
import { asset } from '../lib/utils'

export function Home() {
  return <div className="home">
    <header className="home-header"><Brand/><nav aria-label="首页导航"><a href="#/demo/chat">浏览示例</a><a className="button small secondary" href="#/app/settings">开始使用</a></nav></header>
    <main id="main-content" tabIndex={-1}>
      <section className="hero">
        <div className="hero-copy"><h1>接下来，<br/>故事由你推动。</h1><p>与 AI 进行连续对话。<br/>故事独立保存，重要经历随对话保留。</p>
          <div className="hero-actions"><a className="button primary" href="#/app/settings">开始使用 <ArrowRight size={17}/></a><a className="text-button" href="#/demo/chat">浏览示例 <ArrowRight size={15}/></a></div>
        </div>
        <a href="#/demo/chat" className="hero-art" aria-label="浏览星海观测站示例故事"><img src={asset('observatory.webp')} alt="云海之上，旅人仰望星空中的巨大观测装置" fetchPriority="high"/><div className="art-caption"><span>示例故事</span><h2>星海观测站</h2><ArrowRight size={20}/></div></a>
      </section>
      <details className="home-about"><summary>关于 StoryCanvas</summary>
        <p>StoryCanvas AI 是一个结合文本生成、长期记忆与场景配图的互动故事系统。你用自己的话描述行动或做出决策，AI 根据已有剧情生成后续内容，让故事随着对话推进。</p>
        <p>每个故事独立保存对话记录与记忆。系统从对话中提取重要人物、物品和事件，为后续生成提供背景。你可以查看和修正这些记忆，也可以从保存的故事继续，或复制存档尝试不同的选择。</p>
        <p>需要插图时，系统将本轮剧情转化为场景描述，再生成图片。文字与插图全部完成后一起呈现，图片保留在对应的对话中。公开示例展示了这一过程，无需连接服务即可浏览。</p>
      </details>
    </main>
    <footer className="home-footer"><span>StoryCanvas AI</span><a href="https://github.com/l399535557-ctrl/StoryCanvas-AI" target="_blank" rel="noopener noreferrer"><Github size={15}/>项目源码</a></footer>
  </div>
}
