import { ArrowDown, ArrowRight, ArrowUpRight, BookOpen, Compass, Database, Image, Github, Sparkles } from 'lucide-react'
import { Brand } from '../components/ui'
import { asset } from '../lib/utils'

export function Home() {
  return <div className="home">
    <header className="home-header"><Brand/><nav aria-label="首页导航"><a href="#how-it-works" onClick={e => { e.preventDefault(); document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' }) }}>关于系统</a><a href="#/demo/chat">示例故事</a><a className="button small secondary" href="#/app/settings">进入工作台 <ArrowUpRight size={15}/></a></nav></header>
    <main id="main-content" tabIndex={-1}>
      <section className="hero">
        <div className="hero-copy"><span className="eyebrow"><span className="tiny-dot"/>LOCAL-FIRST · MULTIMODAL STORYTELLING</span>
          <h1>你的选择，<br/>让<span>故事发生。</span></h1>
          <p>走进一个尚未写完的世界。<br/>输入你的行动，让 AI 延续剧情、记住经历，<br className="desktop-break"/>并将新的场景绘成插图。</p>
          <div className="hero-actions"><a className="button primary" href="#/app/settings">开始我的故事 <ArrowRight size={17}/></a><a className="button ghost" href="#/demo/chat"><BookOpen size={17}/>浏览示例</a></div>
          <div className="hero-caption"><span className="orbit-mark">✦</span><span>每一次决定，都通向新的故事。</span></div>
        </div>
        <a href="#/demo/chat" className="hero-art" aria-label="浏览星海观测站示例故事"><img src={asset('observatory.webp')} alt="云海之上，旅人仰望星空中的巨大观测装置" fetchPriority="high"/>
          <div className="art-top"><span><Sparkles size={12}/>公开示例插图</span><ArrowUpRight size={20}/></div>
          <div className="art-caption"><span className="eyebrow">A GLIMPSE INTO THE STORY</span><h2>星海观测站</h2><p>那组坐标指向的并不是远方。<br/>而是你的正上方。</p><span className="art-link">走进这个故事 <ArrowRight size={15}/></span></div>
        </a>
      </section>
      <div className="home-divider"><span>一个行动，一段剧情，一幅新的场景。</span><ArrowDown size={18}/></div>
      <section id="how-it-works" className="how-section"><div className="section-intro"><span className="eyebrow">THE STORY CONTINUES</span><h2>世界会记得<br/>你的选择。</h2><p>故事、记忆与插图，在同一个工作台里延续。</p></div><div className="steps">
        <article><span className="step-number">01</span><div><h3><Compass size={19}/>做出你的决定</h3><p>你可以推开一扇门，也可以改变方向。用自己的话输入行动，让剧情随选择展开。</p></div></article>
        <article><span className="step-number">02</span><div><h3><Database size={19}/>让故事保持连贯</h3><p>每个故事独立保存。长期记忆保留重要人物、物品与事件，在后续对话中提供相关背景。</p></div></article>
        <article><span className="step-number">03</span><div><h3><Image size={19}/>看见新的场景</h3><p>需要插图时，AI 将剧情转化为视觉描述，交由 ComfyUI 绘制。整轮完成后，文字与图片一起返回。</p></div></article>
      </div></section>
      <section className="home-invitation"><div><span className="eyebrow">YOUR STORY, YOUR CANVAS</span><h2>下一步，由你决定。</h2><p>先浏览公开示例，或连接自己的网关开始冒险。</p></div><a href="#/demo/chat" className="button primary">浏览示例故事 <ArrowRight size={17}/></a></section>
    </main>
    <footer className="home-footer"><Brand compact/><span>本地优先的多模态互动故事系统</span><a href="https://github.com/l399535557-ctrl/StoryCanvas-AI" target="_blank" rel="noopener noreferrer"><Github size={16}/>GitHub <ArrowUpRight size={13}/></a></footer>
  </div>
}
