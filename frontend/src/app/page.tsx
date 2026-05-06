"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [niche, setNiche] = useState("Công nghệ thông tin");
  const [platforms, setPlatforms] = useState<string[]>(["TikTok"]);
  const [loading, setLoading] = useState(false);

  const availablePlatforms = ["Instagram", "LinkedIn", "Twitter", "Facebook", "TikTok"];

  const industries = [
    "Công nghệ thông tin",
    "Điện tử viễn thông",
    "Marketing",
    "Tài chính ngân hàng",
    "Giáo dục",
    "Y tế & Sức khỏe",
    "Bất động sản",
    "Du lịch & Khách sạn",
    "Thời trang & Làm đẹp",
    "Ẩm thực (F&B)",
    "Thể thao & Giải trí",
    "Nông nghiệp công nghệ cao",
    "Khác"
  ];

  const togglePlatform = (platform: string) => {
    setPlatforms((prev) =>
      prev.includes(platform)
        ? prev.filter((p) => p !== platform)
        : [...prev, platform]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic || !niche || platforms.length === 0) return;

    setLoading(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, niche, platforms }),
      });

      if (res.ok) {
        const data = await res.json();
        const targetUrl = `/review/${data.thread_id}`;
        console.log("Redirecting to:", targetUrl);
        router.push(targetUrl);
      } else {
        alert("Failed to start pipeline.");
      }
    } catch (err) {
      console.error(err);
      alert("Error connecting to backend.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex-1 flex flex-col items-center justify-center p-6 sm:p-12">
      <div className="w-full max-w-2xl">
        <div className="text-center mb-10">
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 mb-4">
            AI Media Post Generator
          </h1>
          <p className="text-slate-400 text-lg">
            Hệ thống Multi-Agent nghiên cứu, viết nội dung và sinh ảnh minh họa tự động.
          </p>
        </div>

        <div className="glass-panel rounded-2xl p-6 sm:p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Chủ đề bài đăng (Topic)
              </label>
              <input
                type="text"
                required
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Ví dụ: 5 bí quyết tăng năng suất làm việc tại nhà"
                className="w-full bg-slate-900/50 border border-slate-700/50 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Lĩnh vực (Industry / Niche)
              </label>
              <select
                required
                value={niche}
                onChange={(e) => setNiche(e.target.value)}
                className="w-full bg-slate-900/50 border border-slate-700/50 rounded-lg px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all appearance-none"
                style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2394a3b8'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right 1rem center', backgroundSize: '1.5em' }}
              >
                {industries.map((item) => (
                  <option key={item} value={item} className="bg-slate-900 text-white">
                    {item}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-3">
                Chọn nền tảng đăng bài
              </label>
              <div className="flex flex-wrap gap-3">
                {availablePlatforms.map((platform) => (
                  <button
                    key={platform}
                    type="button"
                    onClick={() => togglePlatform(platform)}
                    className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${platforms.includes(platform)
                        ? "bg-indigo-500 text-white shadow-[0_0_15px_rgba(99,102,241,0.5)]"
                        : "bg-slate-800/50 text-slate-400 hover:bg-slate-700 hover:text-white"
                      }`}
                  >
                    {platform}
                  </button>
                ))}
              </div>
            </div>

            <div className="pt-4">
              <button
                type="submit"
                disabled={loading || platforms.length === 0}
                className="w-full relative group overflow-hidden rounded-lg bg-indigo-600 px-4 py-4 text-sm font-bold text-white transition-all hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:animate-[shimmer_1.5s_infinite]"></div>
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    Đang khởi tạo quy trình AI...
                  </span>
                ) : (
                  "Bắt đầu tạo nội dung"
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </main>
  );
}
