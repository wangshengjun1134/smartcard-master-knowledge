"use client"

import { useEffect, useState } from 'react'
import { ChevronRight, ChevronDown, FileText, Folder } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getDocumentTree } from '@/lib/api'
import type { TreeNode } from '@/types'
import Link from 'next/link'

export function DocumentTree() {
  const [treeNodes, setTreeNodes] = useState<TreeNode[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set())

  useEffect(() => {
    loadTree()
  }, [])

  const loadTree = async () => {
    try {
      const result = await getDocumentTree()
      setTreeNodes(result.tree)
    } catch (error) {
      console.error('Failed to load document tree:', error)
    } finally {
      setLoading(false)
    }
  }

  const toggleDir = (dirId: string) => {
    setExpandedDirs(prev => {
      const next = new Set(prev)
      if (next.has(dirId)) {
        next.delete(dirId)
      } else {
        next.add(dirId)
      }
      return next
    })
  }

  // 统计文件总数
  const countFiles = (nodes: TreeNode[]): number => {
    let count = 0
    for (const node of nodes) {
      if (node.type === 'file') {
        count++
      } else if (node.children) {
        count += countFiles(node.children)
      }
    }
    return count
  }

  const totalFiles = countFiles(treeNodes)

  return (
    <div className="space-y-1">
      <div className="px-2 py-1.5 text-xs text-muted-foreground">
        {totalFiles} 个文件
      </div>
      {loading ? (
        <div className="px-2 py-4 text-sm text-muted-foreground text-center">
          加载中...
        </div>
      ) : (
        treeNodes.map((node) => (
          <TreeNodeItem
            key={node.id}
            node={node}
            expandedDirs={expandedDirs}
            onToggle={toggleDir}
          />
        ))
      )}
    </div>
  )
}

function TreeNodeItem({
  node,
  expandedDirs,
  onToggle,
}: {
  node: TreeNode
  expandedDirs: Set<string>
  onToggle: (dirId: string) => void
}) {
  const isExpanded = expandedDirs.has(node.id)

  if (node.type === 'directory' && node.children) {
    return (
      <div>
        <button
          onClick={() => onToggle(node.id)}
          className="flex items-center gap-2 w-full px-2 py-1.5 text-sm rounded-md hover:bg-accent hover:text-accent-foreground transition-colors"
        >
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          <Folder className="h-4 w-4 text-blue-500" />
          <span className="font-medium truncate">{node.label}</span>
          {node.count !== undefined && (
            <span className="ml-auto text-xs text-muted-foreground shrink-0">
              {node.count}
            </span>
          )}
        </button>
        {isExpanded && (
          <div className="ml-4 mt-0.5 space-y-0.5">
            {node.children.map((child) => (
              <TreeNodeItem
                key={child.id}
                node={child}
                expandedDirs={expandedDirs}
                onToggle={onToggle}
              />
            ))}
          </div>
        )}
      </div>
    )
  }

  if (node.type === 'file') {
    const hasDoc = !!node.document
    const status = node.document?.processing_status

    return (
      <Link
        href={hasDoc ? `/docs/${node.document!.id}` : '#'}
        className={cn(
          'flex items-center gap-2 w-full px-2 py-1.5 text-sm rounded-md transition-colors',
          hasDoc
            ? 'hover:bg-accent hover:text-accent-foreground cursor-pointer'
            : 'text-muted-foreground cursor-default'
        )}
        onClick={(e) => {
          if (!hasDoc) {
            e.preventDefault()
          }
        }}
      >
        <FileText className={cn(
          "h-4 w-4 shrink-0",
          hasDoc ? "text-muted-foreground" : "text-muted-foreground/50"
        )} />
        <span className="truncate">{node.label}</span>
        {hasDoc && status && (
          <span className={cn(
            "ml-auto text-xs shrink-0",
            status === 'completed' ? "text-green-500" :
            status === 'processing' ? "text-blue-500" :
            status === 'failed' ? "text-red-500" :
            "text-yellow-500"
          )}>
            {status === 'completed' ? '✓' :
             status === 'processing' ? '⋯' :
             status === 'failed' ? '✗' : '○'}
          </span>
        )}
      </Link>
    )
  }

  return null
}
