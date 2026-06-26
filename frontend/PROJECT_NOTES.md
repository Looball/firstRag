# AI 学习助手项目阶段笔记

## 1. 当前项目阶段

这个项目已经从最初的 `Next.js` 默认模板，逐步演化成了一个具备真实 AI 对话能力的“AI 学习助手”网站原型。

当前版本已经不再只是一个简单聊天壳，而是具备了：
- 真实 DeepSeek 接入
- 多轮聊天
- 多会话管理
- 本地持久化
- 会话级状态管理
- 一定程度的产品交互打磨

---

## 2. 已完成的任务

## 2.1 基础工程搭建

已完成：
- 创建 `Next.js + TypeScript + Tailwind CSS` 项目
- 理解并使用 `App Router`
- 跑通本地开发环境
- 修改默认模板页面为自定义首页

相关文件：
- [`page.tsx`](/Users/bing/Documents/New%20project/ai-research-assistant/src/app/page.tsx)
  - 前端聊天页面
  - 负责输入、发送、展示消息、显示 loading 和错误
- [`layout.tsx`](/Users/bing/Documents/New%20project/ai-research-assistant/src/app/layout.tsx)
  - 全局布局
  - 负责 metadata、html/body 外壳、字体和全局结构
- [`globals.css`](/Users/bing/Documents/New%20project/ai-research-assistant/src/app/globals.css)
  - 全局样式

---

## 2.2 前后端基础打通

已完成：
- 在同一个 Next.js 项目中同时编写前端页面和后端 API
- 前端通过 `fetch("/api/chat")` 调用后端
- 后端通过 [`route.ts`](/Users/bing/Documents/New%20project/ai-research-assistant/src/app/api/chat/route.ts) 提供 API 能力

已理解：
- `page.tsx` 是页面入口
- `route.ts` 是 API 路由入口
- 文件夹路径决定 URL
- 特殊文件名决定角色

---

## 2.3 接入真实 AI 模型

已完成：
- 使用 `DeepSeek`
- 在 [`.env.local`](/Users/bing/Documents/New%20project/ai-research-assistant/.env.local) 中存放 `DEEPSEEK_API_KEY`
- 使用 `openai` SDK 的兼容方式调用 DeepSeek
- 后端使用 `system + messages` 发送给模型

已实现能力：
- 用户提交问题
- 后端调用 DeepSeek
- 前端展示真实回答

---

## 2.4 从单轮问答升级为多轮聊天

已完成：
- 从 `question + answer` 状态结构升级为 `input + messages`
- 每条消息具有：
  - `role`
  - `content`
- 支持用户消息与 AI 回复连续追加
- 页面从“单轮回答框”升级为“消息流”

---

## 2.5 多会话聊天管理

已完成：
- 引入 `ChatSession` 结构
- 支持多个会话
- 支持切换当前会话
- 支持新建会话
- 支持删除会话
- 支持重命名会话
- 当前会话由 `currentSessionId` 决定

当前会话结构：

```ts
type ChatSession = {
  id: string;
  title: string;
  messages: Message[];
};
```

---

## 2.6 会话标题优化

已完成：
- 初始标题为 `新对话`
- 首次发送消息时，自动根据用户输入生成标题
- 标题支持：
  - 清理多余空格
  - 截断过长内容
- 后续可手动重命名会话

---

## 2.7 本地持久化

已完成：
- 使用 `localStorage` 保存：
  - `sessions`
  - `currentSessionId`
- 刷新页面后恢复会话和当前选中的会话
- 添加 `hasLoaded`，避免初始化时错误覆盖本地数据

相关思路：
- 首次加载时恢复数据
- 后续状态变化时自动保存

---

## 2.8 会话级 loading / error 状态

已完成：
- 从全局 `isLoading / error` 升级为按会话维护状态
- 解决了“会话1请求中导致会话2也被锁住”的问题
- 支持多个会话并发请求

当前状态结构思路：
- `loadingSessions: Record<string, boolean>`
- `sessionErrors: Record<string, string>`

