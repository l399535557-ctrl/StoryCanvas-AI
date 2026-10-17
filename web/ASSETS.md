# 示例场景素材

这些图片只用于公开、只读示例，不包含真实用户故事或私有后端输出。

| 文件 | 用途 | 来源 |
| --- | --- | --- |
| `public/assets/observatory.webp` | 首页封面、第三轮露台场景 | 项目原有公开素材 |
| `public/assets/observatory-hall.webp` | 第一轮雨夜观测站大厅 | 内置 imagegen 生成，以上图为画风参考 |
| `public/assets/observatory-console.webp` | 第二轮月纹钥匙启动控制台 | 内置 imagegen 生成，以上图为画风参考 |

前两张为 1536 × 1024 横向插图，保存时仅进行 WebP 编码压缩。场景提示分别为：雨夜铜门内、积水黄铜纹路、中央星图与月纹钥匙；旅行者转动钥匙、开启穹顶、星图投影与星光落在手上。统一深蓝与黄铜金色，不添加文字、界面或水印。

示例和正式模式使用相同的 `Turn.image_tasks`、`StoryText`、`SceneImage` 与原图弹窗。`taskImageURL` 仅负责将示例图片映射到本地资产、将正式图片映射到网关 `/images/` 路径；同一张图在聊天和插图库中复用。
