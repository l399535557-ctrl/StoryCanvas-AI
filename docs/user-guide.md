# StoryCanvas AI 用户操作手册

## 1. 运行准备

在 Windows 10/11 上安装 Python 3.11 或更高版本，并准备可运行的 ComfyUI、SDXL
兼容模型和 OpenAI 兼容文本模型接口。仓库不包含模型权重。

首次安装：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
Copy-Item .env.example .env
```

至少配置 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`、`GATEWAY_API_KEY` 和
`CHECKPOINT_NAME`。真实密钥只能保存在本地 `.env` 中。

## 2. 启动和检查

先启动监听 `127.0.0.1:8188` 的 ComfyUI，再启动网关：

```powershell
.\scripts\start.ps1
```

浏览器访问 `http://127.0.0.1:8000/health` 检查服务状态，访问
`http://127.0.0.1:8000/docs` 打开交互式 API 文档。需要详细排查时运行：

```powershell
.\scripts\doctor.ps1
```

## 3. 创建演示数据

以下命令会在当前配置的 SQLite 数据库中新建一个通用演示存档。重复运行不会复制数据，
也不会覆盖已有同名存档：

```powershell
.\.venv\Scripts\storycanvas-seed-demo.exe
```

演示存档包含两轮故事和三条带来源关系的长期记忆，适合检查存档、历史和 RAG 管理接口。

## 4. 连接聊天客户端

在 Chatbox、SillyTavern 或其他 OpenAI 兼容客户端中填写：

- API 地址：`http://127.0.0.1:8000/v1`
- API 密钥：本地 `.env` 中的 `GATEWAY_API_KEY`
- 模型：`storycanvas`

常用命令包括 `/图`、`/图开`、`/图关`、`/存档`、`/存档列表`、`/记忆` 和
`/记忆状态`。客户端也可以使用 `story_save_id` 或 `X-Story-Save-ID` 精确选择存档。

## 5. 数据管理

在 `/docs` 中使用 `/v1/story` 下的接口可以完成：

- 新建、重命名、归档、恢复、复制及导入导出存档；
- 分页查看故事历史及其关联插图任务；
- 新增、修改、归档、恢复、标记冲突或修订长期记忆；
- 查看、取消和重试图像任务；
- 创建、查看和恢复数据库备份；
- 导出包含 Markdown 和本地插图的作品 ZIP。

所有管理接口都需要 `Authorization: Bearer <GATEWAY_API_KEY>`。

## 6. 备份与恢复

重要演示或迁移前，先调用 `POST /v1/story/backups` 创建快照。恢复接口会验证文件名、
数据库完整性和架构版本，并在替换数据库前自动生成 `pre-restore` 安全快照。

存档级迁移使用 JSON 导出和导入；面向展示的成果使用 publication ZIP，两者用途不同。

## 7. 诊断与故障处理

认证后访问 `GET /v1/story/diagnostics`，可以查看软件版本、数据库完整性、架构版本、
FTS5 状态、数据总量和各类任务数量。响应不会返回数据库路径、密钥、故事正文或内部提示词。

- `health.status=degraded`：通常表示 ComfyUI 未启动，但数据库和管理接口仍可使用。
- 文本请求返回 502：检查文本模型地址、密钥和网络。
- 图像任务失败：确认 ComfyUI、模型文件和 `.env` 中的模型名称，再通过任务接口重试。
- 服务意外关闭：重启后，遗留的排队或运行任务会自动标记为失败，不会永久卡住。

## 8. 数据安全

不要把 `.env`、SQLite 数据库、备份、运行日志、模型权重或生成图片提交到公开仓库。
远程访问应使用可信私网，不要直接把网关或图片目录暴露到公网。
