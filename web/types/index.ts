// 文档信息类型
export interface DocumentInfo {
  id: string
  document_code?: string
  title?: string
  series_id?: string
  file_name: string
  file_path?: string
  file_hash?: string
  file_size?: number
  file_format?: string
  page_count?: number
  revision?: string
  publication_date?: string
  effective_date?: string
  issuer?: string
  language?: string
  source_type?: string
  parser?: string
  parser_version?: string
  processing_status?: 'pending' | 'processing' | 'completed' | 'failed'
  processing_started_at?: string
  processing_finished_at?: string
  processing_error?: string
  item_count: number
  text_count: number
  title_count: number
  table_count: number
  picture_count: number
  formula_count: number
  metadata?: Record<string, any>
  created_at?: string
  updated_at?: string
}

// 文档 Item 类型
export interface DocItem {
  id: string
  document_id: string
  page_id: string
  parent_id?: string
  label: string
  text?: string
  order_index: number
  bbox?: { l: number; t: number; r: number; b: number }
  metadata?: Record<string, any>
  content?: Record<string, any>
  is_rag_enabled: boolean
  textualization?: string
  raw_json?: Record<string, any>
  created_at?: string
  updated_at?: string
}

// API 响应类型
export interface ApiResponse<T = any> {
  success: boolean
  message: string
  data?: T
}

// 文本化请求类型
export interface TextualizeRequest {
  document_id?: string
  label?: string
  vlm_backend_type: string
  vlm_api_key?: string
  vlm_base_url?: string
  vlm_model: string
  dry_run: boolean
}

// 文本化响应类型
export interface TextualizeResponse {
  success: boolean
  message: string
  stats: {
    total: number
    success: number
    failed: number
  }
}

// 统计信息类型
export interface ItemStatistics {
  document_id: string
  total_items: number
  textualized: number
  needs_textualization: number
  type_distribution: Record<string, number>
}

// 文档树节点类型
export interface TreeNode {
  id: string
  label: string
  type: 'directory' | 'file'
  count?: number
  children?: TreeNode[]
  document?: DocumentInfo
  path?: string
}
