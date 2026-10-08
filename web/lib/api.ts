import axios from 'axios'
import type { DocumentInfo, DocItem, Chunk, ApiResponse, TextualizeRequest, TextualizeResponse, ItemStatistics, PaginatedItemsResponse, PaginatedChunksResponse, TreeNode } from '@/types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ==================== 文档管理 API ====================

export async function listDocuments(params?: {
  document_code?: string
  series_id?: string
  processing_status?: string
  file_hash?: string
  keyword?: string
  page?: number
  page_size?: number
}): Promise<{
  items: DocumentInfo[]
  total: number
  page: number
  page_size: number
  total_pages: number
}> {
  const response = await api.get('/api/docs', { params })
  return response.data
}

export async function getStatusCounts(): Promise<Record<string, number>> {
  const response = await api.get('/api/docs/status-counts')
  return response.data.counts
}

export async function getDocumentTree(): Promise<{
  tree: TreeNode[]
  files: { path: string; name: string; directory: string }[]
}> {
  const response = await api.get('/api/docs/tree')
  return response.data
}

export async function getDocument(documentId: string): Promise<DocumentInfo> {
  const response = await api.get(`/api/docs/${documentId}`)
  return response.data
}

export async function createDocument(doc: Omit<DocumentInfo, 'id' | 'created_at' | 'updated_at'>): Promise<DocumentInfo> {
  const response = await api.post('/api/docs', doc)
  return response.data
}

export async function updateDocument(documentId: string, doc: Partial<DocumentInfo>): Promise<DocumentInfo> {
  const response = await api.put(`/api/docs/${documentId}`, doc)
  return response.data
}

export async function deleteDocument(documentId: string): Promise<ApiResponse> {
  const response = await api.delete(`/api/docs/${documentId}`)
  return response.data
}

