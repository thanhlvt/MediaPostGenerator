"use client";

import { useState, useEffect } from "react";

const TEXT_MODELS = [
  "deepseek/deepseek-v4-flash",
  "deepseek/deepseek-v4-pro",
  "openai/gpt-oss-120b",
  "openai/gpt-oss-20b",
  "openai/gpt-5.5",
  "google/gemini-3.1-flash-lite",
  "google/gemini-3.1-pro-preview",
  "google/gemini-3-flash-preview",
  "anthropic/claude-sonnet-4.6",
  "anthropic/claude-opus-4.6",
  "openai/gpt-5.4-mini",
  "moonshotai/kimi-k2.6",
  "minimax/minimax-m2.7",
  "x-ai/grok-4.3",
  "z-ai/glm-5.1",
];

const IMAGE_MODELS = [
  "google/gemini-3-pro-image-preview",
  "google/gemini-2.5-flash-image",
  "openai/gpt-5.4-image-2",
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<any>({
    topic_model: "deepseek/deepseek-v4-flash",
    research_model: "deepseek/deepseek-v4-flash",
    writer_model: "deepseek/deepseek-v4-flash",
    qa_model: "deepseek/deepseek-v4-flash",
    image_model: "google/gemini-2.5-flash-image",
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  useEffect(() => {
    fetch(`${backendUrl}/api/settings`)
      .then((res) => res.json())
      .then((data) => {
        if (Object.keys(data).length > 0) {
          setSettings(data);
        }
        setIsLoading(false);
      })
      .catch((err) => {
        console.error("Failed to fetch settings:", err);
        setIsLoading(false);
      });
  }, [backendUrl]);

  const handleSave = async () => {
    setIsSaving(true);
    setMessage("");
    try {
      const res = await fetch(`${backendUrl}/api/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      if (res.ok) {
        setMessage("Cài đặt đã được lưu thành công!");
      } else {
        setMessage("Lỗi khi lưu cài đặt.");
      }
    } catch (err) {
      setMessage("Không thể kết nối tới server.");
    } finally {
      setIsSaving(false);
      setTimeout(() => setMessage(""), 3000);
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="flex-1 container mx-auto max-w-2xl p-8">
      <div className="glass-panel p-8 rounded-2xl border border-white/10 shadow-2xl">
        <h1 className="text-3xl font-bold mb-8 bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
          Cấu hình Model AI
        </h1>

        <div className="space-y-8">
          {/* Topic Agent */}
          <div className="space-y-2">
            <label className="text-sm font-semibold text-slate-300 block">Topic Agent Model</label>
            <p className="text-xs text-slate-500 mb-2 italic">Dùng để phân tích chủ đề và gợi ý tiêu đề viral.</p>
            <select
              value={settings.topic_model}
              onChange={(e) => setSettings({ ...settings, topic_model: e.target.value })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
            >
              {TEXT_MODELS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          {/* Research Agent */}
          <div className="space-y-2">
            <label className="text-sm font-semibold text-slate-300 block">Research Agent Model</label>
            <p className="text-xs text-slate-500 mb-2 italic">Dùng để tổng hợp thông tin từ Tavily thành Research Brief.</p>
            <select
              value={settings.research_model}
              onChange={(e) => setSettings({ ...settings, research_model: e.target.value })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
            >
              {TEXT_MODELS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          {/* Writer Agent */}
          <div className="space-y-2">
            <label className="text-sm font-semibold text-slate-300 block">Writer Agent Model</label>
            <p className="text-xs text-slate-500 mb-2 italic">Dùng để viết nội dung chi tiết cho từng nền tảng (TikTok, FB, LinkedIn,...).</p>
            <select
              value={settings.writer_model}
              onChange={(e) => setSettings({ ...settings, writer_model: e.target.value })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
            >
              {TEXT_MODELS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          {/* QA Agent */}
          <div className="space-y-2">
            <label className="text-sm font-semibold text-slate-300 block">QA Agent Model</label>
            <p className="text-xs text-slate-500 mb-2 italic">Dùng để kiểm tra chất lượng nội dung và so khớp với Research Brief.</p>
            <select
              value={settings.qa_model}
              onChange={(e) => setSettings({ ...settings, qa_model: e.target.value })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
            >
              {TEXT_MODELS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          {/* Image Agent */}
          <div className="space-y-2">
            <label className="text-sm font-semibold text-slate-300 block">Image Agent Model</label>
            <p className="text-xs text-slate-500 mb-2 italic">Dùng để tạo ảnh minh họa cuối cùng.</p>
            <select
              value={settings.image_model}
              onChange={(e) => setSettings({ ...settings, image_model: e.target.value })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
            >
              {IMAGE_MODELS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          <div className="pt-6 border-t border-white/5 flex flex-col gap-4">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className={`w-full py-4 rounded-xl font-bold text-white transition-all transform active:scale-[0.98] ${isSaving
                ? "bg-slate-700 cursor-not-allowed"
                : "bg-gradient-to-r from-indigo-600 to-purple-600 hover:shadow-[0_0_20px_rgba(79,70,229,0.4)]"
                }`}
            >
              {isSaving ? "Đang lưu..." : "Lưu cài đặt"}
            </button>

            {message && (
              <div className={`p-4 rounded-lg text-sm text-center animate-in fade-in slide-in-from-bottom-2 ${message.includes("thành công") ? "bg-green-500/20 text-green-400 border border-green-500/30" : "bg-red-500/20 text-red-400 border border-red-500/30"
                }`}>
                {message}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
