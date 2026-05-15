import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Agent Task Dashboard",
  description: "GitHub 文件轮询式本地 Agent 任务管理后台",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full">
        <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-5 sm:px-6 lg:px-8">
          <header className="mb-6 flex items-center justify-between rounded-[2rem] border border-stone-200/80 bg-white/75 px-5 py-4 shadow-sm backdrop-blur">
            <Link href="/projects" className="flex items-center gap-3">
              <span className="grid size-10 place-items-center rounded-2xl bg-stone-950 text-sm font-black text-stone-50">A</span>
              <span>
                <span className="block text-sm font-semibold uppercase tracking-[0.24em] text-stone-500">Local Agent</span>
                <span className="block text-xl font-semibold tracking-tight text-stone-950">Task Dashboard</span>
              </span>
            </Link>
            <nav className="flex items-center gap-2 text-sm font-medium text-stone-600">
              <Link className="rounded-full px-4 py-2 hover:bg-stone-100" href="/projects">Projects</Link>
              <Link className="rounded-full bg-stone-950 px-4 py-2 text-white hover:bg-stone-800" href="/projects/new">New Project</Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
