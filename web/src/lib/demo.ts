import type { ImageTask, Memory, Save, Turn } from './types'
import { asset } from './utils'

// Public, authored fixtures only. Never captures a user's real conversation.
export const demoSave: Save = {
  id: 'demo-observatory', name: '星海观测站', created_at: 1791028800, updated_at: 1791030600,
  archived_at: null, turn_count: 3, memory_count: 3,
}
export const demoTask: ImageTask = {
  id: 'example-scene-01', save_id: demoSave.id, turn_id: 3, request_id: 'example-request-03',
  status: 'succeeded', image_filename: null, error: null,
  created_at: 1791030570, started_at: 1791030570, finished_at: 1791030600,
  duration_seconds: null, retry_of_task_id: null, backend: 'comfy-sdxl',
}
export const demoTurns: Turn[] = [
  { id: 1, user_text: '我在暴雨中抵达废弃的星海观测站。', created_at: 1791028800, image_tasks: [],
    assistant_text: '铜门在你的掌心下发出沉闷的回响。你推开门，雨声被隔在身后，只有鞋底带进来的水滴，沿着地面的黄铜纹路缓缓流动。\n\n大厅中央，一幅星图仍在无声运转。没有电源，也没有守夜人。控制台旁放着一枚刻有月纹的钥匙，仿佛已经在这里等待了很久。' },
  { id: 2, user_text: '我拿起月纹钥匙，尝试启动控制台。', created_at: 1791029700, image_tasks: [],
    assistant_text: '钥匙恰好嵌入控制台中央的凹槽。你转动它，墙壁深处传来齿轮咬合的声音。\n\n穹顶缓缓开启，冰冷的星光落在你的手背上。星图浮现出一行文字：**北侧档案室，午夜解锁。** 下方是一组陌生的坐标。\n\n你把坐标记下来。距离午夜，还有最后一刻钟。' },
  { id: 3, user_text: '我沿着星光走上露台，抬头寻找坐标指向的地方。', created_at: 1791030600,
    image_tasks: [demoTask], assistant_text: `露台的尽头没有栏杆，只有一片铺向天边的云海。雨已经停了。\n\n你循着光线抬起头，一座巨大的环形观测装置悬在夜空，金色的圆盘像一只缓缓睁开的眼睛。星光从它的中心垂落，与你脚下的纹路连成一线。\n\n那组坐标指向的并不是远方。\n\n**而是你的正上方。**\n\n![星海观测站示例插图](${asset('observatory.webp')})` },
]
export const demoMemories: Memory[] = [
  { id: 1, memory_type: 'world', content: '星海观测站的中央星图在停电后仍能独立运转。', tags: ['观测站', '星图'], entities: ['星海观测站'], importance: 4, source_turn_id: 1 },
  { id: 2, memory_type: 'item', content: '月纹钥匙可以启动观测站控制台。', tags: ['月纹钥匙', '控制台'], entities: ['月纹钥匙'], importance: 5, source_turn_id: 2 },
  { id: 3, memory_type: 'event', content: '北侧档案室将在午夜解锁。', tags: ['档案室', '午夜'], entities: ['北侧档案室'], importance: 5, source_turn_id: 2 },
].map(item => ({ ...item, story_time: '第一章', supersedes_memory_id: null, status: 'active', created_at: 1791030600, updated_at: 1791030600, archived_at: null })) as Memory[]
