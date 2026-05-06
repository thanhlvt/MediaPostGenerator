"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function HistoryPage() {
  const [posts, setPosts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const fetchPosts = async () => {
      try {
        const res = await fetch(`${apiUrl}/api/posts`);
        if (res.ok) {
          const json = await res.json();
          setPosts(json);
        }
      } catch (err) {
        console.error("Fetch posts error:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchPosts();
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "APPROVED":
        return "text-green-400 bg-green-400/10 border-green-400/20";
      case "REJECTED":
        return "text-red-400 bg-red-400/10 border-red-400/20";
      case "PENDING_REVIEW":
        return "text-yellow-400 bg-yellow-400/10 border-yellow-400/20";
      default:
        return "text-slate-400 bg-slate-400/10 border-slate-400/20";
    }
  };

  return (
    <main className="container mx-auto p-6 pb-20 max-w-6xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Lịch sử bài đăng</h1>
          <p className="text-slate-400 text-sm">Quản lý tất cả nội dung đã được AI khởi tạo</p>
        </div>
        <Link 
          href="/" 
          className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-lg font-medium transition-all shadow-lg shadow-indigo-500/20 flex items-center gap-2"
        >
          <span>✨</span> Tạo bài mới
        </Link>
      </div>

      <div className="glass-panel rounded-xl border border-white/10 shadow-2xl overflow-hidden">
        {loading ? (
          <div className="p-20 text-center">
            <div className="inline-block w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4"></div>
            <p className="text-slate-400">Đang tải danh sách...</p>
          </div>
        ) : posts.length === 0 ? (
          <div className="p-20 text-center">
            <div className="text-5xl mb-6">🏜️</div>
            <p className="text-slate-300 text-lg font-medium">Chưa có bài đăng nào</p>
            <p className="text-slate-500 text-sm mt-2">Hãy bắt đầu tạo nội dung đầu tiên của bạn!</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-white/5 text-slate-300 text-sm font-semibold uppercase tracking-wider">
                  <th className="px-6 py-4 border-b border-white/10">Chủ đề (Topic)</th>
                  <th className="px-6 py-4 border-b border-white/10">Nền tảng</th>
                  <th className="px-6 py-4 border-b border-white/10">Trạng thái</th>
                  <th className="px-6 py-4 border-b border-white/10 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {posts.map((post) => (
                  <tr key={post.thread_id} className="hover:bg-white/5 transition-colors group">
                    <td className="px-6 py-5">
                      <div className="flex flex-col">
                        <span className="text-white font-medium mb-1 line-clamp-1">{post.topic || "Không có chủ đề"}</span>
                        <span className="text-xs text-slate-500 font-mono">{post.thread_id.substring(0, 8)}...</span>
                      </div>
                    </td>
                    <td className="px-6 py-5">
                      <div className="flex flex-wrap gap-1.5">
                        {post.post_contents && Object.keys(post.post_contents).map((platform) => (
                          <span key={platform} className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px] font-bold uppercase border border-slate-700">
                            {platform}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-6 py-5">
                      <span className={`px-2.5 py-1 rounded-full text-[11px] font-bold border ${getStatusColor(post.status)}`}>
                        {post.status}
                      </span>
                    </td>
                    <td className="px-6 py-5 text-right">
                      <Link 
                        href={`/review/${post.thread_id}`}
                        className="inline-flex items-center gap-2 bg-white/10 hover:bg-white/20 text-white px-4 py-2 rounded-lg text-sm transition-all border border-white/10"
                      >
                        Chi tiết <span>➡️</span>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
