'use client'

import { useState } from 'react'
import Link from 'next/link'
import { searchDocuments } from '@/lib/api'
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
import { Search, FileText, Highlighter, ChevronDown, ChevronUp, Home } from 'lucide-react'

interface SearchResult {
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
}

interface SearchResponse {
  query: string
  total: number
  results: SearchResult[]
  reranked: boolean
}

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [searchType, setSearchType] = useState('hybrid')
  const [topK, setTopK] = useState(20)
  const [rerankTopK, setRerankTopK] = useState(10)
  const [threshold, setThreshold] = useState(0.3)
  const [enableRerank, setEnableRerank] = useState(true)
  const [results, setResults] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [expandedChunks, setExpandedChunks] = useState<Set<number>>(new Set())

  const handleSearch = async () => {
    if (!query.trim()) return

    setLoading(true)
    try {
      const response = await searchDocuments({
        query: query.trim(),
        search_type: searchType,
        top_k: topK,
        rerank_top_k: rerankTopK,
        threshold: threshold,
        enable_rerank: enableRerank,
      })
      setResults(response)
    } catch (error) {
      console.error('Search failed:', error)
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

  const getScoreColor = (score: number) => {
    if (score >= 0.7) return 'bg-green-500'
    if (score >= 0.5) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  const getScoreLabel = (score: number) => {
    if (score >= 0.7) return '高相关'
    if (score >= 0.5) return '中相关'
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
            <CardContent>
              <div className="flex flex-col md:flex-row gap-6">
                {/* 左侧：参数设置 */}
                <div className="w-full md:w-80 lg:w-96 space-y-4 border-r pr-6">
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

                  <Separator />

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

                  <Separator />

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

                  <Separator />

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
                      />
                    </div>
                  </div>

                  <Separator />

                  <div className="flex items-center space-x-2">
                    <Switch
                      id="enable-rerank"
                      checked={enableRerank}
                      onCheckedChange={setEnableRerank}
                    />
                    <Label htmlFor="enable-rerank">启用重排 (Rerank)</Label>
                  </div>
                </div>

                {/* 右侧：查询输入 */}
                <div className="flex-1">
                  <Label htmlFor="query">查询内容</Label>
                  <div className="flex flex-col gap-2 mt-2">
                    <Textarea
                      id="query"
                      placeholder="输入您的问题，例如：eUICC 架构是什么？&#10;支持多行输入..."
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      className="min-h-[200px] resize-y"
                    />
                    <div className="flex justify-end">
                      <Button onClick={handleSearch} disabled={loading || !query.trim()}>
                        <Search className="h-4 w-4 mr-2" />
                        {loading ? '检索中...' : '检索'}
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

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
                    {results.reranked && (
                      <Badge variant="secondary">
                        <Highlighter className="h-3 w-3 mr-1" />
                        已重排
                      </Badge>
                    )}
                  </div>
                </CardTitle>
                <CardDescription>
                  查询: "{results.query}"
                </CardDescription>
              </CardHeader>
              <CardContent>
                {results.results.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    没有找到相关的文档片段
                  </div>
                ) : (
                  <div className="space-y-4">
                    {results.results.map((result, idx) => (
                      <Card key={result.id} className="overflow-hidden">
                        <CardContent className="p-4">
                          {/* 结果头部 */}
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <FileText className="h-4 w-4 text-muted-foreground" />
                              <span className="text-sm font-medium">
                                结果 #{idx + 1}
                              </span>
                              <Badge variant="outline" className="text-xs">
                                Chunk {result.chunk_index}
                              </Badge>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className={`w-3 h-3 rounded-full ${getScoreColor(result.score)}`} />
                              <span className="text-sm font-medium">
                                {result.score.toFixed(3)}
                              </span>
                              <Badge variant="outline" className="text-xs">
                                {getScoreLabel(result.score)}
                              </Badge>
                            </div>
                          </div>

                          {/* 标题路径 */}
                          {result.heading_path && (
                            <div className="text-xs text-muted-foreground mb-2">
                              📍 {result.heading_path}
                            </div>
                          )}

                          {/* 页面信息 */}
                          {result.page_nos.length > 0 && (
                            <div className="text-xs text-muted-foreground mb-2">
                              📄 页码: {result.page_nos.join(', ')}
                            </div>
                          )}

                          {/* 文本内容 */}
                          <div className="text-sm bg-muted p-3 rounded-md whitespace-pre-wrap">
                            {expandedChunks.has(idx)
                              ? result.text
                              : result.text.substring(0, 300) + (result.text.length > 300 ? '...' : '')}
                          </div>

                          {/* 展开/折叠按钮 */}
                          {result.text.length > 300 && (
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
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </main>
    </div>
  )
}
