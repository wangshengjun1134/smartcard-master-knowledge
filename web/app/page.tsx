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
import { formatFileSize, formatDate } from '@/lib/utils'
import { Upload, FileText, Search, Plus } from 'lucide-react'

export default function Home() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    loadDocuments()
  }, [])

  const loadDocuments = async () => {
    try {
      const docs = await listDocuments()
      setDocuments(docs)
    } catch (error) {
      console.error('Failed to load documents:', error)
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

      await uploadDocument(formData)
      await loadDocuments()
    } catch (error) {
      console.error('Failed to upload document:', error)
      alert('上传失败，请重试')
    } finally {
      setUploading(false)
    }
  }

  const filteredDocuments = documents.filter(doc =>
    doc.file_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    doc.document_code?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    doc.title?.toLowerCase().includes(searchTerm.toLowerCase())
  )

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
          <nav className="flex items-center gap-4">
            <Link href="/" className="text-sm font-medium hover:underline">
              文档管理
            </Link>
          </nav>
        </div>
      </header>

      {/* 主内容 */}
      <main className="container mx-auto px-4 py-8">
        {/* 页面标题和操作区 */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold">文档管理</h2>
            <p className="text-muted-foreground">
              管理所有智能卡标准规范文档
            </p>
          </div>
          <div className="flex items-center gap-4">
            {/* 搜索框 */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="搜索文档..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 w-64"
              />
            </div>

            {/* 上传按钮 */}
            <label className="inline-flex items-center gap-2">
              <Button variant="default" disabled={uploading}>
                <Upload className="h-4 w-4" />
                {uploading ? '上传中...' : '上传 PDF'}
              </Button>
              <input
                type="file"
                accept=".pdf"
                onChange={handleUpload}
                className="hidden"
                disabled={uploading}
              />
            </label>
          </div>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
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
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-center py-8 text-muted-foreground">
                加载中...
              </div>
            ) : filteredDocuments.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {searchTerm ? '没有找到匹配的文档' : '暂无文档，请上传 PDF 文件'}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>文档编号</TableHead>
                    <TableHead>文件名</TableHead>
                    <TableHead>标题</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>Item 数</TableHead>
                    <TableHead>文件大小</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredDocuments.map((doc) => (
                    <TableRow key={doc.id}>
                      <TableCell className="font-medium">
                        {doc.document_code || '-'}
                      </TableCell>
                      <TableCell>{doc.file_name}</TableCell>
                      <TableCell className="max-w-xs truncate">
                        {doc.title || '-'}
                      </TableCell>
                      <TableCell>{getStatusBadge(doc.processing_status)}</TableCell>
                      <TableCell>{doc.item_count}</TableCell>
                      <TableCell>
                        {doc.file_size ? formatFileSize(doc.file_size) : '-'}
                      </TableCell>
                      <TableCell>
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
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
