'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { getDocument, listDocumentItems, getItemStatistics, listDocumentChunks } from '@/lib/api'
import type { DocumentInfo, DocItem, Chunk, ItemStatistics, PaginatedItemsResponse } from '@/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useToast } from '@/hooks/use-toast'
import { formatDate, truncateText } from '@/lib/utils'
import { ArrowLeft, FileText, Table2, Image, List, Hash, BookOpen, ChevronLeft, ChevronRight, Blocks, Scan, Link2, Eye } from 'lucide-react'

type TabType = 'items' | 'chunks'

export default function DocumentDetail() {
  const params = useParams()
  const router = useRouter()
  const { toast } = useToast()
  const documentId = params.id as string

  const [document, setDocument] = useState<DocumentInfo | null>(null)
  const [items, setItems] = useState<DocItem[]>([])
  const [chunks, setChunks] = useState<Chunk[]>([])
  const [stats, setStats] = useState<ItemStatistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [filterLabel, setFilterLabel] = useState<string>('')
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalItems, setTotalItems] = useState(0)
  const pageSize = 20
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())
  const [activeTab, setActiveTab] = useState<TabType>('items')
  const [chunksLoading, setChunksLoading] = useState(false)
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set())
  const [chunkFilterRag, setChunkFilterRag] = useState<boolean | undefined>(undefined)
  const [chunkTokenLimit, setChunkTokenLimit] = useState<number | undefined>(undefined)
  const [chunkPage, setChunkPage] = useState(1)
  const [chunkTotalPages, setChunkTotalPages] = useState(1)
  const [chunkTotalItems, setChunkTotalItems] = useState(0)
  const chunkPageSize = 20
  const [imageViewer, setImageViewer] = useState<{ open: boolean; src: string; title: string }>({ open: false, src: '', title: '' })

  const toggleItem = (itemId: string) => {
    setExpandedItems(prev => {
      const next = new Set(prev)
      if (next.has(itemId)) {
        next.delete(itemId)
      } else {
        next.add(itemId)
      }
      return next
    })
  }

  const toggleChunk = (chunkId: string) => {
    setExpandedChunks(prev => {
      const next = new Set(prev)
      if (next.has(chunkId)) {
        next.delete(chunkId)
      } else {
        next.add(chunkId)
      }
      return next
    })
  }

  useEffect(() => {
    loadData()
  }, [documentId, currentPage, filterLabel])

  const loadData = async () => {
    setLoading(true)
    try {
      const [doc, paginatedItems, docStats] = await Promise.all([
        getDocument(documentId),
        listDocumentItems(documentId, {
          label: filterLabel || undefined,
          page: currentPage,
          page_size: pageSize,
        }),
        getItemStatistics(documentId),
      ])
      setDocument(doc)
      setItems(paginatedItems.items)
      setTotalPages(paginatedItems.total_pages)
      setTotalItems(paginatedItems.total)
      setStats(docStats)
    } catch (error) {
      console.error('Failed to load document:', error)
      toast({
        title: '加载失败',
        description: '无法加载文档详情',
        variant: 'destructive',
      })
    } finally {
      setLoading(false)
    }
  }

  const loadChunks = async () => {
    setChunksLoading(true)
    try {
      const data = await listDocumentChunks(documentId, {
        is_rag_enabled: chunkFilterRag,
        chunk_token_limit: chunkTokenLimit,
        page: chunkPage,
        page_size: chunkPageSize,
      })
      setChunks(data.items)
      setChunkTotalPages(data.total_pages)
      setChunkTotalItems(data.total)
    } catch (error) {
      console.error('Failed to load chunks:', error)
      toast({
        title: '加载失败',
        description: '无法加载 Chunk 信息',
        variant: 'destructive',
      })
    } finally {
      setChunksLoading(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'chunks') {
      loadChunks()
    }
  }, [documentId, chunkFilterRag, chunkTokenLimit, chunkPage, activeTab])

  const filteredItems = filterLabel
    ? items.filter(item => item.label === filterLabel)
    : items

  // 生成分页页码
  const getPageNumbers = () => {
    const pages: number[] = []
    const maxVisible = 5
    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) pages.push(i)
    } else {
      if (currentPage <= 3) {
        for (let i = 1; i <= 4; i++) pages.push(i)
        pages.push(0) // 省略号
        pages.push(totalPages)
      } else if (currentPage >= totalPages - 2) {
        pages.push(1)
        pages.push(0)
        for (let i = totalPages - 3; i <= totalPages; i++) pages.push(i)
      } else {
        pages.push(1)
        pages.push(0)
        for (let i = currentPage - 1; i <= currentPage + 1; i++) pages.push(i)
        pages.push(0)
        pages.push(totalPages)
      }
    }
    return pages
  }

  // 生成 Chunk 分页页码
  const getPageNumbersForChunks = () => {
    const pages: number[] = []
    const maxVisible = 5
    if (chunkTotalPages <= maxVisible) {
      for (let i = 1; i <= chunkTotalPages; i++) pages.push(i)
    } else {
      if (chunkPage <= 3) {
        for (let i = 1; i <= 4; i++) pages.push(i)
        pages.push(0) // 省略号
        pages.push(chunkTotalPages)
      } else if (chunkPage >= chunkTotalPages - 2) {
        pages.push(1)
        pages.push(0)
        for (let i = chunkTotalPages - 3; i <= chunkTotalPages; i++) pages.push(i)
      } else {
        pages.push(1)
        pages.push(0)
        for (let i = chunkPage - 1; i <= chunkPage + 1; i++) pages.push(i)
        pages.push(0)
        pages.push(chunkTotalPages)
      }
    }
    return pages
  }

  const getLabelIcon = (label: string) => {
    const icons: Record<string, React.ReactNode> = {
      text: <FileText className="h-4 w-4" />,
      section_header: <Hash className="h-4 w-4" />,
      table: <Table2 className="h-4 w-4" />,
      picture: <Image className="h-4 w-4" />,
      list_item: <List className="h-4 w-4" />,
      document_index: <BookOpen className="h-4 w-4" />,
    }
    return icons[label] || <FileText className="h-4 w-4" />
  }

  const getLabelColor = (label: string) => {
    const colors: Record<string, string> = {
      text: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
      section_header: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
      table: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
      picture: 'bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200',
      list_item: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
      document_index: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
    }
    return colors[label] || 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-muted-foreground">加载中...</div>
      </div>
    )
  }

  if (!document) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-bold mb-2">文档不存在</h2>
          <Link href="/">
            <Button variant="outline">返回首页</Button>
          </Link>
        </div>
      </div>
    )
  }

  const textualizationProgress = stats
    ? Math.round((stats.textualized / stats.total_items) * 100)
    : 0

  return (
    <div className="min-h-screen bg-background">
      {/* 导航栏 */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4 mr-2" />
                返回
              </Button>
            </Link>
            <h1 className="text-xl font-bold truncate max-w-md">{document.file_name}</h1>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="container mx-auto px-4 py-8">
        {/* 文档信息卡片 */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>文档信息</CardTitle>
            <CardDescription>
              {document.document_code && `文档编号: ${document.document_code}`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-sm text-muted-foreground">标题</div>
                <div className="font-medium">{document.title || '-'}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">发布机构</div>
                <div className="font-medium">{document.issuer || '-'}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">语言</div>
                <div className="font-medium">{document.language || '-'}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">状态</div>
                <Badge variant={document.processing_status === 'completed' ? 'default' : 'secondary'}>
                  {document.processing_status || '未知'}
                </Badge>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">页数</div>
                <div className="font-medium">{document.page_count || '-'}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Item 总数</div>
                <div className="font-medium">{document.item_count}</div>
              </div>
              <div className="col-span-2 md:col-span-2">
                <div className="text-sm text-muted-foreground">文档连接</div>
                {document.file_path ? (
                  <a
                    href={`/api/docs/${document.id}/file`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-primary hover:underline inline-flex items-center gap-1.5"
                  >
                    <Link2 className="h-3.5 w-3.5" />
                    <span className="truncate max-w-[400px]">{document.file_path}</span>
                  </a>
                ) : (
                  <div className="font-medium text-muted-foreground">-</div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Tab 切换 */}
        <div className="mb-6">
          <div className="flex gap-2 border-b">
            <button
              onClick={() => setActiveTab('items')}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'items'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <FileText className="h-4 w-4 inline mr-2" />
              文档内容 ({stats?.total_items || 0})
            </button>
            <button
              onClick={() => setActiveTab('chunks')}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'chunks'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <Blocks className="h-4 w-4 inline mr-2" />
              Chunk 信息 ({chunks.length})
            </button>
          </div>
        </div>

        {/* 文档内容 Tab */}
        {activeTab === 'items' && (
          <Card>
            <CardHeader>
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                  <CardTitle>文档内容</CardTitle>
                  <CardDescription>
                    共 {filteredItems.length} 个 Item
                    {filterLabel && ` (过滤: ${filterLabel})`}
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <select
                    value={filterLabel}
                    onChange={(e) => {
                      setFilterLabel(e.target.value)
                      setCurrentPage(1)
                    }}
                    className="px-3 py-1 border rounded-md text-sm bg-background"
                  >
                    <option value="">所有类型</option>
                    <option value="text">文本</option>
                    <option value="section_header">标题</option>
                    <option value="table">表格</option>
                    <option value="picture">图片</option>
                    <option value="list_item">列表项</option>
                    <option value="document_index">文档索引</option>
                  </select>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {stats && (
                <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-4">
                  <Card>
                    <CardContent className="pt-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold">{stats.total_items}</div>
                        <div className="text-sm text-muted-foreground">总 Item</div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold">{stats.type_distribution.text || 0}</div>
                        <div className="text-sm text-muted-foreground">文本</div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold">{stats.type_distribution.section_header || 0}</div>
                        <div className="text-sm text-muted-foreground">标题</div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold">{stats.type_distribution.table || 0}</div>
                        <div className="text-sm text-muted-foreground">表格</div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold">{stats.type_distribution.picture || 0}</div>
                        <div className="text-sm text-muted-foreground">图片</div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold">{stats.textualized}/{stats.total_items}</div>
                        <div className="text-sm text-muted-foreground">已文本化</div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">顺序</TableHead>
                    <TableHead className="w-24">类型</TableHead>
                    <TableHead>内容</TableHead>
                    <TableHead className="w-32">文本化</TableHead>
                    <TableHead className="w-24">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((item) => {
                    const isExpanded = expandedItems.has(item.id)
                    const content = item.textualization || item.text || ''
                    const isLongContent = content.length > 200

                    return (
                      <TableRow
                        key={item.id}
                        className={isLongContent ? 'cursor-pointer' : ''}
                        onClick={() => isLongContent && toggleItem(item.id)}
                      >
                        <TableCell className="py-1.5 px-2 font-mono text-sm">{item.order_index}</TableCell>
                        <TableCell className="py-1.5 px-2">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${getLabelColor(item.label)}`}>
                            {getLabelIcon(item.label)}
                            {item.label}
                          </span>
                        </TableCell>
                        <TableCell className="py-1.5 px-2">
                          <div className="max-w-xl">
                            {item.textualization ? (
                              <div className={`text-sm ${isExpanded ? 'whitespace-pre-wrap' : 'line-clamp-1 whitespace-nowrap overflow-hidden text-ellipsis'}`} title={isExpanded ? undefined : item.textualization}>
                                {item.textualization}
                              </div>
                            ) : item.text ? (
                              <div className={`text-sm text-muted-foreground ${isExpanded ? 'whitespace-pre-wrap' : 'line-clamp-1 whitespace-nowrap overflow-hidden text-ellipsis'}`} title={isExpanded ? undefined : item.text}>
                                {item.text}
                              </div>
                            ) : (
                              <span className="text-sm text-muted-foreground">-</span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="py-1.5 px-2">
                          {item.textualization ? (
                            <Badge variant="default" className="text-xs px-2 py-0">已文本化</Badge>
                          ) : (
                            <Badge variant="secondary" className="text-xs px-2 py-0">待文本化</Badge>
                          )}
                        </TableCell>
                        <TableCell className="py-1.5 px-2">
                          {item.label === 'picture' && item.metadata?.image_path ? (
                            <Button
                              variant="outline"
                              size="sm"
                              className="text-xs gap-1.5"
                              onClick={(e) => {
                                e.stopPropagation()
                                const imagePath = item.metadata!.image_path
                                setImageViewer({
                                  open: true,
                                  src: imagePath,
                                  title: imagePath.split('/').pop() || '图片',
                                })
                              }}
                            >
                              <Eye className="h-3.5 w-3.5" />
                              查看图片
                            </Button>
                          ) : (
                            <span className="text-xs text-muted-foreground">-</span>
                          )}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>

              {/* 分页控件 */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t">
                  <div className="text-sm text-muted-foreground">
                    第 {currentPage} / {totalPages} 页，共 {totalItems} 条
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                      disabled={currentPage === 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    {getPageNumbers().map((page, idx) =>
                      page === 0 ? (
                        <span key={`ellipsis-${idx}`} className="px-2 text-muted-foreground">
                          ...
                        </span>
                      ) : (
                        <Button
                          key={page}
                          variant={currentPage === page ? 'default' : 'outline'}
                          size="sm"
                          onClick={() => setCurrentPage(page)}
                          className="w-8 h-8 p-0"
                        >
                          {page}
                        </Button>
                      )
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                      disabled={currentPage === totalPages}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Chunk 信息 Tab */}
        {activeTab === 'chunks' && (
          <Card>
            <CardHeader>
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                  <CardTitle>Chunk 信息</CardTitle>
                  <CardDescription>
                    共 {chunkTotalItems} 个 Chunk
                    {chunkFilterRag !== undefined && ` (RAG: ${chunkFilterRag ? '启用' : '禁用'})`}
                    {chunkTokenLimit && ` (${chunkTokenLimit} tokens)`}
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  {/* Token 限制过滤 */}
                  <div className="flex items-center gap-1">
                    {[undefined, 256, 512, 1024].map((limit) => (
                      <button
                        key={limit ?? 'all'}
                        onClick={() => { setChunkTokenLimit(limit); setChunkPage(1) }}
                        className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                          chunkTokenLimit === limit
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted text-muted-foreground hover:bg-muted/80'
                        }`}
                      >
                        {limit ? `${limit}` : '全部'}
                      </button>
                    ))}
                  </div>
                  {/* RAG 状态过滤 */}
                  <select
                    value={chunkFilterRag === undefined ? 'all' : chunkFilterRag ? 'enabled' : 'disabled'}
                    onChange={(e) => {
                      const val = e.target.value
                      setChunkFilterRag(val === 'all' ? undefined : val === 'enabled')
                      setChunkPage(1)
                    }}
                    className="px-3 py-1 border rounded-md text-sm bg-background"
                  >
                    <option value="all">所有 RAG 状态</option>
                    <option value="enabled">仅启用</option>
                    <option value="disabled">仅禁用</option>
                  </select>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {chunksLoading ? (
                <div className="text-center py-8 text-muted-foreground">加载中...</div>
              ) : chunks.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Scan className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>暂无 Chunk 数据</p>
                  <p className="text-sm mt-2">请先解析 PDF 文档以生成语义块</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Chunk 统计 */}
                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <Card>
                      <CardContent className="pt-4">
                        <div className="text-center">
                          <div className="text-2xl font-bold">{chunkTotalItems}</div>
                          <div className="text-sm text-muted-foreground">总 Chunk</div>
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-4">
                        <div className="text-center">
                          <div className="text-2xl font-bold">
                            {chunks.filter(c => c.is_rag_enabled).length}
                          </div>
                          <div className="text-sm text-muted-foreground">当前页 RAG 启用</div>
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-4">
                        <div className="text-center">
                          <div className="text-2xl font-bold">
                            {chunks.reduce((sum, c) => sum + (c.token_count || 0), 0)}
                          </div>
                          <div className="text-sm text-muted-foreground">当前页总 Token</div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  {/* Chunk 列表 */}
                  <div className="space-y-3">
                    {chunks.map((chunk) => {
                      const isExpanded = expandedChunks.has(chunk.id)
                      const isLongText = chunk.text.length > 300

                      return (
                        <Card key={chunk.id} className="overflow-hidden">
                          <div
                            className={`p-4 cursor-pointer ${isLongText ? '' : ''}`}
                            onClick={() => isLongText && toggleChunk(chunk.id)}
                          >
                            <div className="flex items-start justify-between gap-4 mb-2">
                              <div className="flex items-center gap-2">
                                <Badge variant="outline" className="text-xs">
                                  #{chunk.chunk_index}
                                </Badge>
                                {chunk.heading_path && (
                                  <span className="text-sm font-medium text-primary">
                                    {chunk.heading_path}
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-2">
                                <Badge variant={chunk.is_rag_enabled ? 'default' : 'outline'} className="text-xs">
                                  {chunk.is_rag_enabled ? 'RAG 启用' : 'RAG 禁用'}
                                </Badge>
                                {chunk.token_count !== null && chunk.token_count !== undefined && (
                                  <span className="text-xs text-muted-foreground">
                                    {chunk.token_count} tokens
                                  </span>
                                )}
                              </div>
                            </div>

                            {chunk.headings && chunk.headings.length > 0 && (
                              <div className="flex flex-wrap gap-1 mb-2">
                                {chunk.headings.map((h, i) => (
                                  <Badge key={i} variant="secondary" className="text-xs">
                                    {h}
                                  </Badge>
                                ))}
                              </div>
                            )}

                            <div className={`text-sm text-muted-foreground ${isExpanded ? 'whitespace-pre-wrap' : 'line-clamp-3'}`}>
                              {chunk.text}
                            </div>

                            <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                              {chunk.page_nos && chunk.page_nos.length > 0 && (
                                <span>页码: {chunk.page_nos.join(', ')}</span>
                              )}
                              {chunk.linked_item_ids && chunk.linked_item_ids.length > 0 && (
                                <span>关联 Items: {chunk.linked_item_ids.length} 个</span>
                              )}
                            </div>
                          </div>
                        </Card>
                      )
                    })}
                  </div>

                  {/* 分页控件 */}
                  {chunkTotalPages > 1 && (
                    <div className="flex items-center justify-between mt-4 pt-4 border-t">
                      <div className="text-sm text-muted-foreground">
                        第 {chunkPage} / {chunkTotalPages} 页，共 {chunkTotalItems} 条
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setChunkPage(p => Math.max(1, p - 1))}
                          disabled={chunkPage === 1}
                        >
                          <ChevronLeft className="h-4 w-4" />
                        </Button>
                        {getPageNumbersForChunks().map((page, idx) =>
                          page === 0 ? (
                            <span key={`chunk-ellipsis-${idx}`} className="px-2 text-muted-foreground">
                              ...
                            </span>
                          ) : (
                            <Button
                              key={`chunk-page-${page}`}
                              variant={chunkPage === page ? 'default' : 'outline'}
                              size="sm"
                              onClick={() => setChunkPage(page)}
                              className="w-8 h-8 p-0"
                            >
                              {page}
                            </Button>
                          )
                        )}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setChunkPage(p => Math.min(chunkTotalPages, p + 1))}
                          disabled={chunkPage === chunkTotalPages}
                        >
                          <ChevronRight className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </main>

      {/* 图片查看器 */}
      <Dialog open={imageViewer.open} onOpenChange={(open) => setImageViewer({ open, src: '', title: '' })}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-auto">
          <DialogHeader>
            <DialogTitle>{imageViewer.title}</DialogTitle>
          </DialogHeader>
          <div className="flex items-center justify-center">
            <img
              src={`/api/docs/${documentId}/file?image_path=${encodeURIComponent(imageViewer.src)}`}
              alt={imageViewer.title}
              className="max-w-full max-h-[80vh] object-contain"
            />
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
