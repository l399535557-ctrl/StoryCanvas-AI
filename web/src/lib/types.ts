export type TaskStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
export interface Save {
  id: string; name: string; created_at: number; updated_at: number
  archived_at: number | null; turn_count: number; memory_count: number
}
export interface ImageTask {
  id: string; save_id?: string; turn_id: number | null; request_id: string
  status: TaskStatus; image_filename: string | null; error: string | null
  created_at: number; started_at: number | null; finished_at: number | null
  duration_seconds: number | null; retry_of_task_id: string | null; backend: string
}
export interface Turn {
  id: number; user_text: string; assistant_text: string; created_at: number; image_tasks: ImageTask[]
}
export interface Memory {
  id: number; memory_type: string; content: string; tags: string[]; entities: string[]
  importance: number; story_time: string | null; source_turn_id: number | null
  supersedes_memory_id: number | null; status: 'active' | 'conflicted' | 'superseded'
  created_at: number; updated_at: number; archived_at: number | null
}
export interface MemoryInput {
  type: string; content: string; tags: string[]; entities: string[]; importance: number; story_time: string | null
}
export interface Backup { filename: string; size_bytes: number; created_at: number; schema_version?: number }
export interface Health {
  status: string; configuration: Record<string, boolean>; comfyui_ok: boolean
  device: string | null; image_backend: string; auto_image: boolean
  memory: { enabled: boolean; extract_enabled: boolean; active_save_id: string; top_k: number; context_max_chars: number }
}
export interface Diagnostics {
  version: string
  database: {
    integrity: string; schema_version: number; journal_mode: string; database_size_bytes: number
    fts_enabled: boolean; task_status_counts: Record<TaskStatus, number>; counts: Record<string, number | boolean>
  }
}
export interface Message { role: 'user' | 'assistant'; content: string }
export interface ChatPayload {
  model: 'storycanvas'; stream: boolean; story_save_id: string; messages: Message[]; temperature?: number; max_tokens?: number
}
export interface DataList<T> { data: T[]; limit?: number; offset?: number }
export interface SaveList extends DataList<Save> { active_save_id: string }
export type View = 'chat' | 'saves' | 'memories' | 'tasks' | 'gallery' | 'status' | 'settings'
export type Mode = 'demo' | 'app'
export interface Route { mode: Mode; view: View; home: boolean }
