# Mini Claude Code — Python 版

> 📖 完整教程文档见 [claude-code-from-scratch](https://github.com/Windy3f3f3f3f/claude-code-from-scratch)

## 快速开始

```bash
pip install -e .
```
## 设置 API Key
支持两种后端，通过环境变量自动识别：（支持自定义base url）

**方式一：Anthropic 格式（推荐）**

```bash
export ANTHROPIC_API_KEY="sk-ant-xxx"
# 可选：使用代理
export ANTHROPIC_BASE_URL="https://aihubmix.com"
```

**方式二：OpenAI 兼容格式**

```bash
export OPENAI_API_KEY="sk-xxx"
export OPENAI_BASE_URL="https://api.openai.com/v1"
```

默认模型为 `claude-opus-4-6`，可通过环境变量或命令行参数自定义：

```bash
export MINI_CLAUDE_MODEL="claude-sonnet-4-6"    # 环境变量方式
npm start -- --model gpt-4o                      # 命令行方式（优先级更高）
```
## 运行
```bash
mini-claude-py               # 交互式 REPL 模式（推荐）
mini-claude-py --resume      # 恢复上次会话继续对话
mini-claude-py --yolo        # 跳过安全确认
mini-claude-py --plan        # Plan 模式：只分析不修改
mini-claude-py --accept-edits # 自动批准文件编辑
mini-claude-py --dont-ask    # CI 模式：需确认的操作自动拒绝
mini-claude-py --max-cost 0.50 # 费用限制（美元）
mini-claude-py --max-turns 20  # 轮次限制
```

## 使用 OpenAI 兼容后端
```bash
OPENAI_API_KEY=sk-xxx mini-claude-py --api-base https://api.openai.com/v1 --model gpt-4o "hello"
```

## REPL 命令

| 命令 | 功能 |
|------|------|
| `/clear` | 清空对话历史 |
| `/cost` | 显示累计 token 用量和费用估算 |
| `/compact` | 手动触发对话压缩 |
| `/memory` | 列出所有已保存的记忆 |
| `/skills` | 列出可用的技能 |
| `/<skill>` | 调用已注册的技能（如 `/commit`） |

> 详见 [CLI 与会话](https://windy3f3f3f3f.github.io/claude-code-from-scratch/#/docs/04-cli-session) 和 [功能测试](https://windy3f3f3f3f.github.io/claude-code-from-scratch/#/docs/14-testing)

## ⚖️ 与 Claude Code 的对比

| 维度 | Claude Code | Mini Claude Code |
|------|------------|-----------------|
| 定位 | 生产级编程智能体 | 教学 / 最小可用实现 |
| 工具数量 | 66+ 内置工具 | 13 个工具（6 核心 + web_fetch + tool_search + skill + agent + plan mode） |
| 工具执行 | 并发 + streaming 早期启动 | 并行执行 + streaming 早期启动 |
| 上下文管理 | 4 级压缩流水线 | 4 层压缩 + 大结果持久化（>30KB） |
| 权限系统 | 7 层 + AST 分析 | 5 种模式 + 声明式规则 + 正则检测 |
| 编辑验证 | 14 步流水线 | 引号容错 + 唯一性 + mtime 防护 + diff 输出 |
| 记忆系统 | 4 类型 + 语义召回 | 4 类型 + 语义召回 + 异步预取 |
| 技能系统 | 6 源 + inline/fork | 2 源 + inline/fork |
| 多 Agent | Sub-Agent + Coordinator + Swarm | Sub-Agent（3 内置 + 自定义 Agent） |
| MCP 集成 | mcpClient.ts + 动态工具发现 | McpManager + JSON-RPC over stdio |
| 预算控制 | USD/轮次/abort 三维 | USD + 轮次限制 |
| 代码量 | 50 万+ 行 | ~4300 行（TS）/ ~3800 行（Python） |

## ⚡ 核心能力

- **Agent 循环**：自动调用工具、处理结果、持续迭代，直到任务完成
- **13 个工具**：读写编辑文件（mtime 防护）、搜索、Shell、WebFetch、ToolSearch（延迟加载）、技能、子 Agent、Plan Mode
- **流式输出**：逐字实时显示，Anthropic + OpenAI 双后端，streaming 工具早期执行
- **并行工具执行**：只读工具（read_file、grep_search 等）自动并发，2-3x 加速
- **4 层上下文压缩**：budget 截断 → stale snip → microcompact → auto-compact + 大结果持久化（>30KB 写磁盘）
- **权限系统**：5 种模式 + `.claude/settings.json` 声明式 allow/deny 规则 + 16 个危险命令正则
- **记忆系统**：4 类型记忆 + 语义召回（sideQuery 调模型选择相关记忆）+ 异步预取
- **技能系统**：`.claude/skills/` 目录加载，支持 inline 注入和 fork 子 Agent 两种执行模式
- **多 Agent**：Sub-Agent fork-return 模式（3 内置类型 + `.claude/agents/` 自定义类型）
- **MCP 集成**：JSON-RPC over stdio 连接外部工具服务器，动态工具发现与调用转发
- **System Prompt**：@include 语法递归引入、.claude/rules/ 自动加载、模板变量替换
- **Extended Thinking**：支持 Anthropic 扩展思考（`--thinking`），adaptive/enabled/disabled 三模式
- **预算控制**：`--max-cost` 费用限制 + `--max-turns` 轮次限制，超限自动停止
- **会话持久化**：自动保存对话，`--resume` 恢复上次会话
- **跨平台**：Windows / macOS / Linux，自动检测 shell（PowerShell / bash / zsh）
- **错误恢复**：API 限流/过载时指数退避 + 随机抖动重试（最多 3 次），Ctrl+C 优雅中断

## 🏗️ 架构图

```
用户输入
  │
  ▼
┌─────────────────────────────────────┐
│          Agent Loop                 │
│                                     │
│  消息历史 → API (流式) → 实时输出   │
│       ▲                   │         │
│       │              ┌────┴───┐     │
│       │              │文本输出│     │
│       │              │工具调用│     │
│       │              └────┬───┘     │
│       │                   │         │
│       │   ┌───────┐ ┌────▼───┐     │
│       │   │截断保护│←│工具执行│     │
│       │   └───────┘ └────┬───┘     │
│       │                   │         │
│       │   ┌───────────────▼───┐     │
│       └───│Token 追踪 + 压缩 │     │
│           └───────────────────┘     │
└─────────────────────────────────────┘
  │
  ▼
任务完成 → 自动保存会话
```

## 🔗 相关项目

- **[how-claude-code-works](https://github.com/Windy3f3f3f3f/how-claude-code-works)** — Claude Code 源码架构深度解析（12 篇专题，33 万字）

## demo
<div align="center">
  <video src="https://github.com/user-attachments/assets/4f6597e2-6ea3-45ae-8a6b-77662c4e9540" width="100%" autoplay loop muted playsinline></video>
</div>

## 🙏 致谢

感谢作者[Windy3f3f3f3f](https://github.com/Windy3f3f3f3f/claude-code-from-scratch.git)开源.