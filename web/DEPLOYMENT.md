# 公开访问与自动更新

GitHub Pages 托管 `web/dist`，公开首页与三轮图文示例，无需 Mac 或 Windows 持续运行。站点地址：

https://l399535557-ctrl.github.io/StoryCanvas-AI/

## 日常修改

本地仍在 `frontend/mac-ui` 分支开发。在仓库根目录提交并推送：

```sh
git add web
git commit -m "Update frontend"
git push origin frontend/mac-ui
```

推送后，`.github/workflows/deploy-web.yml` 自动安装锁定依赖、运行 lint 和测试、构建并发布网站。访问网址不变。只保存本地文件不会触发发布；失败的检查不会覆盖已上线的版本。

发布进度：仓库 Actions → Deploy StoryCanvas Web。可以在已有工作流运行中选择重新运行，重新发布该次提交。

修改部署工作流时，一并提交 `.github/workflows/deploy-web.yml`。当前只发布 `frontend/mac-ui` 分支，不会自动合并 `main`，后端的开发和运行不受此流程影响。

## 构建配置

- Node.js 24，`npm ci` 使用 `web/package-lock.json`。
- `VITE_ASSET_BASE` 取 Pages 的 `base_path` 并补上尾部 `/`，项目子目录中的脚本、样式、favicon 和三张配图均使用正确路径。
- `VITE_STATIC_HOST=true` 表示静态托管，设置页会说明正式生成需要另外连接 HTTPS 后端，且不会向 Pages 提交网关密钥。
- 使用 GitHub 提供的临时工作流令牌与 OIDC 部署，无需将个人令牌、模型密钥或网关密钥放进仓库。
- `/StoryCanvas-AI/deployment.json` 记录当前发布的提交、分支和构建时间，便于核对自动更新。

工作流只上传 `web/dist`，不上传 Python 服务、SQLite、Windows 本地目录或生成模型。前端应用代码仍位于 `web/`，部署工作流是为自动发布新增的仓库配置。

## 接入真实生成服务

GitHub Pages 仅提供静态网页，不运行 Python、LLM 或 ComfyUI。正式对话需要另行部署或公开 Windows 网关，提供 HTTPS 地址，并允许来自 `https://l399535557-ctrl.github.io` 的跨域请求；网页设置中再填写地址和授权密钥。

当前公开站点不包含真实后端地址或任何用户密钥，首页与图文示例无需登录即可浏览。

## 检查和回退

发布后刷新网页；若仍显示旧版，执行浏览器强制刷新。要恢复旧版，在前端分支撤销对应提交并推送，或者在 Actions 中重新运行已验证的旧部署。每次发布可以通过 `deployment.json` 核对提交编号。

官方参考：[GitHub Pages 自定义工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)、[Vite 静态部署](https://vite.dev/guide/static-deploy#github-pages)。
