import axios from 'axios'
import type { DocumentInfo, DocItem, ApiResponse, TextualizeRequest, TextualizeResponse, ItemStatistics } from '@/types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

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
    limit?: number
    offset?: number
  }
): Promise<DocItem[]> {
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
