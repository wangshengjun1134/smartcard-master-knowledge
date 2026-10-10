'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { Loader2 } from 'lucide-react'

declare global {
  interface Window {
    pdfjsLib: any
  }
}

interface PdfViewerProps {
  documentId: string
  startPage: number
  documentName: string
}

export default function PdfViewer({ documentId, startPage, documentName }: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRefs = useRef<Map<number, HTMLCanvasElement | null>>(new Map())
  const [pdfLib, setPdfLib] = useState<any>(null)
  const [pdfDoc, setPdfDoc] = useState<any>(null)
  const [totalPages, setTotalPages] = useState(0)
  const [loadedEndPage, setLoadedEndPage] = useState(0)
  const [rendering, setRendering] = useState<Set<number>>(new Set())
  const [error, setError] = useState<string | null>(null)

  // Load pdf.js from CDN
  useEffect(() => {
    if (window.pdfjsLib) {
      setPdfLib(window.pdfjsLib)
      return
    }

    const script = document.createElement('script')
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.min.mjs'
    script.type = 'module'
    script.onload = () => {
      setPdfLib(window.pdfjsLib)
    }
    script.onerror = () => setError('Failed to load PDF viewer library')
    document.head.appendChild(script)
  }, [])

  // Load PDF document
  const loadDocument = useCallback(async (lib: any) => {
    try {
      lib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.worker.min.mjs'

      // Fetch PDF blob
      const response = await fetch(`/api/docs/${documentId}/file`)
      if (!response.ok) throw new Error('Failed to fetch PDF')
      const blob = await response.blob()
      const arrayBuffer = await blob.arrayBuffer()

      const doc = await lib.getDocument({ data: arrayBuffer }).promise
      setPdfDoc(doc)
      setTotalPages(doc.numPages)

      // Calculate initial page range
      const initialStart = Math.max(1, startPage - 2)
      const initialEnd = Math.min(doc.numPages, startPage + 2)
      setLoadedEndPage(initialEnd)
    } catch (err: any) {
      setError(err.message || 'Failed to load PDF')
    }
  }, [documentId, startPage])

  useEffect(() => {
    if (pdfLib && !pdfDoc) {
      loadDocument(pdfLib)
    }
  }, [pdfLib, pdfDoc, loadDocument])

  // Render a single page
  const renderPage = async (pageNum: number) => {
    if (!pdfDoc || !pdfLib) return
    if (canvasRefs.current.has(pageNum)) return // Already rendered

    try {
      setRendering(prev => new Set(prev).add(pageNum))
      const page = await pdfDoc.getPage(pageNum)
      const canvas = canvasRefs.current.get(pageNum)
      if (!canvas) return

      const container = containerRef.current
      const containerWidth = container ? container.clientWidth - 32 : 800
      const viewport = page.getViewport({ scale: 1 })
      const scale = containerWidth / viewport.width
      const scaledViewport = page.getViewport({ scale })

      canvas.width = scaledViewport.width
      canvas.height = scaledViewport.height
      canvas.style.maxWidth = '100%'
      canvas.style.height = 'auto'
      canvas.style.display = 'block'
      canvas.style.margin = '0 auto 16px'

      const ctx = canvas.getContext('2d')
      if (ctx) {
        await page.render({ canvasContext: ctx, viewport: scaledViewport }).promise
      }
      setRendering(prev => {
        const next = new Set(prev)
        next.delete(pageNum)
        return next
      })
    } catch (err) {
      console.error(`Failed to render page ${pageNum}:`, err)
      setRendering(prev => {
        const next = new Set(prev)
        next.delete(pageNum)
        return next
      })
    }
  }

  // Render pages in range
  useEffect(() => {
    if (!pdfDoc || !loadedEndPage) return
    const pagesToRender: number[] = []
    for (let i = 1; i <= loadedEndPage; i++) {
      if (!canvasRefs.current.has(i)) {
        pagesToRender.push(i)
      }
    }
    pagesToRender.forEach(pageNum => renderPage(pageNum))
  }, [pdfDoc, loadedEndPage])

  // Handle scroll - load more pages
  const handleScroll = useCallback(() => {
    const container = containerRef.current
    if (!container || !totalPages) return

    const { scrollTop, scrollHeight, clientHeight } = container
    // Load more when scrolled to 80% of the way down
    if (scrollTop + clientHeight >= scrollHeight * 0.8 && loadedEndPage < totalPages) {
      const newEnd = Math.min(totalPages, loadedEndPage + 2)
      if (newEnd > loadedEndPage) {
        setLoadedEndPage(newEnd)
      }
    }
  }, [totalPages, loadedEndPage])

  if (error) {
    return (
      <div className="text-center py-8 text-destructive">
        <p>{error}</p>
      </div>
    )
  }

  if (!pdfDoc) {
    return (
      <div className="text-center py-8">
        <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">加载 PDF 中...</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="text-xs text-muted-foreground mb-2">
        共 {totalPages} 页，已加载 1-{loadedEndPage} 页
      </div>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 py-2"
        style={{ maxHeight: '70vh' }}
      >
        {Array.from({ length: loadedEndPage }, (_, i) => i + 1).map(pageNum => (
          <div key={pageNum} className="mb-4">
            <canvas
              ref={el => { canvasRefs.current.set(pageNum, el) }}
              className="border rounded shadow-sm"
            />
            {rendering.has(pageNum) && (
              <div className="text-center text-xs text-muted-foreground mt-1">
                <Loader2 className="h-3 w-3 animate-spin inline mr-1" />
                渲染中...
              </div>
            )}
          </div>
        ))}
        {loadedEndPage < totalPages && (
          <div className="text-center py-4">
            <Loader2 className="h-4 w-4 animate-spin inline mr-1 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">向下滚动加载更多页面...</span>
          </div>
        )}
      </div>
    </div>
  )
}
