"use client"

import { useState } from 'react'
import { ChevronRight, ChevronDown, FileText, Folder, Hash } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { DocumentInfo } from '@/types'

interface TreeNode {
  id: string
  label: string
  type: 'series' | 'document'
  children?: TreeNode[]
  document?: DocumentInfo
  count?: number
}

interface DocumentTreeProps {
  documents: DocumentInfo[]
  selectedId?: string
  onSelect?: (doc: DocumentInfo) => void
}

export function DocumentTree({ documents, selectedId, onSelect }: DocumentTreeProps) {
  // 构建树形结构
  const treeNodes = buildTree(documents)

  return (
    <div className="space-y-1">
      {treeNodes.map((node) => (
        <TreeNodeItem
          key={node.id}
          node={node}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}

function buildTree(documents: DocumentInfo[]): TreeNode[] {
  // 按 series_id 分组
  const seriesMap = new Map<string, DocumentInfo[]>()

  documents.forEach((doc) => {
    const series = doc.series_id || 'uncategorized'
    const docs = seriesMap.get(series) || []
    docs.push(doc)
    seriesMap.set(series, docs)
  })

  const nodes: TreeNode[] = []

  seriesMap.forEach((docs, seriesId) => {
    if (seriesId === 'uncategorized') {
      // 没有 series_id 的文档直接作为节点
      docs.forEach((doc) => {
        nodes.push({
          id: doc.id,
          label: doc.document_code || doc.file_name,
          type: 'document',
          document: doc,
        })
      })
    } else {
      nodes.push({
        id: seriesId,
        label: seriesId,
        type: 'series',
        count: docs.length,
        children: docs.map((doc) => ({
          id: doc.id,
          label: doc.document_code || doc.file_name,
          type: 'document',
          document: doc,
        })),
      })
    }
  })

  return nodes
}

function TreeNodeItem({
  node,
  selectedId,
  onSelect,
}: {
  node: TreeNode
  selectedId?: string
  onSelect?: (doc: DocumentInfo) => void
}) {
  const [expanded, setExpanded] = useState(node.type === 'series')

  if (node.type === 'series' && node.children) {
    return (
      <div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 w-full px-2 py-1.5 text-sm rounded-md hover:bg-accent hover:text-accent-foreground transition-colors"
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          <Folder className="h-4 w-4 text-blue-500" />
          <span className="font-medium">{node.label}</span>
          {node.count !== undefined && (
            <span className="ml-auto text-xs text-muted-foreground">
              {node.count}
            </span>
          )}
        </button>
        {expanded && (
          <div className="ml-4 mt-1 space-y-1">
            {node.children.map((child) => (
              <TreeNodeItem
                key={child.id}
                node={child}
                selectedId={selectedId}
                onSelect={onSelect}
              />
            ))}
          </div>
        )}
      </div>
    )
  }

  if (node.type === 'document' && node.document) {
    const isSelected = selectedId === node.id

    return (
      <button
        onClick={() => onSelect?.(node.document!)}
        className={cn(
          'flex items-center gap-2 w-full px-2 py-1.5 text-sm rounded-md transition-colors',
          isSelected
            ? 'bg-accent text-accent-foreground'
            : 'hover:bg-accent hover:text-accent-foreground'
        )}
      >
        <FileText className="h-4 w-4 text-muted-foreground" />
        <span className="truncate">{node.label}</span>
      </button>
    )
  }

  return null
}
