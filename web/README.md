# SmartCard Knowledge Base Web

基于 Next.js + shadcn/ui 的文档管理前端界面。

## 技术栈

- **框架**: Next.js 14 (App Router)
- **样式**: Tailwind CSS
- **UI 组件**: shadcn/ui (Radix UI)
- **HTTP 客户端**: Axios
- **语言**: TypeScript

## 快速开始

### 安装依赖

```bash
cd web
npm install
```

### 开发环境

```bash
# 复制环境变量
cp .env.example .env.local

# 启动开发服务器
npm run dev
```

访问 http://localhost:3000

### 生产构建

```bash
npm run build
npm start
```

## 项目结构

```
web/
├── app/                    # Next.js App Router
│   ├── layout.tsx          # 根布局
│   ├── page.tsx            # 首页（文档列表）
│   ├── globals.css         # 全局样式
│   └── docs/[id]/
│       └── page.tsx        # 文档详情页
├── components/
│   └── ui/                 # shadcn/ui 组件
│       ├── button.tsx
│       ├── card.tsx
│       ├── badge.tsx
│       ├── table.tsx
│       ├── input.tsx
│       └── tabs.tsx
├── lib/
│   ├── api.ts              # API 客户端
│   └── utils.ts            # 工具函数
├── types/
│   └── index.ts            # TypeScript 类型定义
├── public/                 # 静态资源
├── components.json         # shadcn/ui 配置
├── tailwind.config.js      # Tailwind 配置
├── tsconfig.json           # TypeScript 配置
└── next.config.js          # Next.js 配置
```

## API 接口

前端通过 API 代理与后端通信：

| 路径前缀 | 目标 |
|---------|------|
| `/api/*` | `http://localhost:8000/api/*` |

## 功能页面

### 1. 文档列表页 (`/`)
- 文档列表展示
- 搜索过滤
- PDF 上传
- 统计信息展示

### 2. 文档详情页 (`/docs/[id]`)
- 文档基本信息
- Item 列表（支持按类型过滤）
- 批量文本化操作
- 统计卡片

## 添加新组件

使用 shadcn CLI 添加新组件：

```bash
npx shadcn@latest add <component-name>
```

例如：
```bash
npx shadcn@latest add dialog
npx shadcn@latest add select
npx shadcn@latest add toast
```