---

## 2.9 消息交互优化

已完成：
- `Enter` 发送消息
- `Shift + Enter` 换行
- 每条 AI 消息支持复制回答
- 点击后短暂显示“已复制”

---

## 2.10 页面滚动与布局优化

已完成：
- 左侧会话列表独立滚动
- 右侧恢复为页面自然滚动
- 点击左侧会话时，右侧自动滚到底部
- 添加右下角悬浮“回到顶部”按钮
- 自动滚动逻辑经过优化：
  - 当前会话新增消息时滚动
  - 当前会话 loading 开始时滚动
  - 切换会话时按当前需求滚到底部

---

## 2.11 学习场景增强

已完成：
- 增加快捷问题按钮
- 让页面更像“AI 学习助手”而不是空白聊天框

当前快捷问题示例：
- 什么是大语言模型
- RAG 是什么
- Agent 和普通聊天机器人有什么区别
- 提示词工程的核心原则有哪些

---

## 3. 当前网站交互逻辑

## 3.1 会话层逻辑

1. 用户点击左侧某个会话
2. 更新 `currentSessionId`
3. 通过 `sessions.find(...)` 得到 `currentSession`
4. 右侧自动渲染 `currentSession.messages`

## 3.2 消息发送逻辑

1. 检查输入是否为空
2. 构造用户消息
3. 把用户消息追加到当前会话
4. 设置当前会话 loading
5. 调用 `/api/chat`
6. DeepSeek 返回结果
7. 构造 assistant 消息
8. 追加到当前会话
9. 清除当前会话 loading
10. 如果失败则记录当前会话错误

## 3.3 本地保存逻辑

1. 页面首次加载时：
   - 从 `localStorage` 读取 `sessions`
   - 恢复 `currentSessionId`
2. 每当 `sessions` 或 `currentSessionId` 变化：
   - 自动写回 `localStorage`

## 3.4 滚动逻辑

- 左侧：
  - 自己滚动
- 右侧：
  - 跟页面一起滚
- 自动滚动：
  - 当前会话新增消息时滚到底部
  - 当前会话 loading 开始时滚到底部
- 辅助按钮：
  - 点击“回到顶部”回到页面顶部

---

## 4. 当前技术难点

## 4.1 状态设计从简单到复杂的演进

项目中最大的技术难点之一是：
如何从简单状态逐步演进到更接近真实产品的状态结构。

经历了这些阶段：

### 阶段 1

```ts
question
answer
```

### 阶段 2

```ts
input
messages
```

### 阶段 3

```ts
sessions
currentSessionId
```

### 阶段 4

```ts
loadingSessions
sessionErrors
```

这说明随着功能变复杂，状态必须更细分、更贴近真实业务对象。

---

## 4.2 避免重复状态

一个关键认知是：

`能从已有状态推导出来的值，不要再额外存一份 state`

典型例子：

```tsx
const currentSession =
  sessions.find((session) => session.id === currentSessionId) || sessions[0];
```

这里 `currentSession` 不需要单独 `useState`。

原因：
- 它能由 `sessions + currentSessionId` 推导
- 如果额外存一份，容易不同步

---

## 4.3 全局状态与局部状态边界

多会话出现后，出现了一个典型问题：

### 错误做法
- `isLoading`
- `error`

做成全局状态

后果：
- 会话1请求中，会话2也显示 loading
- 会话2无法发送消息

### 正确做法
把状态做成“按会话管理”

例如：
- `loadingSessions[sessionId]`
- `sessionErrors[sessionId]`

这体现了一个重要工程思维：

`状态作用范围必须和业务对象的作用范围一致`

---

## 4.4 useEffect 的时机和依赖

项目中使用了多个 `useEffect`，包括：
- 初始化恢复 localStorage
- 状态变化后保存 localStorage
- 自动滚动到底部

这里的难点在于理解：
- `[]`：只执行一次
- `[messages]`：依赖变化时执行
- `useEffect` 是渲染后的副作用机制，不是普通函数调用

