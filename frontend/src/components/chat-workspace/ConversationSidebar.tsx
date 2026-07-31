"use client";

import type { ChatSession } from "../../lib/chat-workspace/types";

export type ConversationSidebarProps = {
  sessions: ChatSession[];
  activeSessionId: string;
  isCreatingSession: boolean;
  editingSessionId: string;
  editingTitle: string;
  renamingSessionId: string;
  deletingSessionId: string;
  onCreateSession: () => void | Promise<void>;
  onSelectSession: (session: ChatSession) => void | Promise<void>;
  onStartRename: (session: ChatSession) => void;
  onEditingTitleChange: (title: string) => void;
  onSaveRename: () => void | Promise<void>;
  onCancelRename: () => void;
  onDeleteSession: (sessionId: string) => void | Promise<void>;
};

/**
 * 展示新建会话入口和当前知识库的会话索引。
 *
 * 会话 CRUD 与消息懒加载分别由 actions 和 message loader hooks 管理，组件只负责渲染并转发用户操作。
 */
export function ConversationSidebar({
  sessions,
  activeSessionId,
  isCreatingSession,
  editingSessionId,
  editingTitle,
  renamingSessionId,
  deletingSessionId,
  onCreateSession,
  onSelectSession,
  onStartRename,
  onEditingTitleChange,
  onSaveRename,
  onCancelRename,
  onDeleteSession,
}: ConversationSidebarProps) {
  return (
    <>
      <button
        type="button"
        onClick={() => {
          void onCreateSession();
        }}
        disabled={isCreatingSession}
        className="mt-4 w-full border border-[#17201f] bg-[#17201f] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2d3936] disabled:border-[#9ba8a3] disabled:bg-[#9ba8a3]"
      >
        {isCreatingSession ? "创建中..." : "＋ 新建研究会话"}
      </button>

      <div className="mt-4 flex items-center justify-between px-1">
        <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
          Conversation Index
        </p>
        <p className="font-utility text-[10px] text-[#72807b]">
          {String(sessions.length).padStart(2, "0")}
        </p>
      </div>

      <div className="mt-2 min-h-0 min-w-0 flex-1 space-y-2 overflow-y-auto pr-1">
        {sessions.length === 0 && (
          <p className="px-1 py-2 text-xs text-[#7b8884]">
            暂无会话，发送问题即可开始
          </p>
        )}
        {sessions.map((session) => {
          const isActive = session.id === activeSessionId;

          return (
            <div
              key={session.id}
              className={`min-w-0 w-full border-l-4 px-3 py-3 text-left text-sm transition ${
                isActive
                  ? "border-[#e36b4f] bg-[#17201f] text-white"
                  : "border-transparent bg-[#fcfdfb] text-[#46514e] hover:border-[#d5a83b] hover:bg-white"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  {editingSessionId === session.id ? (
                    <div className="space-y-2">
                      <input
                        aria-label={`重命名 ${session.title}`}
                        value={editingTitle}
                        onChange={(event) =>
                          onEditingTitleChange(event.target.value)
                        }
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            void onSaveRename();
                          }

                          if (event.key === "Escape") {
                            onCancelRename();
                          }
                        }}
                        autoFocus
                        className="research-focus w-full border border-[#b7c4bf] bg-white px-3 py-2 text-sm text-[#17201f]"
                      />
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            void onSaveRename();
                          }}
                          disabled={renamingSessionId === session.id}
                          className="bg-[#176b62] px-2 py-1 text-xs text-white transition hover:bg-[#105149]"
                        >
                          {renamingSessionId === session.id
                            ? "保存中..."
                            : "保存"}
                        </button>
                        <button
                          type="button"
                          onClick={onCancelRename}
                          className="px-2 py-1 text-xs transition hover:bg-[#dfe7e3] hover:text-[#17201f]"
                        >
                          取消
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        void onSelectSession(session);
                      }}
                      className="min-w-0 w-full text-left"
                    >
                      <div className="truncate font-semibold">
                        {session.title}
                      </div>
                      <div
                        className={`mt-1 truncate text-xs ${
                          isActive ? "text-[#b8c8c3]" : "text-[#7b8884]"
                        }`}
                      >
                        {session.messages[session.messages.length - 1]?.content ||
                          "暂无消息"}
                      </div>
                    </button>
                  )}
                </div>

                {editingSessionId !== session.id && (
                  <div className="flex shrink-0 gap-1">
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        onStartRename(session);
                      }}
                      className={`rounded-lg px-2 py-1 text-xs transition ${
                        isActive
                          ? "text-[#b8c8c3] hover:bg-white/10 hover:text-white"
                          : "text-[#73807c] hover:bg-[#dfe7e3] hover:text-[#17201f]"
                      }`}
                    >
                      重命名
                    </button>

                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        void onDeleteSession(session.id);
                      }}
                      disabled={deletingSessionId === session.id}
                      className={`rounded-lg px-2 py-1 text-xs transition ${
                        isActive
                          ? "text-[#b8c8c3] hover:bg-white/10 hover:text-white"
                          : "text-[#73807c] hover:bg-[#fff1ed] hover:text-[#9b3c29]"
                      }`}
                    >
                      {deletingSessionId === session.id
                        ? "删除中..."
                        : "删除"}
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
