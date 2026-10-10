'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { Loader2 } from 'lucide-react'

interface PdfViewerProps {
  documentId: string
  startPage: number
  documentName: string
}

export default function PdfViewer({ documentId, startPage, documentName }: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRefs = useRef<Map<number, HTMLCanvasElement | null>>(new Map())
  const [totalPages, setTotalPages] = useState(0)
  const [loadedEndPage, setLoadedEndPage] = useState(0)
  const [rendering, setRendering] = useState<Set<number>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const pdfDocRef = useRef<any>(null)

  // Load pdf.js v3.x from CDN (better compatibility)
  useEffect(() => {
    const loadPdfJs = () => {
      return new Promise<void>((resolve, reject) => {
        if ((window as any).pdfjsLib) {
          resolve()
          return
        }
        const link = document.createElement('link')
        link.rel = 'stylesheet'
        link.href = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf_viewer.min.css'
        document.head.appendChild(link)

        const script = document.createElement('script')
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js'
        script.onload = () => resolve()
        script.onerror = () => reject(new Error('Failed to load pdf.js'))
        document.head.appendChild(script)
      })
    }

    loadPdfJs().then(async () => {
      try {
        const pdfjsLib = (window as any).pdfjsLib
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js'

        // Get total pages first
        const countResp = await fetch(`/api/docs/${documentId}/page-count`)
        if (!countResp.ok) throw new Error('Failed to get page count')
        const countData = await countResp.json()
        setTotalPages(countData.total_pages)

        // Fetch PDF blob
        const response = await fetch(`/api/docs/${documentId}/file`)
        if (!response.ok) throw new Error(`Failed to fetch PDF: ${response.status}`)
        const blob = await response.blob()
        const arrayBuffer = await blob.arrayBuffer()

        const doc = await pdfjsLib.getDocument({ data: arrayBuffer }).promise
        pdfDocRef.current = doc
        setTotalPages(doc.numPages)

        // Initial: load startPage ± 1
        const initialEnd = Math.min(doc.numPages, startPage + 1)
        setLoadedEndPage(initialEnd)
      } catch (err: any) {
        console.error('PDF load error:', err)
        setError(err.message || 'Failed to load PDF')
      }
    }).catch((err) => {
      setError(err.message || 'Failed to load PDF library')
    })
  }, [documentId, startPage])

  // Render a single page
  const renderPage = useCallback(async (pageNum: number) => {
    if (!pdfDocRef.current) return
    if (canvasRefs.current.has(pageNum)) return

    try {
      setRendering(prev => new Set(prev).add(pageNum))
      const page = await pdfDocRef.current.getPage(pageNum)
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
  }, [])

  // Render pages in range
  useEffect(() => {
    if (!loadedEndPage) return
    const pagesToRender: number[] = []
    for (let i = 1; i <= loadedEndPage; i++) {
      if (!canvasRefs.current.has(i)) {
        pagesToRender.push(i)
      }
    }
    pagesToRender.forEach(pageNum => renderPage(pageNum))
  }, [loadedEndPage, renderPage])

  // Handle scroll - load more pages
  const handleScroll = useCallback(() => {
    const container = containerRef.current
    if (!container || !totalPages) return

    const { scrollTop, scrollHeight, clientHeight } = container
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

  if (!pdfDocRef.current) {
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