同时还要理解：
- 为什么多个 effect 可以拆开
- 为什么一个 effect 只做一件事更清晰

---

## 4.5 localStorage 初始化覆盖问题

一个很关键的工程问题是：

如果组件一上来就先把默认状态写进 localStorage，
可能会把旧聊天记录覆盖掉。

解决方式：
- 引入 `hasLoaded`
- 先恢复
- 恢复完成后再开始保存

这个问题体现了：
`初始化流程和持续同步流程不能混为一谈`

---

## 4.6 自动滚动体验设计

自动滚动最初看起来简单，但其实涉及很多交互细节：

- 切换会话时是否要滚动
- 新增消息时是否要滚动
- loading 出现时是否要滚动
- 阅读长内容时是否要保留用户当前位置

最终项目中做了区分：
- 当前会话新增消息：滚动
- loading 开始：滚动
- 切换会话：根据当前产品决定处理方式

这说明：
`“能实现” 和 “体验合理” 之间还有一层交互设计问题`

---

## 4.7 列表渲染和 key

会话列表中使用了：

```tsx
key={session.id}
```

需要理解：
- `session.id` 是业务数据标识
- `key` 是交给 React 用来识别列表项的稳定标识

难点在于：
- 为什么不能乱用 `index`
- 为什么 key 需要稳定唯一
- 为什么 React 依赖 key 做列表 diff

---

## 4.8 闭包与事件处理

左侧点击某个会话时，按钮之所以“知道自己的 id”，本质是因为：

- 按钮是在 `sessions.map((session) => ...)` 中生成的
- `onClick` 闭包记住了当前这轮的 `session`

这个点对理解 React 列表事件非常重要。

---

## 5. 需要重点理解的概念

## React 相关

- `useState`
- `useEffect`
- `useRef`
- 条件渲染
- 受控组件
- 状态驱动 UI
- 不可变更新
- `setState(prev => ...)`
- 闭包
- 列表渲染与 `key`

## Next.js 相关

- `page.tsx`
- `layout.tsx`
- `route.ts`
- App Router
- 页面路由 vs API 路由
- 前后端同项目协作
- 环境变量 `.env.local`

## AI 应用相关

- `messages` 结构
- `system / user / assistant`
- 多轮聊天为什么要带历史上下文
- 前端不能直接暴露 API key
- 前端 -> 后端 -> 模型 的正确调用链
- 单轮问答与多轮聊天的区别

## 产品交互相关

- 多会话管理
- loading/error 状态作用域
- 自动滚动体验
- 长内容阅读 vs 聊天式交互
- 会话命名与管理体验

---

## 6. 当前项目的核心收获

当前阶段最大的收获不是“做了一个聊天页面”，而是理解了：

1. 一个 AI 网站不是单纯把 API 接上去
2. 前端状态结构会随着产品复杂度不断演进
3. 多会话、多状态、滚动、持久化这些问题都是 AI 产品真实工程的一部分
4. React/Next.js 的很多设计，其实都在帮你把“数据 -> UI”的关系变清楚

---

## 7. 当前项目总结

当前网站已经具备：

- 真实 DeepSeek 对话能力
- 多轮聊天
- 多会话管理
- 本地持久化
- 独立会话状态
- 快捷问题
- 复制回答
- 页面导航辅助

它已经是一个相当完整的“AI 学习助手原型”。

---

## 8. 下一阶段建议

下一步最值得推进的不是继续优化聊天壳，而是进入真正的“学习助手能力”：

### 推荐下一步
- 增加“学习材料输入区”
- 用户先粘贴一段资料
- 再基于资料提问
- 让网站从“聊天”走向“学习辅助”

再往后可以继续发展为：
- 文件上传
- 文档总结
- RAG
- 多资料对比
- 学习提纲生成

---

## 9. 一句话总览

这个项目当前已经从“一个能聊天的网页”进化为“一个具备多会话、持久化和基础产品体验的 AI 学习助手原型”，接下来最值得进入的是“基于学习材料的问答能力”。
