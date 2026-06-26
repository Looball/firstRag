import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "❤️本地知识库问答系统Demo❤️",
  description: "一个基于 Next.js 和 langchain 构建的 本地知识库问答系统",
};


/**
 * 根布局组件，定义了整个应用的基本HTML结构
 * @param children - 子组件，将被包裹在根布局中
 * @returns 返回一个包含子组件的完整HTML结构
 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
