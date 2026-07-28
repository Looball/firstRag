"use client";

import Link from "next/link";

export type SidebarAccountModeControlsProps = {
  currentUsername: string;
  isAdvancedMode: boolean;
  onLogout: () => void;
  onAdvancedModeChange: (enabled: boolean) => void;
};

/**
 * 展示工作台侧栏的用户身份入口、退出操作和普通/高级模式切换。
 *
 * 认证状态、退出流程和模式偏好持久化继续由页面层管理，组件只负责渲染并转发操作。
 */
export function SidebarAccountModeControls({
  currentUsername,
  isAdvancedMode,
  onLogout,
  onAdvancedModeChange,
}: SidebarAccountModeControlsProps) {
  return (
    <>
      <div className="flex items-center justify-between gap-3 border-b border-[#c7d1cd] px-1 pb-4">
        <div className="min-w-0">
          <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
            FirstRAG
          </p>
          <Link
            href="/settings"
            title="打开用户设置"
            className="font-display mt-1 block truncate text-lg font-semibold text-[#17201f] underline decoration-[#d5a83b] decoration-2 underline-offset-4 transition hover:text-[#176b62]"
          >
            {currentUsername || "已登录"}
          </Link>
        </div>
        <button
          type="button"
          onClick={onLogout}
          className="font-utility shrink-0 border-b border-[#9eaaa6] px-1 py-1 text-[11px] font-semibold text-[#64716d] transition hover:border-[#e36b4f] hover:text-[#9b3c29]"
        >
          退出
        </button>
      </div>

      <div className="border-b border-[#c7d1cd] py-4">
        <div className="flex items-center justify-between gap-3">
          <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
            模式
          </p>
          <div className="grid grid-cols-2 border border-[#cbd5d1] bg-[#f8faf8] p-0.5 text-[11px] font-semibold text-[#64716d]">
            <button
              type="button"
              aria-pressed={!isAdvancedMode}
              onClick={() => onAdvancedModeChange(false)}
              className={`px-2 py-1 transition ${
                !isAdvancedMode
                  ? "bg-[#176b62] text-white"
                  : "hover:text-[#176b62]"
              }`}
            >
              普通
            </button>
            <button
              type="button"
              aria-pressed={isAdvancedMode}
              onClick={() => onAdvancedModeChange(true)}
              className={`px-2 py-1 transition ${
                isAdvancedMode
                  ? "bg-[#176b62] text-white"
                  : "hover:text-[#176b62]"
              }`}
            >
              高级
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
