"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function HistoryPage() {
  const [posts, setPosts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(10);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [isDeletingBatch, setIsDeletingBatch] = useState(false);

  const fetchPosts = async (currentPage: number, currentLimit: number) => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/posts?page=${currentPage}&limit=${currentLimit}`);
      if (res.ok) {
        const json = await res.json();
        setPosts(json.posts || []);
        setTotal(json.total || 0);
      }
    } catch (err) {
      console.error("Fetch posts error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPosts(page, limit);
    window.scrollTo({ top: 0, behavior: 'smooth' });

    const interval = setInterval(() => {
      fetchPosts(page, limit);
    }, 10000);

    return () => clearInterval(interval);
  }, [page, limit]);

  const totalPages = Math.ceil(total / limit);
  const startRange = (page - 1) * limit + 1;
  const endRange = Math.min(page * limit, total);

  const handleDeletePost = async (threadId: string) => {
    if (!confirm("Bạn có chắc chắn muốn xóa bài viết này không? Hành động này không thể hoàn tác.")) return;

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/posts/${threadId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        fetchPosts(page, limit);
        setSelectedIds(prev => prev.filter(id => id !== threadId));
      } else {
        alert("Lỗi khi xóa bài viết.");
      }
    } catch (err) {
      console.error("Delete post error:", err);
      alert("Lỗi hệ thống khi xóa bài viết.");
    }
  };

  const handleBatchDelete = async () => {
    if (!selectedIds.length) return;
    if (!confirm(`Bạn có chắc chắn muốn xóa ${selectedIds.length} bài viết đã chọn? Hành động này không thể hoàn tác.`)) return;

    setIsDeletingBatch(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/posts/delete-batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_ids: selectedIds }),
      });
      if (res.ok) {
        setSelectedIds([]);
        fetchPosts(page, limit);
      } else {
        alert("Lỗi khi xóa bài viết hàng loạt.");
      }
    } catch (err) {
      console.error("Batch delete error:", err);
      alert("Lỗi hệ thống khi xóa hàng loạt.");
    } finally {
      setIsDeletingBatch(false);
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    if (selectedIds.length === posts.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(posts.map(p => p.thread_id));
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "APPROVED":
        return "text-green-400 bg-green-400/10 border-green-400/20";
      case "REJECTED":
        return "text-red-400 bg-red-400/10 border-red-400/20";
      case "PENDING_REVIEW":
        return "text-indigo-400 bg-indigo-400/10 border-indigo-400/20";
      case "ERROR":
        return "text-slate-100 bg-red-600 border-red-700";
      default:
        return "text-indigo-300 bg-indigo-500/10 border-indigo-500/20 animate-pulse";
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case "START": return "INITIALIZING";
      case "RESEARCHING": return "RESEARCHING";
      case "WRITING": return "WRITING";
      case "GENERATING_IMAGE": return "GENERATING IMAGE";
      case "PENDING_REVIEW": return "PENDING REVIEW";
      case "APPROVED": return "APPROVED";
      case "REJECTED": return "REJECTED";
      case "ERROR": return "ERROR";
      default: return status;
    }
  };

  return (
    <main className="container mx-auto p-6 pb-20 max-w-6xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Lịch sử bài đăng</h1>
          <p className="text-slate-400 text-sm">Quản lý tất cả nội dung đã được AI khởi tạo</p>
        </div>
        <div className="flex items-center gap-3">
          {selectedIds.length > 0 && (
            <button
              onClick={handleBatchDelete}
              disabled={isDeletingBatch}
              className="bg-red-500/20 hover:bg-red-500/30 text-red-400 px-5 py-2.5 rounded-lg font-medium transition-all border border-red-500/30 flex items-center gap-2"
            >
              {isDeletingBatch ? (
                <span className="w-4 h-4 rounded-full border-2 border-red-400/50 border-t-red-400 animate-spin"></span>
              ) : (
                <span>🗑️</span>
              )}
              Xóa {selectedIds.length} mục đã chọn
            </button>
          )}
          <Link
            href="/"
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-lg font-medium transition-all shadow-lg shadow-indigo-500/20 flex items-center gap-2"
          >
            <span>✨</span> Tạo bài mới
          </Link>
        </div>
      </div>

      <div className="glass-panel rounded-xl border border-white/10 shadow-2xl overflow-hidden">
        {loading && posts.length === 0 ? (
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
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-white/5 text-slate-300 text-sm font-semibold uppercase tracking-wider">
                    <th className="px-6 py-4 border-b border-white/10 w-10">
                      <input
                        type="checkbox"
                        checked={selectedIds.length === posts.length && posts.length > 0}
                        onChange={toggleSelectAll}
                        className="w-4 h-4 rounded border-white/20 bg-slate-800 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                      />
                    </th>
                    <th className="px-6 py-4 border-b border-white/10">Chủ đề (Topic)</th>
                    <th className="px-6 py-4 border-b border-white/10">Nền tảng</th>
                    <th className="px-6 py-4 border-b border-white/10">Trạng thái</th>
                    <th className="px-6 py-4 border-b border-white/10">Ngày tạo</th>
                    <th className="px-6 py-4 border-b border-white/10 text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {posts.map((post) => (
                    <tr key={post.thread_id} className={`hover:bg-white/5 transition-colors group ${selectedIds.includes(post.thread_id) ? "bg-white/5" : ""}`}>
                      <td className="px-6 py-5">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(post.thread_id)}
                          onChange={() => toggleSelect(post.thread_id)}
                          className="w-4 h-4 rounded border-white/20 bg-slate-800 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                        />
                      </td>
                      <td className="px-6 py-5">
                        <div className="flex flex-col">
                          <span className="text-white font-medium mb-1">{post.topic || "Không có chủ đề"}</span>
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
                          {getStatusLabel(post.status)}
                        </span>
                      </td>
                      <td className="px-6 py-5 text-slate-400 text-sm">
                        {post.created_at ? new Date(post.created_at).toLocaleString('vi-VN', {
                          day: '2-digit',
                          month: '2-digit',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        }) : "---"}
                      </td>
                      <td className="px-6 py-5 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {post.status === "PENDING_REVIEW" ? (
                            <Link
                              href={`/review/${post.thread_id}`}
                              className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm transition-all shadow-lg shadow-indigo-500/30"
                            >
                              Review
                            </Link>
                          ) : (
                            <Link
                              href={`/review/${post.thread_id}`}
                              className="inline-flex items-center gap-2 bg-white/5 hover:bg-white/10 text-slate-300 px-4 py-2 rounded-lg text-sm transition-all border border-white/10"
                            >
                              Details
                            </Link>
                          )}
                          <button
                            onClick={() => handleDeletePost(post.thread_id)}
                            className="p-2 text-slate-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all"
                            title="Xóa bài viết"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination UI */}
            <div className="px-6 py-4 bg-white/5 border-t border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-4 text-sm text-slate-400">
                <div className="flex items-center gap-2">
                  <span>Hiển thị</span>
                  <select
                    value={limit}
                    onChange={(e) => {
                      setLimit(Number(e.target.value));
                      setPage(1);
                    }}
                    className="bg-slate-800 border border-white/10 rounded px-2 py-1 text-slate-200 outline-none focus:border-indigo-500 transition-all cursor-pointer"
                  >
                    {[10, 20, 50, 100].map(val => (
                      <option key={val} value={val}>{val}</option>
                    ))}
                  </select>
                </div>
                <span>
                  <span className="font-medium text-slate-200">{startRange}-{endRange}</span> trong số <span className="font-medium text-slate-200">{total}</span> bài viết
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 rounded-lg border border-white/10 text-slate-300 text-sm font-medium hover:bg-white/5 disabled:opacity-30 disabled:hover:bg-transparent transition-all"
                >
                  Trước
                </button>
                <div className="flex items-center gap-1">
                  {[...Array(totalPages)].map((_, i) => (
                    <button
                      key={i + 1}
                      onClick={() => setPage(i + 1)}
                      className={`w-8 h-8 rounded-lg text-xs font-bold transition-all ${
                        page === i + 1
                          ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/30"
                          : "text-slate-400 hover:bg-white/5"
                      }`}
                    >
                      {i + 1}
                    </button>
                  )).slice(Math.max(0, page - 3), Math.min(totalPages, page + 2))}
                </div>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-3 py-1.5 rounded-lg border border-white/10 text-slate-300 text-sm font-medium hover:bg-white/5 disabled:opacity-30 disabled:hover:bg-transparent transition-all"
                >
                  Sau
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
