"use client"; // Trigger Turbopack recompile

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";

export default function ReviewPage() {
  const params = useParams();
  const thread_id = params?.id;
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [feedback, setFeedback] = useState("");
  const [isRejecting, setIsRejecting] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [expandedReasoning, setExpandedReasoning] = useState<Record<string, boolean>>({
    topic: false,
    brief: false
  });
  const [copiedPlatform, setCopiedPlatform] = useState<string | null>(null);

  const copyToClipboard = (text: string, platform: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedPlatform(platform);
      setTimeout(() => setCopiedPlatform(null), 2000);
    });
  };

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    const fetchStatus = async () => {
      try {
        const res = await fetch(`${apiUrl}/api/status/${thread_id}`);
        if (res.ok) {
          const json = await res.json();
          console.log("Status update:", json);
          // Only update base data if not currently writing/researching (to prevent race conditions with SSE)
          setData((prev: any) => {
            const isActiveStreaming = ["START", "RESEARCHING", "WRITING"].includes(json.status);
            if (isActiveStreaming && prev) {
               return { 
                 ...json, 
                 post_contents: prev.status === "WRITING" ? prev.post_contents : json.post_contents,
                 selected_title: prev.status === "START" ? prev.selected_title : json.selected_title,
                 research_brief: prev.status === "RESEARCHING" ? prev.research_brief : json.research_brief,
                 reasoning: prev.reasoning || json.reasoning,
                 topic_reasoning: prev.topic_reasoning || json.topic_reasoning,
                 brief_reasoning: prev.brief_reasoning || json.brief_reasoning
               };
            }
            return json;
          });
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    };

    fetchStatus();
    // Poll every 3 seconds
    const interval = setInterval(() => {
      fetchStatus();
    }, 3000);

    return () => clearInterval(interval);
  }, [thread_id]);

  // SSE for real-time streaming
  const lastIndexRef = useRef<number>(-1);
  const needsClearPostsRef = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const briefScrollRef = useRef<HTMLPreElement>(null);
  const postsScrollRef = useRef<HTMLDivElement>(null);

  // Auto scroll to bottom when content updates
  useEffect(() => {
    const activeStreamingPhases = ["START", "RESEARCHING", "WRITING"];
    if (activeStreamingPhases.includes(data?.status)) {
      // Scroll internal containers if they are active
      if (data?.status === "RESEARCHING" && briefScrollRef.current) {
        briefScrollRef.current.scrollTop = briefScrollRef.current.scrollHeight;
      }
      if (data?.status === "WRITING" && postsScrollRef.current) {
        postsScrollRef.current.scrollTop = postsScrollRef.current.scrollHeight;
      }
    }
  }, [data?.post_contents, data?.selected_title, data?.research_brief, data?.status]);

  useEffect(() => {
    if (!thread_id) return;

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const eventSource = new EventSource(`${apiUrl}/api/stream/${thread_id}`);

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        console.log("SSE Event:", payload);

        // Avoid processing duplicate messages (especially during history replay)
        if (payload.index !== undefined) {
          if (payload.index <= lastIndexRef.current) return;
          lastIndexRef.current = payload.index;
        }

        if (payload.type === "topic_token") {
          setExpandedReasoning(e => e.topic ? ({ ...e, topic: false }) : e);
          setData((prev: any) => {
            if (prev?.status !== "START") return prev; // Only append if in start/topic phase
            return { ...prev, selected_title: (prev?.selected_title || "") + payload.content };
          });
        } else if (payload.type === "topic_reasoning") {
          setExpandedReasoning(e => e.topic ? e : ({ ...e, topic: true }));
          setData((prev: any) => ({ ...prev, topic_reasoning: (prev?.topic_reasoning || "") + payload.content }));
        } else if (payload.type === "brief_token") {
          setExpandedReasoning(e => e.brief ? ({ ...e, brief: false }) : e);
          setData((prev: any) => {
            if (prev?.status !== "RESEARCHING") return prev;
            return { ...prev, research_brief: (prev?.research_brief || "") + payload.content };
          });
        } else if (payload.type === "brief_reasoning") {
          setExpandedReasoning(e => e.brief ? e : ({ ...e, brief: true }));
          setData((prev: any) => ({ ...prev, brief_reasoning: (prev?.brief_reasoning || "") + payload.content }));
        } else if (payload.type === "token") {
          const shouldClear = needsClearPostsRef.current;
          if (shouldClear) needsClearPostsRef.current = false;
          setExpandedReasoning(e => e[payload.platform] ? ({ ...e, [payload.platform]: false }) : e);
          setData((prev: any) => {
            if (prev?.status !== "WRITING") return prev;
            if (shouldClear) {
              return { ...prev, post_contents: { [payload.platform]: payload.content }, reasoning: {} };
            }
            const newContents = { ...prev?.post_contents };
            newContents[payload.platform] = (newContents[payload.platform] || "") + payload.content;
            return { ...prev, post_contents: newContents };
          });
        } else if (payload.type === "reasoning") {
          const shouldClear = needsClearPostsRef.current;
          if (shouldClear) needsClearPostsRef.current = false;
          setExpandedReasoning(e => e[payload.platform] ? e : ({ ...e, [payload.platform]: true }));
          setData((prev: any) => {
            if (shouldClear) {
              return { ...prev, post_contents: {}, reasoning: { [payload.platform]: payload.content } };
            }
            const newReasoning = { ...prev?.reasoning || {} };
            newReasoning[payload.platform] = (newReasoning[payload.platform] || "") + payload.content;
            return { ...prev, reasoning: newReasoning };
          });
        } else if (payload.type === "error") {
          console.error("Stream error:", payload.message);
          setData((prev: any) => ({ ...prev, status: "ERROR", feedback: payload.message }));
          eventSource.close();
        }
      } catch (err) {
        console.error("Failed to parse SSE data:", err);
      }
    };

    eventSource.onerror = (err) => {
      console.error("SSE connection error, retrying...", err);
      // eventSource.close(); // Don't close, let it retry automatically
    };

    return () => {
      eventSource.close();
    };
  }, [thread_id, data?.status]);

  const handleReview = async (action: "APPROVE" | "REJECT", manualFeedback?: string) => {
    const finalFeedback = manualFeedback || feedback;
    if (action === "REJECT" && !finalFeedback) {
      alert("Please provide feedback for rejection.");
      return;
    }

    setActionLoading(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/review/${thread_id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, feedback: action === "REJECT" ? finalFeedback : null }),
      });

      if (res.ok) {
        if (action === "REJECT") {
          setIsRejecting(false);
          setFeedback("");
          needsClearPostsRef.current = true;
          setData((prev: any) => ({ ...prev, status: "WRITING", post_contents: {} }));
        } else {
          // Success! Update local status to reflect approval immediately
          setData((prev: any) => ({ ...prev, status: "APPROVED" }));
        }
      }
    } catch (err) {
      console.error(err);
      alert("Error submitting review.");
    } finally {
      setActionLoading(false);
    }
  };

  const phases = [
    { key: "START", label: "Khởi tạo hệ thống", icon: "🚀" },
    { key: "RESEARCHING", label: "Nghiên cứu thông tin", icon: "🔍" },
    { key: "WRITING", label: "Viết nội dung bài đăng", icon: "✍️" },
    { key: "GENERATING_IMAGE", label: "Thiết kế ảnh minh họa", icon: "🎨" },
    { key: "QUALITY_ASSURANCE", label: "Kiểm định chất lượng", icon: "🛡️" },
    { key: "SCHEDULING", label: "Lập lịch đăng bài", icon: "📅" },
    { key: "PENDING_REVIEW", label: "Hoàn tất", icon: "✅" },
  ];

  let displayStatus = data?.status || "START";
  if (displayStatus === "REJECTED") displayStatus = "WRITING";
  const currentPhaseIndex = data ? Math.max(0, phases.findIndex(p => p.key === displayStatus)) : 0;
  const status = (data?.status || "START").toUpperCase();
  const isWaitingForReview = status === "PENDING_REVIEW";
  const isCompleted = status === "APPROVED" || status === "REJECTED";
  const isError = status === "ERROR";

  console.log("Current Status:", status, "isCompleted:", isCompleted);

  return (
    <main className="flex-1 container mx-auto p-6 pb-20 flex flex-col gap-8">
      {/* Sidebar Progress Tracker */}

      {/* Main Content Area */}
      <div className="w-full flex flex-col space-y-6">
        {/* Header & Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass-panel p-6 rounded-xl border border-indigo-500/20 shadow-lg relative overflow-hidden">
          {!isWaitingForReview && !isError && !isCompleted && (
            <div className="absolute top-0 left-0 w-full h-1 bg-indigo-500/30">
              <div className="h-full bg-indigo-500 w-1/3 animate-[slide_2s_ease-in-out_infinite]"></div>
            </div>
          )}
          {isError && (
            <div className="absolute top-0 left-0 w-full h-1 bg-red-500"></div>
          )}
          <div>
            <h1 className="text-2xl font-bold mb-1">{isError ? "System Error" : "Review Output"}</h1>
            <p className="text-sm text-slate-400">
              {isError ? "The AI pipeline encountered a critical error." :
                status === "APPROVED" ? "This post has been approved and scheduled for publishing." :
                  status === "REJECTED" ? "This post has been rejected and is being rewritten." :
                    isWaitingForReview ? "Review the generated content below. Approve to schedule or reject to rewrite." :
                      "AI is currently working on your request. Content will appear dynamically..."}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {status === "APPROVED" && (
              <div className="flex items-center gap-2">
                <span className="bg-green-500/20 text-green-400 px-4 py-2 rounded-lg text-sm font-bold border border-green-500/50 flex items-center gap-2 shadow-[0_0_15px_rgba(34,197,94,0.2)]">
                  <span className="text-base">✅</span> POST APPROVED
                </span>
                <button
                  onClick={() => handleReview("REJECT", "Tạo lại nội dung mới.")}
                  disabled={actionLoading}
                  className="bg-white/5 hover:bg-white/10 text-slate-300 px-4 py-2 rounded-lg text-sm transition-all border border-white/10 flex items-center gap-2"
                >
                  Tạo lại 🔄
                </button>
              </div>
            )}
            {status === "REJECTED" && (
              <div className="flex items-center gap-2">
                <span className="bg-red-500/20 text-red-400 px-4 py-2 rounded-lg text-sm font-bold border border-red-500/50 flex items-center gap-2 shadow-[0_0_15px_rgba(239,68,68,0.2)]">
                  <span className="text-base">❌</span> POST REJECTED
                </span>
                <button
                  onClick={() => handleReview("REJECT", "Tạo lại nội dung mới.")}
                  disabled={actionLoading}
                  className="bg-white/5 hover:bg-white/10 text-slate-300 px-4 py-2 rounded-lg text-sm transition-all border border-white/10 flex items-center gap-2"
                >
                  Tạo lại 🔄
                </button>
              </div>
            )}

            {!isCompleted && (
              <>
                <button
                  onClick={() => setIsRejecting(true)}
                  disabled={!isWaitingForReview || actionLoading}
                  className="px-4 py-2 rounded-lg border border-red-500/50 text-red-400 font-medium hover:bg-red-500/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  Reject & Rewrite
                </button>
                <button
                  onClick={() => handleReview("APPROVE")}
                  disabled={!isWaitingForReview || actionLoading}
                  className="px-4 py-2 rounded-lg bg-green-600 text-white font-medium shadow-[0_0_15px_rgba(22,163,74,0.4)] hover:bg-green-500 transition-all disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {actionLoading ? (
                    <><span className="w-4 h-4 rounded-full border-2 border-white/50 border-t-white animate-spin"></span> Processing...</>
                  ) : "Approve & Schedule"}
                </button>
              </>
            )}
          </div>
        </div>

        {isError && (
          <div className="mb-2 glass-panel p-6 rounded-xl border border-red-500/50 bg-red-500/10 animate-in fade-in slide-in-from-top-4">
            <h3 className="text-red-400 font-bold mb-2 flex items-center gap-2">
              <span className="text-xl">⚠️</span> Pipeline Execution Failed
            </h3>
            <div className="bg-slate-900/80 p-4 rounded-lg border border-red-500/30">
              <p className="text-slate-300 text-sm font-mono whitespace-pre-wrap">{data?.feedback || "Unknown error occurred during generation."}</p>
            </div>
            <p className="text-xs text-slate-400 mt-4">Vui lòng thử lại sau hoặc tải lại trang.</p>
          </div>
        )}

        {isRejecting && !isError && (
          <div className="mb-2 glass-panel p-6 rounded-xl border border-red-500/30 animate-in fade-in slide-in-from-top-4">
            <h3 className="text-red-400 font-bold mb-2">Provide Feedback for Rewrite</h3>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="e.g. Make the tone more professional, or change the image to be more colorful..."
              className="w-full bg-slate-900/50 border border-slate-700 rounded-lg p-3 text-white mb-4 h-24 focus:ring-1 focus:ring-red-500 outline-none"
            />
            <div className="flex justify-end gap-3">
              <button onClick={() => setIsRejecting(false)} className="text-slate-400 hover:text-white px-4">Cancel</button>
              <button
                onClick={() => handleReview("REJECT")}
                disabled={!feedback || actionLoading}
                className="bg-red-600 hover:bg-red-500 text-white px-6 py-2 rounded-lg font-medium disabled:opacity-50 flex items-center gap-2"
              >
                {actionLoading && <span className="w-4 h-4 rounded-full border-2 border-white/50 border-t-white animate-spin"></span>}
                Submit Feedback
              </button>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-6">
            {/* Topic Section */}
            <div className="glass-panel p-6 rounded-xl border border-white/5 shadow-md">
              <h2 className="text-lg font-bold mb-4 text-indigo-400 flex items-center gap-2">
                <span className="text-xl">🔍</span> AI Topic Suggestions
                {status === "START" && <span className="ml-auto w-4 h-4 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></span>}
              </h2>
              <div className="space-y-4">
                {data?.topic_reasoning && (
                  <div className="border border-slate-800 rounded-lg overflow-hidden animate-in fade-in zoom-in-95 duration-500">
                    <button
                      onClick={() => setExpandedReasoning(prev => ({ ...prev, topic: !prev.topic }))}
                      className="w-full flex items-center justify-between px-3 py-1.5 bg-slate-900/80 hover:bg-slate-800 transition-colors text-[10px] text-slate-500 font-bold uppercase tracking-tighter"
                    >
                      <span className="flex items-center gap-2">
                        <span className="opacity-50">AI Reasoning</span>
                        {status === "START" && <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></span>}
                      </span>
                      <span>{expandedReasoning.topic ? "Collapse ↑" : "Expand ↓"}</span>
                    </button>
                    {expandedReasoning.topic && (
                      <div className="p-3 bg-slate-900/30 text-[10px] text-slate-500 italic leading-relaxed animate-in slide-in-from-top-1 duration-200">
                        {data.topic_reasoning}
                      </div>
                    )}
                  </div>
                )}
                {!data?.selected_title ? (
                  <div className="space-y-3 animate-pulse">
                    <div className="h-16 bg-slate-800/50 rounded-lg w-full"></div>
                    <div className="h-32 bg-slate-800/30 rounded-lg w-full border border-slate-700/50"></div>
                  </div>
                ) : (
                  <div className="p-4 bg-indigo-500/10 border border-indigo-500/30 rounded-lg animate-in fade-in zoom-in-95 duration-500">
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-xs font-bold text-indigo-400 uppercase tracking-wider">Selected Primary Topic</p>
                      {data.selected_title && (
                        <button
                          onClick={() => copyToClipboard(data.selected_title, "topic")}
                          className="text-[10px] text-indigo-400 hover:text-indigo-300 font-bold uppercase transition-colors"
                        >
                          {copiedPlatform === "topic" ? "✅ Copied!" : "📋 Copy"}
                        </button>
                      )}
                    </div>
                    <p className="text-base font-medium">{data.selected_title}</p>
                  </div>
                )}
              </div>
            </div>

            {/* Brief Section */}
            <div className="glass-panel p-6 rounded-xl border border-white/5 shadow-md">
              <h2 className="text-lg font-bold mb-4 text-indigo-400 flex items-center gap-2">
                <span className="text-xl">📚</span> Research Brief
                {status === "RESEARCHING" && <span className="ml-auto w-4 h-4 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></span>}
              </h2>
              <div className="space-y-4">
                {data?.brief_reasoning && (
                  <div className="border border-slate-800 rounded-lg overflow-hidden animate-in fade-in zoom-in-95 duration-500">
                    <button
                      onClick={() => setExpandedReasoning(prev => ({ ...prev, brief: !prev.brief }))}
                      className="w-full flex items-center justify-between px-3 py-1.5 bg-slate-900/80 hover:bg-slate-800 transition-colors text-[10px] text-slate-500 font-bold uppercase tracking-tighter"
                    >
                      <span className="flex items-center gap-2">
                        <span className="opacity-50">AI Reasoning</span>
                        {status === "RESEARCHING" && <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></span>}
                      </span>
                      <span>{expandedReasoning.brief ? "Collapse ↑" : "Expand ↓"}</span>
                    </button>
                    {expandedReasoning.brief && (
                      <div className="p-3 bg-slate-900/30 text-[10px] text-slate-500 italic leading-relaxed animate-in slide-in-from-top-1 duration-200">
                        {data.brief_reasoning}
                      </div>
                    )}
                  </div>
                )}
                {!data?.research_brief ? (
                  <div className="space-y-3 animate-pulse pt-2">
                    <div className="h-3 bg-slate-800/60 rounded w-3/4"></div>
                    <div className="h-3 bg-slate-800/60 rounded w-full"></div>
                    <div className="h-3 bg-slate-800/60 rounded w-full"></div>
                    <div className="h-3 bg-slate-800/60 rounded w-5/6"></div>
                    <div className="h-3 bg-slate-800/60 rounded w-1/2"></div>
                  </div>
                ) : (
                  <pre
                    ref={briefScrollRef}
                    className="whitespace-pre-wrap font-sans text-xs bg-slate-900/50 p-4 rounded-lg border border-slate-800 max-h-64 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700 animate-in fade-in zoom-in-95 duration-500"
                  >
                    {data.research_brief}
                  </pre>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            {/* Posts Section */}
            <div className="glass-panel p-6 rounded-xl border border-white/5 shadow-md relative">
              <h2 className="text-lg font-bold mb-4 text-indigo-400 flex items-center gap-2">
                <span className="text-xl">✍️</span> Generated Posts
                {status === "WRITING" && <span className="ml-auto w-4 h-4 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></span>}
              </h2>

              {status === "QUALITY_ASSURANCE" && (
                <div className="absolute top-4 right-4 bg-purple-500/20 border border-purple-500/50 text-purple-300 text-[10px] uppercase font-bold tracking-wider px-3 py-1 rounded-full animate-pulse flex items-center gap-2 shadow-[0_0_10px_rgba(168,85,247,0.3)]">
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-400"></span> QA Checking
                </div>
              )}

              {(() => {
                const allPlatforms = [...new Set([
                  ...Object.keys(data?.reasoning || {}),
                  ...Object.keys(data?.post_contents || {}),
                ])];
                if (allPlatforms.length === 0) {
                  return (
                    <div className="space-y-4 animate-pulse">
                      <div className="h-40 bg-slate-800/40 rounded-lg w-full border border-slate-700/30"></div>
                      <div className="h-40 bg-slate-800/40 rounded-lg w-full border border-slate-700/30"></div>
                    </div>
                  );
                }
                return (
                  <div
                    ref={postsScrollRef}
                    className="space-y-4 max-h-[500px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-700 animate-in fade-in zoom-in-95 duration-500"
                  >
                    {allPlatforms.map((platform) => (
                      <div key={platform} className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50 shadow-inner">
                        <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
                          <h3 className="font-bold text-sm bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded">{platform}</h3>
                          <div className="flex items-center gap-3">
                            {data.post_contents?.[platform] && status === "APPROVED" && (
                              <button
                                onClick={() => copyToClipboard(data.post_contents[platform], platform)}
                                className="text-[10px] text-indigo-400 hover:text-indigo-300 font-bold uppercase flex items-center gap-1 transition-colors"
                              >
                                {copiedPlatform === platform ? "✅ Copied!" : "📋 Copy Content"}
                              </button>
                            )}
                            <span className="text-[10px] bg-slate-800 px-2 py-1 rounded-full text-slate-400 font-medium">
                              {data.scheduled_times?.[platform] ? `Scheduled: ${data.scheduled_times[platform]}` : "Pending Schedule"}
                            </span>
                          </div>
                        </div>

                        {data.reasoning?.[platform] && (
                          <div className="mb-4 border border-slate-800 rounded-lg overflow-hidden">
                            <button
                              onClick={() => setExpandedReasoning(prev => ({ ...prev, [platform]: !prev[platform] }))}
                              className="w-full flex items-center justify-between px-3 py-1.5 bg-slate-950/80 hover:bg-slate-900 transition-colors text-[10px] text-slate-600 font-bold uppercase tracking-tighter"
                            >
                              <span className="flex items-center gap-2">
                                <span className="opacity-50">AI Reasoning</span>
                                {status === "WRITING" && !data.post_contents?.[platform] && <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></span>}
                              </span>
                              <span>{expandedReasoning[platform] ? "Collapse ↑" : "Expand ↓"}</span>
                            </button>
                            {expandedReasoning[platform] && (
                              <div className="p-3 bg-slate-950/30 text-[10px] text-slate-600 italic leading-relaxed animate-in slide-in-from-top-1 duration-200">
                                {data.reasoning[platform]}
                              </div>
                            )}
                          </div>
                        )}

                        {data.post_contents?.[platform] ? (
                          <pre className="whitespace-pre-wrap font-sans text-sm text-slate-300 leading-relaxed">{data.post_contents[platform]}</pre>
                        ) : (
                          <div className="space-y-2 animate-pulse pt-1">
                            <div className="h-3 bg-slate-800/60 rounded w-3/4"></div>
                            <div className="h-3 bg-slate-800/60 rounded w-full"></div>
                            <div className="h-3 bg-slate-800/60 rounded w-full"></div>
                            <div className="h-3 bg-slate-800/60 rounded w-5/6"></div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>

            {/* Image Section */}
            <div className="glass-panel p-6 rounded-xl border border-white/5 shadow-md">
              <h2 className="text-lg font-bold mb-4 text-indigo-400 flex items-center gap-2">
                <span className="text-xl">🎨</span> Generated Image
                {status === "GENERATING_IMAGE" && <span className="ml-auto w-4 h-4 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></span>}
              </h2>
              {!data?.image_url ? (
                <div className="aspect-square bg-slate-800/30 rounded-lg flex flex-col items-center justify-center border-2 border-dashed border-slate-700 animate-pulse">
                  <span className="text-4xl mb-2 opacity-50">🖼️</span>
                  <span className="text-slate-500 text-xs font-medium">Image Generation Pending...</span>
                </div>
              ) : (
                <div className="animate-in fade-in zoom-in-95 duration-500">
                  <div className="rounded-lg overflow-hidden border border-slate-700/50 shadow-xl group relative">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={data.image_url} alt="Generated for post" className="w-full h-auto object-cover transition-transform duration-700 group-hover:scale-105" />
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-900/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                  </div>
                  <div className="mt-4 bg-slate-900/50 p-3 rounded-lg border border-slate-800 relative">
                    <span className="absolute -top-2 left-3 bg-slate-800 text-[10px] text-slate-400 px-2 rounded-full border border-slate-700">Prompt</span>
                    <p className="text-xs text-slate-300 leading-relaxed mt-1">
                      {data.image_prompt}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div ref={bottomRef} className="h-4" />
      
      {/* Add sliding animation for the progress bar */}
      <style dangerouslySetInnerHTML={{
        __html: `
        @keyframes slide {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(300%); }
        }
      `}} />
    </main>
  );
}
