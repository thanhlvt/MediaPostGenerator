import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AI Media Post Generator",
  description: "Automated social media content generation via Multi-Agent AI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark h-full antialiased">
      <body className={`${inter.className} min-h-full bg-slate-950 text-slate-50 flex flex-col selection:bg-indigo-500/30`}>
        <header className="border-b border-white/5 bg-slate-900/50 backdrop-blur-md sticky top-0 z-50">
          <div className="container mx-auto px-6 h-16 flex items-center justify-between">
            <div className="flex items-center gap-8">
              <a href="/" className="text-xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
                MediaGen AI
              </a>
              <nav className="hidden md:flex items-center gap-6 text-sm font-medium">
                <a href="/" className="text-slate-300 hover:text-white transition-colors">Trang chủ</a>
                <a href="/history" className="text-slate-300 hover:text-white transition-colors">Lịch sử</a>
                <a href="/settings" className="text-slate-300 hover:text-white transition-colors">Cài đặt</a>
              </nav>
            </div>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
