export type ChatWorkspaceHeaderProps = {
  knowledgeBaseName?: string;
  sessionTitle?: string;
  messageCount: number;
  fileCount: number;
};

/**
 * 展示聊天工作区标题、当前知识库以及消息和文件统计。
 *
 * 知识库、会话和文件状态由页面层管理，组件只接收当前视图所需的 primitive props。
 */
export function ChatWorkspaceHeader({
  knowledgeBaseName,
  sessionTitle,
  messageCount,
  fileCount,
}: ChatWorkspaceHeaderProps) {
  return (
    <header className="shrink-0 border-b border-[#cbd5d1] bg-[#fcfdfb] px-5 py-5 md:px-8 md:py-6">
      <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <span className="font-utility bg-[#d5a83b] px-2 py-1 text-[10px] font-bold uppercase text-[#17201f]">
              Live Research
            </span>
            <span className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
              {knowledgeBaseName || "暂无知识库"}
            </span>
          </div>
          <h1 className="font-display mt-4 truncate text-3xl font-semibold text-[#17201f] md:text-4xl">
            {sessionTitle || "聊天工作台"}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#64716d]">
            基于当前知识库继续提问，回答与上下文会保存在此会话中。
          </p>
        </div>
        <div className="font-utility flex shrink-0 gap-5 border-t border-[#d6dedb] pt-4 text-[10px] uppercase text-[#72807b] md:border-l md:border-t-0 md:pl-5 md:pt-0">
          <span>
            消息
            <strong className="mt-1 block text-base text-[#17201f]">
              {String(messageCount).padStart(2, "0")}
            </strong>
          </span>
          <span>
            文件
            <strong className="mt-1 block text-base text-[#17201f]">
              {String(fileCount).padStart(2, "0")}
            </strong>
          </span>
        </div>
      </div>
    </header>
  );
}
