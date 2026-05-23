"use client";

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
  Activity,
  Plus,
  LayoutDashboard,
  FolderGit2,
  Network,
  LineChart,
  Settings
} from "lucide-react";

type PanelType = "chat" | "diff" | "files" | "terminal";

const RIGHT_PANEL_TABS = [
  { id: "chat" as PanelType, icon: MessageSquare, label: "Chat" },
  { id: "diff" as PanelType, icon: GitPullRequest, label: "Diffs" },
  { id: "files" as PanelType, icon: FileCode, label: "Files" },
  { id: "terminal" as PanelType, icon: TerminalIcon, label: "Logs" },
];

export default function DashboardPage() {
  const { status, messages, addMessage, isStreaming, clearMessages, resetStatus } = useAgentStore();
  const { activePanel, setActivePanel } = useUIStore();
  
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;

    const userInput = input.trim();

    addMessage({
      id: Date.now().toString(),
      role: "user",
      content: userInput,
      timestamp: new Date(),
    });

    addMessage({
      id: (Date.now() + 1).toString(),
      role: "agent",
      content: "ATLAS received your request. Backend execution engine not connected yet.",
      timestamp: new Date(),
    });

    setInput("");
    setTimeout(() => {
      inputRef.current?.focus();
    }, 100);
  };

  const handleNewTask = () => {
    if (clearMessages) clearMessages();
    if (resetStatus) resetStatus();
    setInput("");
    setActivePanel("chat");
    setTimeout(() => {
      inputRef.current?.focus();
    }, 100);
  };

  const hasActiveTask = messages.length > 0;

  return (
    <div className="flex h-screen w-full bg-background text-foreground overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border bg-background/50 flex flex-col backdrop-blur-sm hidden md:flex shrink-0">
        <div className="h-14 border-b border-border flex items-center px-6">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gradient-to-br from-accent to-accent-secondary flex items-center justify-center">
              <span className="text-white font-bold text-[10px]">A</span>
            </div>
            <span className="font-semibold tracking-wide">ATLAS</span>
          </div>
        </div>

        <div className="p-4 border-b border-border/50">
          <button
            onClick={handleNewTask}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-accent text-accent-foreground rounded-md hover:bg-accent/90 transition-colors text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            New Task
          </button>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <div className="text-xs font-semibold text-muted-foreground/70 mb-3 px-3 uppercase tracking-wider">
            Platform
          </div>
          <button className="w-full flex items-center gap-3 px-3 py-2.5 bg-accent/10 text-accent rounded-md text-sm font-medium transition-colors">
            <LayoutDashboard className="w-4 h-4" />
            Dashboard
          </button>
          
          {/* Placeholder/Disabled Routes */}
          {[
            { icon: FolderGit2, label: "Repositories" },
            { icon: Network, label: "Agents" },
            { icon: LineChart, label: "Analytics" },
            { icon: Settings, label: "Settings" },
          ].map((item) => (
            <button
              key={item.label}
              disabled
              className="w-full flex items-center gap-3 px-3 py-2.5 text-muted-foreground hover:text-foreground hover:bg-white/[0.05] rounded-md text-sm transition-colors cursor-not-allowed group"
            >
              <item.icon className="w-4 h-4 opacity-70" />
              <span className="flex-1 text-left opacity-70">{item.label}</span>
              <span className="text-[9px] uppercase tracking-wider bg-white/10 px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity">
                Soon
              </span>
            </button>
          ))}
        </nav>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Bar */}
        <header className="h-14 border-b border-border flex items-center justify-between px-6 bg-background/50 backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <StatusIndicator
              status={status || "idle"}
              size="sm"
              showLabel
            />
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Server className="w-3.5 h-3.5" />
              <span>System Ready</span>
            </div>
            <div className="w-px h-4 bg-border" />
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Activity className="w-3.5 h-3.5" />
              <span>{hasActiveTask ? "Processing" : "Idle"}</span>
            </div>
          </div>
        </header>

        {/* Workspace */}
        <div className="flex-1 flex overflow-hidden">
          {/* Chat / Main Panel */}
          <div className="flex-1 flex flex-col min-w-0 bg-background/30">
            {/* Task Info */}
            <div className="px-6 py-4 border-b border-border transition-colors">
              {hasActiveTask ? (
                <>
                  <div className="flex items-center gap-3 mb-2">
                    <GitBranch className="w-4 h-4 text-accent" />
                    <span className="text-sm font-mono text-accent">atlas/execution</span>
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

            {/* Messages */}
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
                {messages.map((msg, i) => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
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
                        <span className="text-xs text-muted-foreground">
                          {msg.timestamp && !isNaN(new Date(msg.timestamp).getTime())
                            ? new Date(msg.timestamp).toLocaleTimeString()
                            : "--:--:--"}
                        </span>
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
                ))}
              </AnimatePresence>
              
              {/* Invisible element to anchor the auto-scroll */}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-border bg-background">
              <div className="glass-panel flex items-center gap-3 px-4 py-3 border border-border/50 rounded-lg focus-within:border-accent/50 focus-within:ring-1 focus-within:ring-accent/50 transition-all">
                <input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder="Ask ATLAS to build or modify something..."
                  className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/50"
                  autoFocus
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

            {/* Terminal (Always Visible for MVP) */}
            <div className="h-64 border-t border-border overflow-hidden bg-background shrink-0">
              <Terminal logs={[]} live={false} title="atlas-executor.log [STANDBY]" />
            </div>
          </div>

          {/* Right Panel */}
          <div className="w-80 border-l border-border bg-background/50 backdrop-blur-sm flex flex-col shrink-0 hidden lg:flex">
            {/* Tabs */}
            <div className="flex border-b border-border">
              {RIGHT_PANEL_TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActivePanel(tab.id)}
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

            {/* Panel Content (Empty States for MVP) */}
            <div className="flex-1 overflow-auto p-4 flex flex-col">
              {activePanel === "chat" && (
                <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground space-y-3 opacity-50">
                  <MessageSquare className="w-8 h-8" />
                  <p className="text-xs">Agent thoughts will appear here</p>
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
                <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground space-y-3 opacity-50">
                  <TerminalIcon className="w-8 h-8" />
                  <p className="text-xs">Awaiting execution logs</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
