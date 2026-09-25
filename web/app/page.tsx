'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { listDocuments, uploadDocument } from '@/lib/api'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useToast } from '@/hooks/use-toast'
import { formatFileSize, formatDate } from '@/lib/utils'
import { Upload, FileText, Search, Moon, Sun, Plus } from 'lucide-react'
import { useTheme } from 'next-themes'

export default function Home() {
  const { toast } = useToast()
  const { theme, setTheme } = useTheme()
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterStatus, setFilterStatus] = useState<string>('')
  const [uploading, setUploading] = useState(false)
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const [uploadForm, setUploadForm] = useState({
    document_code: '',
    title: '',
    issuer: '',
    language: 'en',
  })

  useEffect(() => {
    loadDocuments()
  }, [])

  const loadDocuments = async () => {
    try {
      const docs = await listDocuments()
      setDocuments(docs)
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

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('document_code', uploadForm.document_code)
      formData.append('title', uploadForm.title)
      formData.append('issuer', uploadForm.issuer)
      formData.append('language', uploadForm.language)

      await uploadDocument(formData)
      toast({
        title: '上传成功',
        description: `${file.name} 已上传并开始解析`,
      })
      await loadDocuments()
      setUploadDialogOpen(false)
      setUploadForm({ document_code: '', title: '', issuer: '', language: 'en' })
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

  const filteredDocuments = documents.filter(doc => {
    const matchesSearch =
      doc.file_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      doc.document_code?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      doc.title?.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesStatus = !filterStatus || doc.processing_status === filterStatus
    return matchesSearch && matchesStatus
  })

  const getStatusBadge = (status?: string) => {
    const statusMap: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
      pending: { label: '等待处理', variant: 'secondary' },
      processing: { label: '处理中', variant: 'default' },
      completed: { label: '已完成', variant: 'default' },
      failed: { label: '失败', variant: 'destructive' },
    }
    const config = statusMap[status || 'pending'] || { label: status, variant: 'outline' as const }
    return <Badge variant={config.variant}>{config.label}</Badge>
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
      <main className="container mx-auto px-4 py-8">
        {/* 页面标题和操作区 */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-2xl font-bold">文档管理</h2>
            <p className="text-muted-foreground">
              管理所有智能卡标准规范文档
            </p>
          </div>
          <div className="flex items-center gap-4 flex-wrap">
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

            {/* 状态过滤 */}
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="所有状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">所有状态</SelectItem>
                <SelectItem value="pending">等待处理</SelectItem>
                <SelectItem value="processing">处理中</SelectItem>
                <SelectItem value="completed">已完成</SelectItem>
                <SelectItem value="failed">失败</SelectItem>
              </SelectContent>
            </Select>

            {/* 上传对话框 */}
            <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  上传 PDF
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                  <DialogTitle>上传 PDF 文档</DialogTitle>
                  <DialogDescription>
                    选择 PDF 文件并填写文档信息（可选）
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label htmlFor="file">PDF 文件</Label>
                    <Input
                      id="file"
                      type="file"
                      accept=".pdf"
                      onChange={handleUpload}
                      disabled={uploading}
                    />
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
                  <Button variant="outline" onClick={() => setUploadDialogOpen(false)}>
                    取消
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>总文档数</CardDescription>
              <CardTitle className="text-3xl">{documents.length}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>已完成</CardDescription>
              <CardTitle className="text-3xl">
                {documents.filter(d => d.processing_status === 'completed').length}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>处理中</CardDescription>
              <CardTitle className="text-3xl">
                {documents.filter(d => d.processing_status === 'processing').length}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>总 Item 数</CardDescription>
              <CardTitle className="text-3xl">
                {documents.reduce((sum, d) => sum + d.item_count, 0)}
              </CardTitle>
            </CardHeader>
          </Card>
        </div>

        {/* 文档列表 */}
        <Card>
          <CardHeader>
            <CardTitle>文档列表</CardTitle>
            <CardDescription>
              共 {filteredDocuments.length} 个文档
              {filterStatus && ` (过滤: ${filterStatus})`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-center py-8 text-muted-foreground">
                加载中...
              </div>
            ) : filteredDocuments.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {searchTerm || filterStatus ? '没有找到匹配的文档' : '暂无文档，请上传 PDF 文件'}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>文档编号</TableHead>
                      <TableHead>文件名</TableHead>
                      <TableHead className="hidden md:table-cell">标题</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead className="hidden sm:table-cell">Item 数</TableHead>
                      <TableHead className="hidden lg:table-cell">文件大小</TableHead>
                      <TableHead className="hidden lg:table-cell">创建时间</TableHead>
                      <TableHead>操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredDocuments.map((doc) => (
                      <TableRow key={doc.id}>
                        <TableCell className="font-medium">
                          {doc.document_code || '-'}
                        </TableCell>
                        <TableCell className="max-w-[200px] truncate">
                          {doc.file_name}
                        </TableCell>
                        <TableCell className="hidden md:table-cell max-w-xs truncate">
                          {doc.title || '-'}
                        </TableCell>
                        <TableCell>{getStatusBadge(doc.processing_status)}</TableCell>
                        <TableCell className="hidden sm:table-cell">{doc.item_count}</TableCell>
                        <TableCell className="hidden lg:table-cell">
                          {doc.file_size ? formatFileSize(doc.file_size) : '-'}
                        </TableCell>
                        <TableCell className="hidden lg:table-cell">
                          {doc.created_at ? formatDate(doc.created_at) : '-'}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Link href={`/docs/${doc.id}`}>
                              <Button variant="outline" size="sm">
                                查看
                              </Button>
                            </Link>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
