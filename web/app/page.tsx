'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { listDocuments, uploadDocument, parseDocument, parseAllDocuments, vlmAllDocuments, generateVLMDocuments, chunkDocument, generateEmbeddings } from '@/lib/api'
import type { DocumentInfo } from '@/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useToast } from '@/hooks/use-toast'
import { formatFileSize, formatDate } from '@/lib/utils'
import { Upload, FileText, Search, Moon, Sun, Plus, ChevronLeft, ChevronRight, MoreHorizontal, Eye, FileUp, Image, Layers, Database, Play, Sparkles, RotateCcw, AlertCircle, CheckCircle, ArrowRight } from 'lucide-react'
import { useTheme } from 'next-themes'
import { DocumentTree } from '@/components/document-tree'

export default function Home() {
  const { toast } = useToast()
  const { theme, setTheme } = useTheme()
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const [uploadForm, setUploadForm] = useState({
    document_code: '',
    title: '',
    issuer: '',
    language: 'en',
  })
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalDocs, setTotalDocs] = useState(0)
  const [processingDoc, setProcessingDoc] = useState<string | null>(null)
  const [processingType, setProcessingType] = useState<string | null>(null)
  const [parsingAll, setParsingAll] = useState(false)
  const [vlmAll, setVlmAll] = useState(false)
  const [parseAllDialogOpen, setParseAllDialogOpen] = useState(false)
  const [vlmAllDialogOpen, setVlmAllDialogOpen] = useState(false)
  const [parseAllForm, setParseAllForm] = useState({
    parallel_count: 1,
    do_ocr: true,
    output_dir: 'output/pictures',
  })
  const [vlmAllForm, setVlmAllForm] = useState({
    parallel_count: 1,
    backend_type: 'openai',
    api_key: '',
    base_url: '',
    model: '',
    prompt: '',
    max_new_tokens: 2048,
    language: 'en',
    output_dir: 'output/pictures',
  })
  // Pipeline filter state
  const [pipelineFilter, setPipelineFilter] = useState<string>('')
  const pageSize = 20

  useEffect(() => {
    loadDocuments()
  }, [currentPage, pipelineFilter])

  const loadDocuments = async () => {
    try {
      const result = await listDocuments({
        processing_status: pipelineFilter || undefined,
        page: currentPage,
        page_size: pageSize,
      })
      setDocuments(result.items)
      setTotalDocs(result.total)
      setTotalPages(result.total_pages)
    } catch (error) {
      console.error('Failed to load documents:', error)
      toast({
        title: '加载失败',
        description: '无法加载文档列表，请检查后端服务是否启动',
        variant: 'destructive',
      })
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) {
      toast({
        title: '请选择文件',
        description: '请先选择要上传的 PDF 文件',
        variant: 'destructive',
      })
      return
    }

    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('document_code', uploadForm.document_code)
      formData.append('title', uploadForm.title)
      formData.append('issuer', uploadForm.issuer)
      formData.append('language', uploadForm.language)

      await uploadDocument(formData)
      toast({
        title: '上传成功',
        description: `${selectedFile.name} 已上传并开始解析`,
      })
      setCurrentPage(1)
      await loadDocuments()
      setUploadDialogOpen(false)
      setUploadForm({ document_code: '', title: '', issuer: '', language: 'en' })
      setSelectedFile(null)
    } catch (error) {
      console.error('Failed to upload document:', error)
      toast({
        title: '上传失败',
        description: '请重试',
        variant: 'destructive',
      })
    } finally {
      setUploading(false)
    }
  }

  const handleParse = async (doc: DocumentInfo) => {
    setProcessingDoc(doc.id)
    setProcessingType('parse')
    try {
      const result = await parseDocument({
        pdf_path: doc.file_path || '',
        document_id: doc.id,
        do_ocr: true,
      })
      toast({
        title: '解析任务已提交',
        description: result.message || '正在后台处理，请稍后刷新查看',
      })
      await loadDocuments()
    } catch (error: any) {
      toast({
        title: '解析失败',
        description: error.response?.data?.detail || '请重试',
        variant: 'destructive',
      })
    } finally {
      setProcessingDoc(null)
      setProcessingType(null)
    }
  }

  const handleParseAll = async () => {
    setParsingAll(true)
    try {
      const result = await parseAllDocuments({
        parallel_count: parseAllForm.parallel_count,
        do_ocr: parseAllForm.do_ocr,
        output_dir: parseAllForm.output_dir,
      })
      toast({
        title: '批量解析任务已提交',
        description: result.message || `已提交 ${result.total} 个文档的解析任务`,
      })
      await loadDocuments()
      setParseAllDialogOpen(false)
    } catch (error: any) {
      toast({
        title: '批量解析失败',
        description: error.response?.data?.detail || '请重试',
        variant: 'destructive',
      })
    } finally {
      setParsingAll(false)
    }
  }

  const handleVlmAll = async () => {
    setVlmAll(true)
    try {
      const result = await vlmAllDocuments({
        parallel_count: vlmAllForm.parallel_count,
        backend_type: vlmAllForm.backend_type,
        api_key: vlmAllForm.api_key || undefined,
        base_url: vlmAllForm.base_url || undefined,
        model: vlmAllForm.model || undefined,
        prompt: vlmAllForm.prompt || undefined,
        max_new_tokens: vlmAllForm.max_new_tokens,
        language: vlmAllForm.language,
        output_dir: vlmAllForm.output_dir,
      })
      toast({
        title: '批量 VLM 增强任务已提交',
        description: result.message || `已提交 ${result.total} 个文档的 VLM 增强任务`,
      })
      await loadDocuments()
      setVlmAllDialogOpen(false)
    } catch (error: any) {
      toast({
        title: '批量 VLM 增强失败',
        description: error.response?.data?.detail || '请重试',
        variant: 'destructive',
      })
    } finally {
      setVlmAll(false)
    }
  }

  const handleVLM = async (doc: DocumentInfo) => {
    setProcessingDoc(doc.id)
    setProcessingType('vlm')
    try {
      const result = await generateVLMDocuments({
        document_id: doc.id,
        backend_type: 'openai',
      })
      toast({
        title: 'VLM 任务已提交',
        description: result.message || '正在后台处理，请稍后刷新查看',
      })
      await loadDocuments()
    } catch (error: any) {
      toast({
        title: 'VLM 失败',
        description: error.response?.data?.detail || '请重试',
        variant: 'destructive',
      })
    } finally {
      setProcessingDoc(null)
      setProcessingType(null)
    }
  }

  const handleChunk = async (doc: DocumentInfo) => {
    setProcessingDoc(doc.id)
    setProcessingType('chunk')
    try {
      const result = await chunkDocument({
        pdf_path: doc.file_path || '',
        document_id: doc.id,
        max_tokens: 512,
      })
      toast({
        title: '分块任务已提交',
        description: result.message || '正在后台处理，请稍后刷新查看',
      })
      await loadDocuments()
    } catch (error: any) {
      toast({
        title: '分块失败',
        description: error.response?.data?.detail || '请重试',
        variant: 'destructive',
      })
    } finally {
      setProcessingDoc(null)
      setProcessingType(null)
    }
  }

  const handleEmbedding = async (doc: DocumentInfo) => {
    setProcessingDoc(doc.id)
    setProcessingType('embedding')
    try {
      const result = await generateEmbeddings({
        document_id: doc.id,
        backend_type: 'local',
      })
      toast({
        title: 'Embedding 任务已提交',
        description: result.message || '正在后台处理，请稍后刷新查看',
      })
      await loadDocuments()
    } catch (error: any) {
      toast({
        title: 'Embedding 失败',
        description: error.response?.data?.detail || '请重试',
        variant: 'destructive',
      })
    } finally {
      setProcessingDoc(null)
      setProcessingType(null)
    }
  }

  const getStatusBadge = (status?: string) => {
    const statusMap: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
      uploaded: { label: '已上传', variant: 'secondary' },
      parsing: { label: '解析中', variant: 'default' },
      parsed: { label: '已解析', variant: 'outline' },
      vlm_processing: { label: 'VLM处理中', variant: 'default' },
      vlm_completed: { label: 'VLM已完成', variant: 'outline' },
      chunking: { label: '分块中', variant: 'default' },
      chunked: { label: '已分块', variant: 'outline' },
      embedding: { label: 'Embedding中', variant: 'default' },
      embedded: { label: '已嵌入', variant: 'outline' },
      parse_failed: { label: '解析失败', variant: 'destructive' },
      vlm_failed: { label: 'VLM失败', variant: 'destructive' },
      chunk_failed: { label: '分块失败', variant: 'destructive' },
      embedding_failed: { label: 'Embedding失败', variant: 'destructive' },
      completed: { label: '已完成', variant: 'default' },
      failed: { label: '失败', variant: 'destructive' },
      pending: { label: '等待处理', variant: 'secondary' },
      processing: { label: '处理中', variant: 'default' },
    }
    const config = statusMap[status || 'pending'] || { label: status || 'unknown', variant: 'outline' as const }
    return <Badge variant={config.variant}>{config.label}</Badge>
  }

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

  return (
    <div className="min-h-screen bg-background">
      {/* 导航栏 */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="h-6 w-6" />
            <h1 className="text-xl font-bold">SmartCard Knowledge Base</h1>
          </div>
          <div className="flex items-center gap-4">
            <nav className="flex items-center gap-4">
              <Link href="/" className="text-sm font-medium hover:underline">
                文档管理
              </Link>
              <Link href="/search" className="text-sm font-medium hover:underline">
                文档检索
              </Link>
            </nav>
            <Button
              variant="outline"
              size="icon"
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            >
              <Sun className="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
              <Moon className="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
            </Button>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="container mx-auto px-4 py-4 h-[calc(100vh-80px)]">
        <div className="flex gap-6 h-full">
          {/* 左侧文档树 */}
          <div className="w-64 flex-shrink-0 flex flex-col h-full">
            <Card className="flex-1 flex flex-col overflow-hidden">
              <CardHeader className="pb-3 flex-shrink-0">
                <CardTitle className="text-lg">文档树</CardTitle>
                <CardDescription>
                  {totalDocs} 个文档
                </CardDescription>
              </CardHeader>
              <CardContent className="p-2 flex-1 overflow-y-auto min-h-0">
                <DocumentTree />
              </CardContent>
            </Card>
          </div>

          {/* 右侧主内容区 */}
          <div className="flex-1 min-w-0">
        {/* 页面标题 */}
        <div className="mb-4">
          <h2 className="text-2xl font-bold">文档管理</h2>
          <p className="text-muted-foreground">
            管理所有智能卡标准规范文档
          </p>
        </div>

        {/* Pipeline 状态过滤 */}
        <Card className="mb-4">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold">流水线状态过滤</span>
                <span className="text-xs text-muted-foreground">（点击节点进行筛选）</span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => { setPipelineFilter(''); setCurrentPage(1) }}
                className="text-xs h-7"
              >
                <RotateCcw className="h-3 w-3 mr-1" />
                重置
              </Button>
            </div>
            <div className="flex items-start gap-2 overflow-x-auto pb-1">
              {/* 全部 */}
              <button
                onClick={() => { setPipelineFilter(''); setCurrentPage(1) }}
                className={`flex-shrink-0 flex flex-col items-center px-3 py-2 rounded-lg border transition-all ${
                  pipelineFilter === ''
                    ? 'border-primary bg-primary/5 ring-1 ring-primary'
                    : 'border-border hover:bg-muted'
                }`}
              >
                <span className="text-xs font-semibold">全部</span>
                <span className={`text-xs mt-1 px-2 py-0.5 rounded-full font-bold ${
                  pipelineFilter === '' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
                }`}>{totalDocs}</span>
              </button>

              {/* Arrow */}
              <ArrowRight className="h-4 w-4 text-muted-foreground mt-2 flex-shrink-0" />

              {/* 已上传 */}
              <button
                onClick={() => { setPipelineFilter('uploaded'); setCurrentPage(1) }}
                className={`flex-1 min-w-[80px] flex flex-col items-center px-3 py-2 rounded-lg border transition-all ${
                  pipelineFilter === 'uploaded'
                    ? 'border-primary bg-primary/5 ring-1 ring-primary'
                    : 'border-border hover:bg-muted'
                }`}
              >
                <span className="text-xs font-semibold">已上传</span>
                <span className={`text-xs mt-1 px-2 py-0.5 rounded-full font-bold ${
                  pipelineFilter === 'uploaded' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
                }`}>
                  {documents.filter(d => d.processing_status === 'uploaded').length}
                </span>
              </button>

              {/* Arrow */}
              <ArrowRight className="h-4 w-4 text-muted-foreground mt-2 flex-shrink-0" />

              {/* 已解析 + 失败分支 */}
              <div className="flex-1 min-w-[80px] flex flex-col items-center">
                <button
                  onClick={() => { setPipelineFilter('parsed'); setCurrentPage(1) }}
                  className={`w-full flex flex-col items-center px-3 py-2 rounded-lg border transition-all ${
                    pipelineFilter === 'parsed'
                      ? 'border-primary bg-primary/5 ring-1 ring-primary'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  <span className="text-xs font-semibold">已解析</span>
                  <span className={`text-xs mt-1 px-2 py-0.5 rounded-full font-bold ${
                    pipelineFilter === 'parsed' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
                  }`}>
                    {documents.filter(d => d.processing_status === 'parsed').length}
                  </span>
                </button>
                <button
                  onClick={() => { setPipelineFilter('parse_failed'); setCurrentPage(1) }}
                  className={`w-full mt-1 flex items-center justify-center gap-1 px-2 py-1 rounded-lg border transition-all text-xs ${
                    pipelineFilter === 'parse_failed'
                      ? 'border-destructive bg-destructive/10 ring-1 ring-destructive'
                      : 'border-destructive/30 bg-destructive/5 hover:bg-destructive/10'
                  }`}
                >
                  <AlertCircle className="h-3 w-3 text-destructive" />
                  <span className="text-xs font-medium text-destructive">解析失败</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                    pipelineFilter === 'parse_failed' ? 'bg-destructive/20 text-destructive' : 'bg-destructive/10 text-destructive'
                  }`}>
                    {documents.filter(d => d.processing_status === 'parse_failed').length}
                  </span>
                </button>
              </div>

              {/* Arrow */}
              <ArrowRight className="h-4 w-4 text-muted-foreground mt-2 flex-shrink-0" />

              {/* VLM已完成 + 失败分支 */}
              <div className="flex-1 min-w-[80px] flex flex-col items-center">
                <button
                  onClick={() => { setPipelineFilter('vlm_completed'); setCurrentPage(1) }}
                  className={`w-full flex flex-col items-center px-3 py-2 rounded-lg border transition-all ${
                    pipelineFilter === 'vlm_completed'
                      ? 'border-primary bg-primary/5 ring-1 ring-primary'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  <span className="text-xs font-semibold">VLM已完成</span>
                  <span className={`text-xs mt-1 px-2 py-0.5 rounded-full font-bold ${
                    pipelineFilter === 'vlm_completed' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
                  }`}>
                    {documents.filter(d => d.processing_status === 'vlm_completed').length}
                  </span>
                </button>
                <button
                  onClick={() => { setPipelineFilter('vlm_failed'); setCurrentPage(1) }}
                  className={`w-full mt-1 flex items-center justify-center gap-1 px-2 py-1 rounded-lg border transition-all text-xs ${
                    pipelineFilter === 'vlm_failed'
                      ? 'border-destructive bg-destructive/10 ring-1 ring-destructive'
                      : 'border-destructive/30 bg-destructive/5 hover:bg-destructive/10'
                  }`}
                >
                  <AlertCircle className="h-3 w-3 text-destructive" />
                  <span className="text-xs font-medium text-destructive">VLM失败</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                    pipelineFilter === 'vlm_failed' ? 'bg-destructive/20 text-destructive' : 'bg-destructive/10 text-destructive'
                  }`}>
                    {documents.filter(d => d.processing_status === 'vlm_failed').length}
                  </span>
                </button>
              </div>

              {/* Arrow */}
              <ArrowRight className="h-4 w-4 text-muted-foreground mt-2 flex-shrink-0" />

              {/* 已分块 + 失败分支 */}
              <div className="flex-1 min-w-[80px] flex flex-col items-center">
                <button
                  onClick={() => { setPipelineFilter('chunked'); setCurrentPage(1) }}
                  className={`w-full flex flex-col items-center px-3 py-2 rounded-lg border transition-all ${
                    pipelineFilter === 'chunked'
                      ? 'border-primary bg-primary/5 ring-1 ring-primary'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  <span className="text-xs font-semibold">已分块</span>
                  <span className={`text-xs mt-1 px-2 py-0.5 rounded-full font-bold ${
                    pipelineFilter === 'chunked' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
                  }`}>
                    {documents.filter(d => d.processing_status === 'chunked').length}
                  </span>
                </button>
                <button
                  onClick={() => { setPipelineFilter('chunk_failed'); setCurrentPage(1) }}
                  className={`w-full mt-1 flex items-center justify-center gap-1 px-2 py-1 rounded-lg border transition-all text-xs ${
                    pipelineFilter === 'chunk_failed'
                      ? 'border-destructive bg-destructive/10 ring-1 ring-destructive'
                      : 'border-destructive/30 bg-destructive/5 hover:bg-destructive/10'
                  }`}
                >
                  <AlertCircle className="h-3 w-3 text-destructive" />
                  <span className="text-xs font-medium text-destructive">分块失败</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                    pipelineFilter === 'chunk_failed' ? 'bg-destructive/20 text-destructive' : 'bg-destructive/10 text-destructive'
                  }`}>
                    {documents.filter(d => d.processing_status === 'chunk_failed').length}
                  </span>
                </button>
              </div>

              {/* Arrow */}
              <ArrowRight className="h-4 w-4 text-muted-foreground mt-2 flex-shrink-0" />

              {/* 已嵌入 + 失败分支 */}
              <div className="flex-1 min-w-[80px] flex flex-col items-center">
                <button
                  onClick={() => { setPipelineFilter('embedded'); setCurrentPage(1) }}
                  className={`w-full flex flex-col items-center px-3 py-2 rounded-lg border transition-all ${
                    pipelineFilter === 'embedded'
                      ? 'border-primary bg-primary/5 ring-1 ring-primary'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  <span className="text-xs font-semibold">已嵌入</span>
                  <span className={`text-xs mt-1 px-2 py-0.5 rounded-full font-bold ${
                    pipelineFilter === 'embedded' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
                  }`}>
                    {documents.filter(d => d.processing_status === 'embedded').length}
                  </span>
                </button>
                <button
                  onClick={() => { setPipelineFilter('embedding_failed'); setCurrentPage(1) }}
                  className={`w-full mt-1 flex items-center justify-center gap-1 px-2 py-1 rounded-lg border transition-all text-xs ${
                    pipelineFilter === 'embedding_failed'
                      ? 'border-destructive bg-destructive/10 ring-1 ring-destructive'
                      : 'border-destructive/30 bg-destructive/5 hover:bg-destructive/10'
                  }`}
                >
                  <AlertCircle className="h-3 w-3 text-destructive" />
                  <span className="text-xs font-medium text-destructive">Embedding失败</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                    pipelineFilter === 'embedding_failed' ? 'bg-destructive/20 text-destructive' : 'bg-destructive/10 text-destructive'
                  }`}>
                    {documents.filter(d => d.processing_status === 'embedding_failed').length}
                  </span>
                </button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 工具栏 */}
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          {/* 搜索框 */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="搜索文档..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 w-48 sm:w-64"
            />
          </div>

          {/* 上传对话框 */}
          <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                <Plus className="h-4 w-4 mr-1.5" />
                上传文档
              </Button>
            </DialogTrigger>
              <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                  <DialogTitle>上传 PDF/DOCX 文档</DialogTitle>
                  <DialogDescription>
                    选择 PDF 或 DOCX 文件并填写文档信息（可选）
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label htmlFor="file">PDF/DOCX 文件</Label>
                    <Input
                      id="file"
                      type="file"
                      accept=".pdf,.docx"
                      onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                      disabled={uploading}
                    />
                    {selectedFile && (
                      <p className="text-sm text-muted-foreground">
                        已选择: {selectedFile.name} ({formatFileSize(selectedFile.size)})
                      </p>
                    )}
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="document_code">文档编号</Label>
                    <Input
                      id="document_code"
                      placeholder="例如: SGP-001"
                      value={uploadForm.document_code}
                      onChange={(e) => setUploadForm({ ...uploadForm, document_code: e.target.value })}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="title">文档标题</Label>
                    <Input
                      id="title"
                      placeholder="例如: Safety Requirements for..."
                      value={uploadForm.title}
                      onChange={(e) => setUploadForm({ ...uploadForm, title: e.target.value })}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="issuer">发布机构</Label>
                    <Input
                      id="issuer"
                      placeholder="例如: GSMA"
                      value={uploadForm.issuer}
                      onChange={(e) => setUploadForm({ ...uploadForm, issuer: e.target.value })}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="language">语言</Label>
                    <Select
                      value={uploadForm.language}
                      onValueChange={(value) => setUploadForm({ ...uploadForm, language: value })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="en">English</SelectItem>
                        <SelectItem value="zh-CN">简体中文</SelectItem>
                        <SelectItem value="zh-TW">繁体中文</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setUploadDialogOpen(false)} disabled={uploading}>
                    取消
                  </Button>
                  <Button onClick={handleUpload} disabled={uploading || !selectedFile}>
                    {uploading ? '上传中...' : '上传'}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {/* Parse All Dialog */}
            <Dialog open={parseAllDialogOpen} onOpenChange={setParseAllDialogOpen}>
                  <DialogTrigger asChild>
                    <Button
                      disabled={parsingAll || totalDocs === 0}
                      variant="default"
                      size="sm"
                      className="gap-1.5"
                    >
                      {parsingAll ? (
                        <>
                          <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                          解析中...
                        </>
                      ) : (
                        <>
                          <Play className="h-4 w-4" />
                          解析所有
                        </>
                      )}
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="sm:max-w-[500px]">
                    <DialogHeader>
                      <DialogTitle>批量解析文档</DialogTitle>
                      <DialogDescription>
                        配置批量解析参数，对所有已上传状态的文档进行解析
                      </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                      <div className="grid gap-2">
                        <Label htmlFor="parse-parallel">并行数量</Label>
                        <Input
                          id="parse-parallel"
                          type="number"
                          min={1}
                          max={10}
                          value={parseAllForm.parallel_count}
                          onChange={(e) => setParseAllForm({ ...parseAllForm, parallel_count: parseInt(e.target.value) || 1 })}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="parse-output-dir">输出目录</Label>
                        <Input
                          id="parse-output-dir"
                          value={parseAllForm.output_dir}
                          onChange={(e) => setParseAllForm({ ...parseAllForm, output_dir: e.target.value })}
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          id="parse-ocr"
                          type="checkbox"
                          checked={parseAllForm.do_ocr}
                          onChange={(e) => setParseAllForm({ ...parseAllForm, do_ocr: e.target.checked })}
                          className="h-4 w-4 rounded border-gray-300"
                        />
                        <Label htmlFor="parse-ocr">启用 OCR</Label>
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setParseAllDialogOpen(false)} disabled={parsingAll}>
                        取消
                      </Button>
                      <Button onClick={handleParseAll} disabled={parsingAll}>
                        {parsingAll ? '提交中...' : '确认提交'}
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>

                {/* VLM All Dialog */}
                <Dialog open={vlmAllDialogOpen} onOpenChange={setVlmAllDialogOpen}>
                  <DialogTrigger asChild>
                    <Button
                      disabled={vlmAll || totalDocs === 0}
                      variant="default"
                      size="sm"
                      className="gap-1.5"
                    >
                      {vlmAll ? (
                        <>
                          <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                          VLM处理中...
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-4 w-4" />
                          VLM增强所有
                        </>
                      )}
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="sm:max-w-[550px]">
                    <DialogHeader>
                      <DialogTitle>批量 VLM 增强</DialogTitle>
                      <DialogDescription>
                        配置 VLM 增强参数，对所有已解析状态的文档进行视觉语言模型增强
                      </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4 max-h-[60vh] overflow-y-auto">
                      <div className="grid gap-2">
                        <Label htmlFor="vlm-parallel">并行数量</Label>
                        <Input
                          id="vlm-parallel"
                          type="number"
                          min={1}
                          max={10}
                          value={vlmAllForm.parallel_count}
                          onChange={(e) => setVlmAllForm({ ...vlmAllForm, parallel_count: parseInt(e.target.value) || 1 })}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="vlm-backend">后端类型</Label>
                        <Select
                          value={vlmAllForm.backend_type}
                          onValueChange={(value) => setVlmAllForm({ ...vlmAllForm, backend_type: value })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="openai">OpenAI Compatible</SelectItem>
                            <SelectItem value="local">Local Qwen VLM</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="vlm-api-key">API Key（可选）</Label>
                        <Input
                          id="vlm-api-key"
                          type="password"
                          placeholder="留空使用环境变量 VLM_OPENAI_API_KEY"
                          value={vlmAllForm.api_key}
                          onChange={(e) => setVlmAllForm({ ...vlmAllForm, api_key: e.target.value })}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="vlm-base-url">Base URL（可选）</Label>
                        <Input
                          id="vlm-base-url"
                          placeholder="例如: https://dashscope.aliyuncs.com/compatible-mode/v1"
                          value={vlmAllForm.base_url}
                          onChange={(e) => setVlmAllForm({ ...vlmAllForm, base_url: e.target.value })}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="vlm-model">模型名称（可选）</Label>
                        <Input
                          id="vlm-model"
                          placeholder="留空使用默认模型"
                          value={vlmAllForm.model}
                          onChange={(e) => setVlmAllForm({ ...vlmAllForm, model: e.target.value })}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="vlm-prompt">提示词（可选）</Label>
                        <Textarea
                          id="vlm-prompt"
                          placeholder="留空使用默认提示词"
                          rows={3}
                          value={vlmAllForm.prompt}
                          onChange={(e) => setVlmAllForm({ ...vlmAllForm, prompt: e.target.value })}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="vlm-max-tokens">最大生成 Token 数</Label>
                        <Input
                          id="vlm-max-tokens"
                          type="number"
                          min={256}
                          step={256}
                          value={vlmAllForm.max_new_tokens}
                          onChange={(e) => setVlmAllForm({ ...vlmAllForm, max_new_tokens: parseInt(e.target.value) || 2048 })}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="vlm-language">输出语言</Label>
                        <Select
                          value={vlmAllForm.language}
                          onValueChange={(value) => setVlmAllForm({ ...vlmAllForm, language: value })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="en">English</SelectItem>
                            <SelectItem value="zh">中文</SelectItem>
                            <SelectItem value="ja">日本語</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="vlm-output-dir">输出目录</Label>
                        <Input
                          id="vlm-output-dir"
                          value={vlmAllForm.output_dir}
                          onChange={(e) => setVlmAllForm({ ...vlmAllForm, output_dir: e.target.value })}
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setVlmAllDialogOpen(false)} disabled={vlmAll}>
                        取消
                      </Button>
                      <Button onClick={handleVlmAll} disabled={vlmAll}>
                        {vlmAll ? '提交中...' : '确认提交'}
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
          </div>

          {/* 文档列表 */}
          <Card className="flex-1 min-h-0 overflow-hidden flex flex-col">
            <CardContent className="p-0 flex-1 overflow-auto min-h-0">
            {loading ? (
              <div className="text-center py-8 text-muted-foreground">
                加载中...
              </div>
            ) : documents.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {pipelineFilter ? '没有找到匹配的文档' : '暂无文档，请上传 PDF/DOCX 文件'}
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <Table className="text-sm">
                    <TableHeader>
                      <TableRow className="h-8">
                        <TableHead className="h-8 px-2 py-1">文档编号</TableHead>
                        <TableHead className="h-8 px-2 py-1">文件名</TableHead>
                        <TableHead className="hidden sm:table-cell h-8 px-2 py-1">系列 ID</TableHead>
                        <TableHead className="hidden sm:table-cell h-8 px-2 py-1">修订版本</TableHead>
                        <TableHead className="h-8 px-2 py-1">状态</TableHead>
                        <TableHead className="h-8 px-2 py-1">操作</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {documents.map((doc) => (
                        <TableRow key={doc.id} className="h-10">
                          <TableCell className="font-medium px-2 py-1">
                            {doc.document_code || '-'}
                          </TableCell>
                          <TableCell className="max-w-[200px] truncate px-2 py-1">
                            {doc.file_name}
                          </TableCell>
                          <TableCell className="hidden sm:table-cell px-2 py-1">
                            {doc.series_id || '-'}
                          </TableCell>
                          <TableCell className="hidden sm:table-cell px-2 py-1">
                            {doc.revision || '-'}
                          </TableCell>
                          <TableCell className="px-2 py-1">{getStatusBadge(doc.processing_status)}</TableCell>
                          <TableCell className="px-2 py-1">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="outline" size="sm">
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-40">
                                <DropdownMenuItem asChild>
                                  <Link href={`/docs/${doc.id}`}>
                                    <Eye className="h-4 w-4 mr-2" />
                                    查看
                                  </Link>
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleParse(doc)} disabled={processingDoc === doc.id}>
                                  <FileUp className="h-4 w-4 mr-2" />
                                  {processingDoc === doc.id && processingType === 'parse' ? '解析中...' : '解析'}
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleVLM(doc)} disabled={processingDoc === doc.id}>
                                  <Image className="h-4 w-4 mr-2" />
                                  {processingDoc === doc.id && processingType === 'vlm' ? 'VLM中...' : 'VLM 增强'}
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleChunk(doc)} disabled={processingDoc === doc.id}>
                                  <Layers className="h-4 w-4 mr-2" />
                                  {processingDoc === doc.id && processingType === 'chunk' ? '分块中...' : '分块'}
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleEmbedding(doc)} disabled={processingDoc === doc.id}>
                                  <Database className="h-4 w-4 mr-2" />
                                  {processingDoc === doc.id && processingType === 'embedding' ? 'Embedding中...' : 'Embedding'}
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                {/* 分页控件 */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between mt-4 pt-4 border-t">
                    <div className="text-sm text-muted-foreground">
                      第 {currentPage} / {totalPages} 页，共 {totalDocs} 条
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
              </>
            )}
            </CardContent>
          </Card>
        </div>
        </div>
      </main>
    </div>
  )
}
