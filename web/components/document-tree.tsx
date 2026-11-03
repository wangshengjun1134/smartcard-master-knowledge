"use client"

import { useEffect, useState } from 'react'
import { ChevronRight, ChevronDown, Folder } from 'lucide-react'
import { getDirectoryTree } from '@/lib/api'
import type { DirectoryTreeNode } from '@/lib/api'

export function DocumentTree() {
  const [treeNodes, setTreeNodes] = useState<DirectoryTreeNode[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedDirs, setExpandedDirs] = useState<Set<number>>(new Set())

  useEffect(() => {
    loadTree()
  }, [])

  const loadTree = async () => {
    try {
      const result = await getDirectoryTree()
      setTreeNodes(result)
    } catch (error) {
      console.error('Failed to load directory tree:', error)
    } finally {
      setLoading(false)
    }
  }

  const toggleDir = (dirId: number) => {
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

  const countNodes = (nodes: DirectoryTreeNode[]): number => {
    let count = 0
    for (const node of nodes) {
      count++
      if (node.children) {
        count += countNodes(node.children)
      }
    }
    return count
  }

  const totalDirs = countNodes(treeNodes)

  return (
    <div className="space-y-1">
      <div className="px-2 py-1.5 text-xs text-muted-foreground">
        {totalDirs} 个目录
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
  node: DirectoryTreeNode
  expandedDirs: Set<number>
  onToggle: (dirId: number) => void
}) {
  const isExpanded = expandedDirs.has(node.id)
  const hasChildren = node.children && node.children.length > 0

  return (
    <div>
      <button
        onClick={() => hasChildren && onToggle(node.id)}
        className={`flex items-center gap-2 w-full px-2 py-1.5 text-sm rounded-md transition-colors ${
          hasChildren ? 'hover:bg-accent hover:text-accent-foreground cursor-pointer' : 'cursor-default'
        }`}
      >
        {hasChildren ? (
          isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )
        ) : (
          <span className="w-4" />
        )}
        <Folder className="h-4 w-4 text-blue-500" />
        <span className="font-medium truncate">{node.name}</span>
        {hasChildren && (
          <span className="ml-auto text-xs text-muted-foreground shrink-0">
            {node.children.length}
          </span>
        )}
      </button>
      {isExpanded && hasChildren && (
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