export async function uploadDocument(formData: FormData): Promise<DocumentInfo> {
  const response = await api.post('/api/docs/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function getDocumentStats(documentId: string): Promise<any> {
  const response = await api.get(`/api/docs/${documentId}/stats`)
  return response.data
}

// ==================== 文档 Item API ====================

export async function listDocumentItems(
  documentId: string,
  params?: {
    page_id?: string
    label?: string
    is_rag_enabled?: boolean
    order_by?: string
    page?: number
    page_size?: number
  }
): Promise<PaginatedItemsResponse> {
  const response = await api.get(`/api/docs/${documentId}/items`, { params })
  return response.data
}

export async function getDocumentItem(documentId: string, itemId: string): Promise<DocItem> {
  const response = await api.get(`/api/docs/${documentId}/items/${itemId}`)
  return response.data
}

export async function textualizeItems(request: TextualizeRequest): Promise<TextualizeResponse> {
  const response = await api.post(`/api/docs/${request.document_id}/items/textualize`, request)
  return response.data
}

export async function textualizeSingleItem(
  itemId: string,
  documentId: string,
  vlmConfig?: {
    vlm_backend_type?: string
    vlm_api_key?: string
    vlm_base_url?: string
    vlm_model?: string
  }
): Promise<DocItem> {
  const params = new URLSearchParams({ document_id: documentId })
  if (vlmConfig?.vlm_backend_type) params.append('vlm_backend_type', vlmConfig.vlm_backend_type)
  if (vlmConfig?.vlm_api_key) params.append('vlm_api_key', vlmConfig.vlm_api_key)
  if (vlmConfig?.vlm_base_url) params.append('vlm_base_url', vlmConfig.vlm_base_url)
  if (vlmConfig?.vlm_model) params.append('vlm_model', vlmConfig.vlm_model)

  const response = await api.post(`/api/docs/items/${itemId}/textualize?${params}`)
  return response.data
}

export async function getItemsNeedingTextualization(
  documentId: string,
  params?: { label?: string; limit?: number }
): Promise<{ total: number; items: DocItem[] }> {
  const response = await api.get(`/api/docs/${documentId}/items/needs-textualization`, { params })
  return response.data
}

export async function getItemStatistics(documentId: string): Promise<ItemStatistics> {
  const response = await api.get(`/api/docs/${documentId}/items/stats`)
  return response.data
}

// ==================== Chunk API ====================

export async function listDocumentChunks(
  documentId: string,
  params?: {
    is_rag_enabled?: boolean
    page?: number
    page_size?: number
  }
): Promise<PaginatedChunksResponse> {
  const response = await api.get(`/api/docs/${documentId}/chunks`, { params })
  return response.data
}

// ==================== 文档处理流程 API ====================

export async function parseDocument(request: {
  pdf_path: string
  document_id: string
  page_range?: [number, number]
  output_dir?: string
  do_ocr?: boolean
}): Promise<{ success: boolean; message: string }> {
  const response = await api.post('/api/docs/process/parse', request)
  return response.data
}

export async function parseAllDocuments(request: {
  parallel_count?: number
  output_dir?: string
  do_ocr?: boolean
}): Promise<{ success: boolean; message: string; total: number; parallel_count: number }> {
  const response = await api.post('/api/docs/process/parse-all', request)
  return response.data
}

export async function generateVLMDocuments(request: {
  document_id: string
  output_dir?: string
  backend_type?: string
  api_key?: string
  base_url?: string
  model?: string
  prompt?: string
  max_new_tokens?: number
}): Promise<{ success: boolean; message: string }> {
  const response = await api.post('/api/docs/process/vlm', request)
  return response.data
}

export async function vlmAllDocuments(request: {
  parallel_count?: number
  output_dir?: string
  backend_type?: string
  api_key?: string
  base_url?: string
  model?: string
  prompt?: string
  max_new_tokens?: number
  language?: string
  detail_level?: string
}): Promise<{ success: boolean; message: string; total: number; parallel_count: number }> {
  const response = await api.post('/api/docs/process/vlm-all', request)
  return response.data
}

export async function chunkDocument(request: {
  pdf_path: string
  document_id: string
  page_range?: [number, number]
  max_tokens?: number
  tokenizer_name?: string
  do_ocr?: boolean
}): Promise<{ success: boolean; message: string }> {
  const response = await api.post('/api/docs/process/chunk', request)
  return response.data
}

export async function chunkAllDocuments(request: {
  parallel_count?: number
  max_tokens?: number
  tokenizer_name?: string
  do_ocr?: boolean
}): Promise<{ success: boolean; message: string; total: number; parallel_count: number }> {
  const response = await api.post('/api/docs/process/chunk-all', request)
  return response.data
}

export async function generateEmbeddings(request: {
  document_id: string
  backend_type?: string
  api_key?: string
  base_url?: string
  model?: string
  model_name?: string
}): Promise<{ success: boolean; message: string }> {
  const response = await api.post('/api/docs/process/embedding', request)
  return response.data
}

export async function embeddingAllDocuments(request: {
  parallel_count?: number
  backend_type?: string
  api_key?: string
  base_url?: string
  model?: string
  model_name?: string
}): Promise<{ success: boolean; message: string; total: number; parallel_count: number }> {
  const response = await api.post('/api/docs/process/embedding-all', request)
  return response.data
}

// ==================== 文档检索 API ====================

export async function searchDocuments(request: {
  query: string
  document_id?: string
  search_type?: string
  top_k?: number
  rerank_top_k?: number
  threshold?: number
  enable_rerank?: boolean
}): Promise<{
  query: string
  total: number
  results: Array<{
    id: string
    document_id: string
    chunk_index: number
    text: string
    score: number
    headings: string[]
    heading_path: string
    page_nos: number[]
    token_count: number
    linked_item_ids: string[]
  }>
  reranked: boolean
}> {
  const response = await api.post('/api/search', request)
  return response.data
}
