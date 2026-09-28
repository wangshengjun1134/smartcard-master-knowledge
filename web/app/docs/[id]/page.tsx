'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { getDocument, listDocumentItems, getItemStatistics, textualizeItems } from '@/lib/api'
import type { DocumentInfo, DocItem, ItemStatistics, PaginatedItemsResponse } from '@/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Progress } from '@/components/ui/progress'
import { useToast } from '@/hooks/use-toast'
import { formatDate, truncateText } from '@/lib/utils'
import { ArrowLeft, FileText, Table2, Image, List, Hash, BookOpen, ChevronLeft, ChevronRight } from 'lucide-react'

export default function DocumentDetail() {
  const params = useParams()
  const router = useRouter()
  const { toast } = useToast()
  const documentId = params.id as string

  const [document, setDocument] = useState<DocumentInfo | null>(null)
  const [items, setItems] = useState<DocItem[]>([])
  const [stats, setStats] = useState<ItemStatistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [filterLabel, setFilterLabel] = useState<string>('')
  const [textualizing, setTextualizing] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalItems, setTotalItems] = useState(0)
  const pageSize = 20
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())

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

  const handleTextualize = async () => {
    setTextualizing(true)
    try {
      const result = await textualizeItems({
        document_id: documentId,
        vlm_backend_type: 'openai',
        vlm_model: 'qwen-vl-max',
        dry_run: false,
      })
      toast({
        title: '文本化完成',
        description: `成功: ${result.stats.success}, 失败: ${result.stats.failed}`,
      })
      await loadData()
    } catch (error) {
      console.error('Failed to textualize:', error)
      toast({
        title: '文本化失败',
        description: '请重试',
        variant: 'destructive',
      })
    } finally {
      setTextualizing(false)
    }
  }

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
          <Button onClick={handleTextualize} disabled={textualizing}>
            {textualizing ? '文本化中...' : '批量文本化'}
          </Button>
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
              <div>
                <div className="text-sm text-muted-foreground">已文本化</div>
                <div className="font-medium">{stats?.textualized || 0}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">待文本化</div>
                <div className="font-medium">{stats?.needs_textualization || 0}</div>
              </div>
            </div>

            {/* 文本化进度 */}
            {stats && stats.total_items > 0 && (
              <div className="mt-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-muted-foreground">文本化进度</span>
                  <span className="text-sm font-medium">{textualizationProgress}%</span>
                </div>
                <Progress value={textualizationProgress} className="h-2" />
              </div>
            )}
          </CardContent>
        </Card>

        {/* 统计卡片 */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-6">
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-2xl font-bold">{stats.total_items}</div>
                  <div className="text-sm text-muted-foreground">总 Item</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-2xl font-bold">{stats.type_distribution.text || 0}</div>
                  <div className="text-sm text-muted-foreground">文本</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-2xl font-bold">{stats.type_distribution.section_header || 0}</div>
                  <div className="text-sm text-muted-foreground">标题</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-2xl font-bold">{stats.type_distribution.table || 0}</div>
                  <div className="text-sm text-muted-foreground">表格</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-2xl font-bold">{stats.type_distribution.picture || 0}</div>
                  <div className="text-sm text-muted-foreground">图片</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-2xl font-bold">{stats.textualized}/{stats.total_items}</div>
                  <div className="text-sm text-muted-foreground">已文本化</div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Item 列表 */}
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
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">顺序</TableHead>
                  <TableHead className="w-24">类型</TableHead>
                  <TableHead>内容</TableHead>
                  <TableHead className="w-32">文本化</TableHead>
                  <TableHead className="w-24">RAG</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => {
                  const isExpanded = expandedItems.has(item.id)
                  return (
                    <TableRow
                      key={item.id}
                      className="cursor-pointer"
                      onClick={() => toggleItem(item.id)}
                    >
                      <TableCell className="font-mono text-sm">{item.order_index}</TableCell>
                      <TableCell>
                        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs ${getLabelColor(item.label)}`}>
                          {getLabelIcon(item.label)}
                          {item.label}
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="max-w-xl">
                          {item.textualization ? (
                            <div
                              className="text-sm whitespace-pre-wrap"
                              style={!isExpanded ? {
                                display: '-webkit-box',
                                WebkitLineClamp: '2',
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                              } : {}}
                            >
                              {isExpanded ? item.textualization : truncateText(item.textualization, 100)}
                            </div>
                          ) : item.text ? (
                            <div
                              className="text-sm text-muted-foreground whitespace-pre-wrap"
                              style={!isExpanded ? {
                                display: '-webkit-box',
                                WebkitLineClamp: '2',
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                              } : {}}
                            >
                              {isExpanded ? item.text : truncateText(item.text, 100)}
                            </div>
                          ) : (
                            <span className="text-sm text-muted-foreground">-</span>
                          )}
                          {(item.textualization || item.text) && (
                            <span className="text-xs text-muted-foreground mt-1 block">
                              {isExpanded ? '点击收起' : '点击展开'}
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {item.textualization ? (
                          <Badge variant="default">已文本化</Badge>
                        ) : (
                          <Badge variant="secondary">待文本化</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant={item.is_rag_enabled ? 'default' : 'outline'}>
                          {item.is_rag_enabled ? '启用' : '禁用'}
                        </Badge>
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
      </main>
    </div>
  )
}
