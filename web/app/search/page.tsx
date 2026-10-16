'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ragSearchDocuments, getDocumentPageCount, rewriteQuery, RAGSearchResult, RAGSearchResponse } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Search, FileText, Highlighter, ChevronDown, ChevronUp, Home, ChevronLeft, ChevronRight, Sparkles } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [searchType, setSearchType] = useState('hybrid')
  const [topK, setTopK] = useState(50)
  const [rerankTopK, setRerankTopK] = useState(10)
  const [threshold, setThreshold] = useState(0.3)
  const [enableThreshold, setEnableThreshold] = useState(false)
  const [enableRerank, setEnableRerank] = useState(true)
  // scope
  const [seriesId, setSeriesId] = useState('')
  const [revision, setRevision] = useState('')
  const [versionPolicy, setVersionPolicy] = useState('all')
  // filters
  const [language, setLanguage] = useState('')
  const [pageId, setPageId] = useState('')
  const [headingPath, setHeadingPath] = useState('')
  // options
  const [includeContent, setIncludeContent] = useState(true)
  const [includeMetadata, setIncludeMetadata] = useState(true)
  const [includeCitations, setIncludeCitations] = useState(true)
  // rewrite
  const [enableRewrite, setEnableRewrite] = useState(false)
  const [rewriteApiUrl, setRewriteApiUrl] = useState('')
  const [rewriteApiKey, setRewriteApiKey] = useState('')
  const [rewriteModel, setRewriteModel] = useState('')
  const [rewritePrompt, setRewritePrompt] = useState('请将以下查询改写为多个不同角度的查询，每行一个：\n{query}')
  const [rewrittenQueries, setRewrittenQueries] = useState<string[]>([])
  const [rewriting, setRewriting] = useState(false)
  const [results, setResults] = useState<RAGSearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [expandedChunks, setExpandedChunks] = useState<Set<number>>(new Set())
  const [pdfViewer, setPdfViewer] = useState<{ open: boolean; documentId: string; currentPage: number; totalPages: number; documentName: string; targetPages: number[] }>({
    open: false,
    documentId: '',
    currentPage: 1,
    totalPages: 0,
    documentName: '',
    targetPages: [],
  })

  const splitList = (s: string) =>
    s.split(',').map((x) => x.trim()).filter(Boolean)

  const handleSearch = async () => {
    if (!query.trim()) return

    setLoading(true)
    setError(null)
    setRewrittenQueries([])
    
    try {
      let queries = [query.trim()]
      
      // 如果启用重写，先调用重写接口
      if (enableRewrite && rewriteApiUrl && rewriteApiKey && rewriteModel) {
        setRewriting(true)
        try {
          const rewriteResponse = await rewriteQuery({
            query: query.trim(),
            api_url: rewriteApiUrl,
            api_key: rewriteApiKey,
            model: rewriteModel,
            prompt: rewritePrompt,
          })
          queries = [query.trim(), ...rewriteResponse.rewritten_queries]
          setRewrittenQueries(rewriteResponse.rewritten_queries)
        } catch (rewriteErr: any) {
          console.error('Rewrite failed, using original query:', rewriteErr)
          // 重写失败时继续使用原始查询
        } finally {
          setRewriting(false)
        }
      }
      
      const response = await ragSearchDocuments({
        queries,
        scope: {
          series_id: splitList(seriesId),
          revision: splitList(revision),
          version_policy: versionPolicy,
        },
        retrieval: {
          retrieval_type: searchType,
          top_k: topK,
          rerank_enabled: enableRerank,
          rerank_top_k: rerankTopK,
          similarity_threshold: enableThreshold ? threshold : null,
        },
        filters: {
          page_id: splitList(pageId),
          heading_path: headingPath.trim() || null,
          language: language.trim() || null,
        },
        options: {
          include_content: includeContent,
          include_metadata: includeMetadata,
          include_citations: includeCitations,
        },
      })
      setResults(response)
    } catch (err: any) {
      const detail = err?.response?.data?.detail || '检索失败'
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail))
      setResults(null)
    } finally {
      setLoading(false)
    }
  }

  const toggleChunk = (index: number) => {
    const newExpanded = new Set(expandedChunks)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedChunks(newExpanded)
  }

  const openPdfViewer = async (result: RAGSearchResult) => {
    const pageNos = result.metadata?.page_nos || result.citation?.page_nos || []
    const firstPage = pageNos[0] || 1
    setPdfViewer({
      open: true,
      documentId: result.document_id,
      currentPage: firstPage,
      totalPages: 0,
      documentName: result.citation?.document_name || '',
      targetPages: pageNos,
    })
    try {
      const total = await getDocumentPageCount(result.document_id)
      setPdfViewer(prev => ({ ...prev, totalPages: total }))
    } catch (error) {
      console.error('Failed to get page count:', error)
    }
  }

  // 分数按排名着色（vector/keyword/hybrid/rerank 量纲不同，不做绝对值判断）
  const getRankColor = (idx: number) => {
    if (idx < 3) return 'bg-green-500'
    if (idx < 6) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  const getRankLabel = (idx: number) => {
    if (idx < 3) return '高相关'
    if (idx < 6) return '中相关'
    return '低相关'
  }

  return (
    <div className="min-h-screen bg-background">
      {/* 导航栏 */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Search className="h-6 w-6" />
            <h1 className="text-xl font-bold">SmartCard Knowledge Base - 文档检索</h1>
          </div>
          <nav className="flex items-center gap-4">
            <Link href="/" className="text-sm font-medium hover:underline flex items-center gap-1">
              <Home className="h-4 w-4" />
              文档管理
            </Link>
          </nav>
        </div>
      </header>

      {/* 主内容 */}
      <main className="container mx-auto px-4 py-6">
        <div className="max-w-5xl mx-auto">
          {/* 搜索卡片 */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-2xl">文档检索</CardTitle>
              <CardDescription>
                输入查询内容，系统将从知识库中检索最相关的文档片段
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* 参数设置（顶部） */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* 第一列：检索策略 */}
                <div className="space-y-4">
                  <div className="text-sm font-semibold">检索策略</div>
                  <div>
                    <Label htmlFor="search-type">检索类型</Label>
                    <Select value={searchType} onValueChange={setSearchType}>
                      <SelectTrigger className="mt-2">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="hybrid">混合检索 (Hybrid)</SelectItem>
                        <SelectItem value="vector">向量检索 (Vector)</SelectItem>
                        <SelectItem value="keyword">关键词检索 (Keyword)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="top-k">初始召回数量 (Top K)</Label>
                    <div className="mt-2">
                      <div className="text-sm text-muted-foreground mb-1">{topK} 条</div>
                      <Slider
                        id="top-k"
                        value={[topK]}
                        onValueChange={([v]) => setTopK(v)}
                        min={5}
                        max={100}
                        step={5}
                      />
                    </div>
                  </div>
                  <div>
                    <Label htmlFor="rerank-top-k">重排数量 (Rerank Top K)</Label>
                    <div className="mt-2">
                      <div className="text-sm text-muted-foreground mb-1">{rerankTopK} 条</div>
                      <Slider
                        id="rerank-top-k"
                        value={[rerankTopK]}
                        onValueChange={([v]) => setRerankTopK(v)}
                        min={1}
                        max={50}
                        step={1}
                        disabled={!enableRerank}
                      />
                    </div>
                  </div>
                  <div>
                    <Label htmlFor="threshold">相似度阈值</Label>
                    <div className="mt-2">
                      <div className="text-sm text-muted-foreground mb-1">{threshold.toFixed(2)}</div>
                      <Slider
                        id="threshold"
                        value={[threshold]}
                        onValueChange={([v]) => setThreshold(v)}
                        min={0}
                        max={1}
                        step={0.05}
                        disabled={!enableThreshold}
                      />
                    </div>
                  </div>
                  <div className="flex flex-col gap-2 pt-2">
                    <div className="flex items-center space-x-2">
                      <Switch
                        id="enable-rerank"
                        checked={enableRerank}
                        onCheckedChange={setEnableRerank}
                      />
                      <Label htmlFor="enable-rerank">启用重排 (Rerank)</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Switch
                        id="enable-threshold"
                        checked={enableThreshold}
                        onCheckedChange={setEnableThreshold}
                      />
                      <Label htmlFor="enable-threshold">启用相似度阈值</Label>
                    </div>
                  </div>
                </div>

                {/* 第二列：检索范围 */}
                <div className="space-y-4">
                  <div className="text-sm font-semibold">检索范围</div>
                  <div>
                    <Label htmlFor="version-policy">版本策略 (version_policy)</Label>
                    <Select value={versionPolicy} onValueChange={setVersionPolicy}>
                      <SelectTrigger className="mt-2">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">all（全部版本）</SelectItem>
                        <SelectItem value="latest">latest（每个系列最新版）</SelectItem>
                        <SelectItem value="exact">exact（指定版本）</SelectItem>
                        <SelectItem value="selected">selected（多版本）</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="series-id">规范系列 (series_id)</Label>
                    <Input
                      id="series-id"
                      className="mt-2"
                      placeholder="如 SGP.27，多个用逗号分隔"
                      value={seriesId}
                      onChange={(e) => setSeriesId(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="revision">版本 (revision)</Label>
                    <Input
                      id="revision"
                      className="mt-2"
                      placeholder="如 1.16，多个用逗号分隔"
                      value={revision}
                      onChange={(e) => setRevision(e.target.value)}
                    />
                  </div>
                </div>

                {/* 第三列：过滤条件 */}
                <div className="space-y-4">
                  <div className="text-sm font-semibold">过滤条件</div>
                  <div>
                    <Label htmlFor="language">语言 (language)</Label>
                    <Input
                      id="language"
                      className="mt-2"
                      placeholder="如 en"
                      value={language}
                      onChange={(e) => setLanguage(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="page-id">页码 (page_id)</Label>
                    <Input
                      id="page-id"
                      className="mt-2"
                      placeholder="如 19,20，多个用逗号分隔"
                      value={pageId}
                      onChange={(e) => setPageId(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="heading-path">章节路径 (heading_path)</Label>
                    <Input
                      id="heading-path"
                      className="mt-2"
                      placeholder="模糊匹配，如 4.2.18"
                      value={headingPath}
                      onChange={(e) => setHeadingPath(e.target.value)}
                    />
                  </div>
                </div>

                {/* 返回选项：横跨第2、3列 */}
                <div className="md:col-span-2">
                  <Separator />
                  <div className="pt-4">
                    <div className="text-sm font-semibold mb-3">返回选项</div>
                    <div className="flex items-center gap-6">
                      <div className="flex items-center space-x-2">
                        <Switch id="inc-content" checked={includeContent} onCheckedChange={setIncludeContent} />
                        <Label htmlFor="inc-content">返回正文</Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Switch id="inc-meta" checked={includeMetadata} onCheckedChange={setIncludeMetadata} />
                        <Label htmlFor="inc-meta">返回元数据</Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Switch id="inc-cite" checked={includeCitations} onCheckedChange={setIncludeCitations} />
                        <Label htmlFor="inc-cite">返回引用</Label>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <Separator />

              {/* 查询重写配置 */}
              <div className="space-y-4">
                <div className="flex items-center space-x-2">
                  <Switch
                    id="enable-rewrite"
                    checked={enableRewrite}
                    onCheckedChange={setEnableRewrite}
                  />
                  <Label htmlFor="enable-rewrite" className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4" />
                    启用查询重写 (Query Rewrite)
                  </Label>
                </div>
                
                {enableRewrite && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pl-6 border-l-2 border-primary/20">
                    <div>
                      <Label htmlFor="rewrite-api-url">API URL</Label>
                      <Input
                        id="rewrite-api-url"
                        className="mt-2"
                        placeholder="如 https://api.openai.com/v1/chat/completions"
                        value={rewriteApiUrl}
                        onChange={(e) => setRewriteApiUrl(e.target.value)}
                      />
                    </div>
                    <div>
                      <Label htmlFor="rewrite-api-key">API Key</Label>
                      <Input
                        id="rewrite-api-key"
                        type="password"
                        className="mt-2"
                        placeholder="sk-..."
                        value={rewriteApiKey}
                        onChange={(e) => setRewriteApiKey(e.target.value)}
                      />
                    </div>
                    <div>
                      <Label htmlFor="rewrite-model">模型</Label>
                      <Input
                        id="rewrite-model"
                        className="mt-2"
                        placeholder="如 gpt-4o-mini"
                        value={rewriteModel}
                        onChange={(e) => setRewriteModel(e.target.value)}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <Label htmlFor="rewrite-prompt">提示词模板</Label>
                      <Textarea
                        id="rewrite-prompt"
                        className="mt-2 min-h-[80px]"
                        placeholder="使用 {query} 作为占位符"
                        value={rewritePrompt}
                        onChange={(e) => setRewritePrompt(e.target.value)}
                      />
                    </div>
                  </div>
                )}
              </div>

              <Separator />

              {/* 查询输入（下方） */}
              <div>
                <Label htmlFor="query">查询内容</Label>
                <div className="flex flex-col gap-2 mt-2">
                  <Textarea
                    id="query"
                    placeholder="输入您的问题，例如：eUICC 架构是什么？&#10;支持多行输入..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    className="min-h-[160px] resize-y"
                  />
                  <div className="flex justify-end">
                    <Button onClick={handleSearch} disabled={loading || rewriting || !query.trim()}>
                      <Search className="h-4 w-4 mr-2" />
                      {rewriting ? '重写中...' : loading ? '检索中...' : '检索'}
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 错误提示 */}
          {error && (
            <Card className="mb-6 border-destructive">
              <CardContent className="p-4 text-sm text-destructive">
                检索失败：{error}
              </CardContent>
            </Card>
          )}

          {/* 结果展示 */}
          {results && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>检索结果</span>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">
                      共 {results.total} 条
                    </Badge>
                    <Badge variant="outline">
                      {results.profile}
                    </Badge>
                    {results.reranked && (
                      <Badge variant="secondary">
                        <Highlighter className="h-3 w-3 mr-1" />
                        已重排
                      </Badge>
                    )}
                  </div>
                </CardTitle>
                <CardDescription>
                  查询: "{results.queries.join(' | ')}"
                </CardDescription>
              </CardHeader>
              <CardContent>
                {rewrittenQueries.length > 0 && (
                  <div className="mb-4 p-3 rounded-md bg-muted/50 text-xs">
                    <div className="flex items-center gap-1 font-medium mb-1">
                      <Sparkles className="h-3 w-3" />
                      重写查询 ({rewrittenQueries.length})
                    </div>
                    <ul className="list-disc list-inside space-y-0.5 text-muted-foreground">
                      {rewrittenQueries.map((q, i) => (
                        <li key={i}>{q}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {results.results.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    没有找到相关的文档片段
                  </div>
                ) : (
                  <div className="space-y-4">
                    {results.results.map((result, idx) => {
                      const content = result.content || ''
                      const headingPath = result.metadata?.heading_path
                      const pageNos = result.metadata?.page_nos || result.citation?.page_nos || []
                      const docName = result.citation?.document_name
                      return (
                      <Card key={result.chunk_id} className="overflow-hidden">
                        <CardContent className="p-4">
                          {/* 结果头部 */}
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2 flex-wrap">
                              <FileText className="h-4 w-4 text-muted-foreground" />
                              <span className="text-sm font-medium">
                                结果 #{idx + 1}
                              </span>
                              {result.chunk_index != null && (
                                <Badge variant="outline" className="text-xs">
                                  Chunk {result.chunk_index}
                                </Badge>
                              )}
                              {result.citation?.series_id && (
                                <Badge variant="outline" className="text-xs">
                                  {result.citation.series_id}
                                  {result.citation.revision ? ` v${result.citation.revision}` : ''}
                                </Badge>
                              )}
                              {docName && (
                                <button
                                  onClick={() => openPdfViewer(result)}
                                  className="text-xs font-medium text-primary hover:underline cursor-pointer"
                                >
                                  {docName}
                                </button>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              <div className={`w-3 h-3 rounded-full ${getRankColor(idx)}`} />
                              <span className="text-sm font-medium">
                                {typeof result.score === 'number' ? result.score.toFixed(3) : '-'}
                              </span>
                              <Badge variant="outline" className="text-xs">
                                {getRankLabel(idx)}
                              </Badge>
                            </div>
                          </div>

                          {/* 标题路径 */}
                          {headingPath && (
                            <div className="text-xs text-muted-foreground mb-2">
                              📍 {headingPath}
                            </div>
                          )}

                          {/* 页面信息 */}
                          {pageNos.length > 0 && (
                            <div className="text-xs text-muted-foreground mb-2">
                              📄 页码: {pageNos.join(', ')}
                            </div>
                          )}

                          {/* 文本内容 */}
                          {content ? (
                            <>
                              <div className="text-sm bg-muted p-3 rounded-md whitespace-pre-wrap">
                                {expandedChunks.has(idx)
                                  ? content
                                  : content.substring(0, 300) + (content.length > 300 ? '...' : '')}
                              </div>
                              {content.length > 300 && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="mt-2"
                                  onClick={() => toggleChunk(idx)}
                                >
                                  {expandedChunks.has(idx) ? (
                                    <>
                                      <ChevronUp className="h-4 w-4 mr-1" />
                                      收起
                                    </>
                                  ) : (
                                    <>
                                      <ChevronDown className="h-4 w-4 mr-1" />
                                      展开完整内容
                                    </>
                                  )}
                                </Button>
                              )}
                            </>
                          ) : (
                            <div className="text-xs text-muted-foreground italic">
                              （未返回正文，include_content=false）
                            </div>
                          )}
                        </CardContent>
                      </Card>
                      )
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* PDF 查看器对话框 */}
        <Dialog open={pdfViewer.open} onOpenChange={(open) => setPdfViewer(prev => ({ ...prev, open }))}>
          <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                {pdfViewer.documentName}
                <span className="text-sm font-normal text-muted-foreground">
                  (第 {pdfViewer.currentPage}{pdfViewer.totalPages > 0 ? ` / ${pdfViewer.totalPages}` : ''} 页)
                </span>
              </DialogTitle>
              {pdfViewer.targetPages.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap pt-1">
                  <span className="text-xs text-muted-foreground">目标页:</span>
                  {pdfViewer.targetPages.map((page) => (
                    <button
                      key={page}
                      onClick={() => setPdfViewer(prev => ({ ...prev, currentPage: page }))}
                      className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                        pdfViewer.currentPage === page
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-muted-foreground hover:bg-muted/80'
                      }`}
                    >
                      {page}
                    </button>
                  ))}
                </div>
              )}
            </DialogHeader>
            <div className="flex-1 overflow-hidden">
              <iframe
                key={`${pdfViewer.documentId}-${pdfViewer.currentPage}`}
                src={`/api/docs/${pdfViewer.documentId}/pages?start_page=${pdfViewer.currentPage}&end_page=${pdfViewer.currentPage}`}
                className="w-full h-[70vh] border-0"
                title="PDF Viewer"
              />
            </div>
            {/* 翻页按钮 */}
            <div className="flex items-center justify-center gap-4 pt-2">
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                disabled={pdfViewer.currentPage <= 1}
                onClick={() => setPdfViewer(prev => ({ ...prev, currentPage: Math.max(1, prev.currentPage - 1) }))}
              >
                <ChevronLeft className="h-4 w-4" />
                上一页
              </Button>
              <span className="text-sm text-muted-foreground">
                {pdfViewer.currentPage}{pdfViewer.totalPages > 0 ? ` / ${pdfViewer.totalPages}` : ''}
              </span>
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                disabled={pdfViewer.totalPages > 0 && pdfViewer.currentPage >= pdfViewer.totalPages}
                onClick={() => setPdfViewer(prev => ({ ...prev, currentPage: prev.totalPages > 0 ? Math.min(prev.totalPages, prev.currentPage + 1) : prev.currentPage + 1 }))}
              >
                下一页
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  )
}
