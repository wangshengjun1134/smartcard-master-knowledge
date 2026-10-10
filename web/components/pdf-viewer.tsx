'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { Loader2 } from 'lucide-react'

interface PdfViewerProps {
  documentId: string
  startPage: number
  documentName: string
}

export default function PdfViewer({ documentId, startPage }: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasContainerRef = useRef<HTMLDivElement>(null)
  const [totalPages, setTotalPages] = useState(0)
  const [loadedEndPage, setLoadedEndPage] = useState(0)
  const [rendering, setRendering] = useState<Set<number>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const pdfDocRef = useRef<any>(null)
  const isRenderingRef = useRef(false)

  // Load pdf.js and PDF document
  useEffect(() => {
    let cancelled = false

    const init = async () => {
      try {
        // Dynamically import pdf.js only on client side
        const pdfjsLib = await import('pdfjs-dist')

        // Use worker served from /public (copied from pdfjs-dist package)
        pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'

        // Fetch PDF blob
        const response = await fetch(`/api/docs/${documentId}/file`)
        if (!response.ok) throw new Error(`Failed to fetch PDF: ${response.status}`)
        const blob = await response.blob()
        const arrayBuffer = await blob.arrayBuffer()

        const doc = await pdfjsLib.getDocument({ data: arrayBuffer }).promise
        if (cancelled) return

        pdfDocRef.current = doc
        setTotalPages(doc.numPages)

        // Initial: load startPage ± 1
        const initialEnd = Math.min(doc.numPages, startPage + 1)
        setLoadedEndPage(initialEnd)
      } catch (err: any) {
        console.error('PDF init error:', err)
        if (!cancelled) {
          setError(err.message || 'Failed to load PDF')
        }
      }
    }

    init()

    return () => { cancelled = true }
  }, [documentId, startPage])

  // Render a single page
  const renderPage = useCallback(async (pageNum: number) => {
    if (!pdfDocRef.current) return

    try {
      setRendering(prev => new Set(prev).add(pageNum))
      const page = await pdfDocRef.current.getPage(pageNum)

      const container = canvasContainerRef.current
      if (!container) return

      // Find the canvas for this page
      const canvas = container.querySelector(`canvas[data-page="${pageNum}"]`) as HTMLCanvasElement
      if (!canvas) return

      const containerWidth = container.clientWidth - 32
      const viewport = page.getViewport({ scale: 1 })
      const scale = Math.min(containerWidth / viewport.width, 2) // max 2x scale
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

  // Render pages when loadedEndPage changes
  useEffect(() => {
    if (!loadedEndPage || !pdfDocRef.current || isRenderingRef.current) return

    isRenderingRef.current = true
    const pagesToRender: number[] = []
    for (let i = 1; i <= loadedEndPage; i++) {
      const canvas = canvasContainerRef.current?.querySelector(`canvas[data-page="${i}"]`) as HTMLCanvasElement | null
      if (!canvas || !canvas.width) {
        pagesToRender.push(i)
      }
    }

    // Render sequentially to avoid overwhelming CPU
    let idx = 0
    const renderNext = async () => {
      if (idx >= pagesToRender.length) {
        isRenderingRef.current = false
        return
      }
      await renderPage(pagesToRender[idx])
      idx++
      // Small delay between pages to keep UI responsive
      setTimeout(renderNext, 100)
    }
    renderNext()
  }, [loadedEndPage, renderPage])

  // Handle scroll - load more pages
  const handleScroll = useCallback(() => {
    const container = containerRef.current
    if (!container || !totalPages) return

    const { scrollTop, scrollHeight, clientHeight } = container
    if (scrollTop + clientHeight >= scrollHeight * 0.75 && loadedEndPage < totalPages) {
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
      <div className="text-xs text-muted-foreground mb-2 flex items-center justify-between">
        <span>共 {totalPages} 页，已加载 1-{loadedEndPage} 页</span>
        <span className="text-[10px] text-muted-foreground/60">向下滚动加载更多</span>
      </div>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto"
        style={{ maxHeight: '70vh' }}
      >
        <div ref={canvasContainerRef} className="px-4 py-2">
          {/* Render canvas placeholders for all loaded pages */}
          {Array.from({ length: loadedEndPage }, (_, i) => i + 1).map(pageNum => (
            <div key={pageNum} className="mb-4 relative">
              <canvas
                data-page={pageNum}
                className="border rounded shadow-sm"
              />
              {rendering.has(pageNum) && (
                <div className="absolute inset-0 flex items-center justify-center bg-background/80 rounded">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              )}
            </div>
          ))}
          {loadedEndPage < totalPages && (
            <div className="text-center py-6">
              <Loader2 className="h-4 w-4 animate-spin inline mr-1 text-muted-foreground" />
              <span className="text-xs text-muted-foreground">加载中...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
