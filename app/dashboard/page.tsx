"use client";

import { Shell } from "@/components/layout/shell";
import { Sidebar } from "@/components/layout/sidebar";
import { Terminal } from "@/components/terminal/terminal";
import { StatusIndicator } from "@/components/agent/status-indicator";
import { StreamingText } from "@/components/motion/streaming-text";
import { useAgentStore } from "@/lib/stores/agent-store";
import { useUIStore } from "@/lib/stores/ui-store";
import { motion, AnimatePresence } from "framer-motion";
import { useState, useRef, useEffect } from "react";
import {
  Send,
  Bot,
  User,
  GitBranch,
  MessageSquare,
  FileCode,
  Terminal as TerminalIcon,
  GitPullRequest,
  Server,
  Activity
} from "lucide-react";

type PanelType = "chat" | "diff" | "files" | "terminal";

export default function DashboardPage() {
  const { status, messages, addMessage, isStreaming, setStatus } = useAgentStore();
  const { activePanel, setActivePanel } = useUIStore();
  const [input, setInput] = useState("");
  const [localLogs, setLocalLogs] = useState<{ id: string; timestamp: Date; level: string; message: string; source: string }[]>([]);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, localLogs]);

  const handleSend = () => {
    if (!input.trim()) return;

    const userInput = input;
    addMessage({
      id: Date.now().toString(),
      role: "user",
      content: userInput,
      timestamp: new Date(),
    });
    
    setInput("");
    if (setStatus) setStatus("working");
    setActivePanel("chat");

    setTimeout(() => {
      setLocalLogs(prev => [...prev, { id: Date.now().toString(), timestamp: new Date(), level: "info", message: "Task received. Initializing planner...", source: "ATLAS-Core" }]);
      addMessage({ id: (Date.now() + 1).toString(), role: "agent", content: "Planning...", timestamp: new Date() });
    }, 600);

    setTimeout(() => {
      setLocalLogs(prev => [...prev, { id: Date.now().toString(), timestamp: new Date(), level: "info", message: "Generating execution steps and applying changes...", source: "ATLAS-Builder" }]);
      addMessage({ id: (Date.now() + 2).toString(), role: "agent", content: "Generating code...", timestamp: new Date() });
    }, 2000);

    setTimeout(() => {
      setLocalLogs(prev => [...prev, { id: Date.now().toString(), timestamp: new Date(), level: "success", message: "Task executed successfully.", source: "ATLAS-Executor" }]);
      addMessage({ id: (Date.now() + 3).toString(), role: "agent", content: "Completed. The modifications have been applied.", timestamp: new Date() });
      if (setStatus) setStatus("idle");
    }, 4000);
  };

  const hasActiveTask = messages.length > 0;

  return (
    <div className="flex h-screen w-full bg-background text-foreground overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 bg-background/50">
        <header className="h-14 border-b border-border flex items-center justify-between px-6 bg-background/50 backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <StatusIndicator status={status || "idle"} size="sm" showLabel />
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Server className="w-3.5 h-3.5" />
              <span>System Ready</span>
            </div>
            <div className="w-px h-4 bg-border" />
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Activity className="w-3.5 h-3.5" />
              <span>{status === "working" ? "Processing" : "Idle"}</span>
            </div>
          </div>
        </header>

        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 flex flex-col min-w-0">
            <div className="px-6 py-4 border-b border-border transition-colors">
              {hasActiveTask ? (
                <>
                  <div className="flex items-center gap-3 mb-2">
                    <GitBranch className="w-4 h-4 text-accent" />
                    <span className="text-sm font-mono text-accent">atlas/workspace</span>
                    <span className="text-xs text-muted-foreground">active task</span>
                  </div>
                  <h2 className="text-lg font-semibold">Active Execution</h2>
                  <p className="text-sm text-muted-foreground mt-1 truncate">
                    {messages[0]?.content || "Awaiting instructions..."}
                  </p>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-3 mb-2 opacity-50">
                    <Bot className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm font-mono text-muted-foreground">standby</span>
                  </div>
                  <h2 className="text-lg font-semibold text-muted-foreground">No active task</h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    Describe your software engineering task below to initialize agents.
                  </p>
                </>
              )}
            </div>

            <div className="flex-1 overflow-auto px-6 py-4 space-y-6">
              {!hasActiveTask && (
                <div className="h-full flex flex-col items-center justify-center text-center opacity-50 space-y-4">
                  <Bot className="w-12 h-12 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">ATLAS is ready</p>
                    <p className="text-xs text-muted-foreground mt-1">Describe what you want to build or modify.</p>
                  </div>
                </div>
              )}
              <AnimatePresence initial={false}>
                {messages.map((msg, i) => {
                  const safeTime = msg.timestamp && !isNaN(new Date(msg.timestamp).getTime())
                    ? new Date(msg.timestamp).toLocaleTimeString()
                    : "--:--";

                  return (
                    <motion.div
                      key={msg.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="flex gap-4"
                    >
                      <div className="shrink-0">
                        {msg.role === "user" ? (
                          <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
                            <User className="w-4 h-4 text-foreground" />
                          </div>
                        ) : (
                          <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center">
                            <Bot className="w-4 h-4 text-accent" />
                          </div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-medium">
                            {msg.role === "user" ? "You" : "ATLAS"}
                          </span>
                          <span className="text-xs text-muted-foreground">{safeTime}</span>
                        </div>
                        <div className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                          {msg.role === "agent" && i === messages.length - 1 && isStreaming ? (
                            <StreamingText text={msg.content} speed={20} />
                          ) : (
                            msg.content
                          )}
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
              <div ref={messagesEndRef} />
            </div>

            <div className="p-4 border-t border-border bg-background">
              <div className="glass-panel flex items-center gap-3 px-4 py-3">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSend()}
                  placeholder="Ask ATLAS to build or modify something..."
                  className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/50"
                />
                <button
                  onClick={handleSend}
                  disabled={!input.trim()}
                  className="p-2 rounded-lg bg-accent/10 text-accent hover:bg-accent/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="h-64 border-t border-border overflow-hidden bg-background shrink-0">
              <Terminal logs={localLogs} live={status === "working"} title={status === "working" ? "atlas-executor.log [LIVE]" : "atlas-executor.log [STANDBY]"} />
            </div>
          </div>

          <div className="w-80 border-l border-border bg-background/50 backdrop-blur-sm flex flex-col shrink-0 hidden lg:flex">
            <div className="flex border-b border-border">
              {[
                { id: "chat", icon: MessageSquare, label: "Chat" },
                { id: "diff", icon: GitPullRequest, label: "Diffs" },
                { id: "files", icon: FileCode, label: "Files" },
                { id: "terminal", icon: TerminalIcon, label: "Logs" },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActivePanel(tab.id as PanelType)}
                  className={`flex-1 flex items-center justify-center gap-2 py-3 text-xs transition-colors ${
                    activePanel === tab.id
                      ? "text-accent border-b-2 border-accent bg-accent/5"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <tab.icon className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">{tab.label}</span>
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-auto p-4 flex flex-col">
              {activePanel === "chat" && (
                <div className="flex-1 overflow-auto space-y-4">
                   {messages.map((msg) => (
                     <div key={`side-${msg.id}`} className="text-sm border-b border-white/5 pb-2">
                       <span className={`font-semibold ${msg.role === 'user' ? 'text-foreground' : 'text-accent'}`}>{msg.role === 'user' ? 'You:' : 'ATLAS:'}</span>
                       <p className="text-muted-foreground mt-1 whitespace-pre-wrap">{msg.content}</p>
                     </div>
                   ))}
                   {messages.length === 0 && (
                     <div className="h-full flex flex-col items-center justify-center text-muted-foreground opacity-50 space-y-2">
                       <MessageSquare className="w-8 h-8" />
                       <p className="text-xs">Agent thoughts will appear here</p>
                     </div>
                   )}
                </div>
              )}

              {activePanel === "diff" && (
                <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground space-y-3 opacity-50">
                  <GitPullRequest className="w-8 h-8" />
                  <p className="text-xs">No diffs generated yet</p>
                </div>
              )}

              {activePanel === "files" && (
                <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground space-y-3 opacity-50">
                  <FileCode className="w-8 h-8" />
                  <p className="text-xs">No files modified yet</p>
                </div>
              )}

              {activePanel === "terminal" && (
                <div className="flex-1 overflow-auto space-y-2 font-mono text-[10px]">
                  {localLogs.length > 0 ? localLogs.map((log) => (
                    <div key={`panel-${log.id}`} className="text-muted-foreground">
                      <span className="text-accent/50">[{log.source}]</span> {log.message}
                    </div>
                  )) : (
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground opacity-50 space-y-2">
                      <TerminalIcon className="w-8 h-8" />
                      <p className="text-xs text-center">Awaiting execution logs</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
