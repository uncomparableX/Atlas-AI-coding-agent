"use client";

import { Shell } from "@/components/layout/shell";
import { Sidebar } from "@/components/layout/sidebar";
import { GlassCard } from "@/components/glass/glass-card";
import { Terminal } from "@/components/terminal/terminal";
import { StatusIndicator } from "@/components/agent/status-indicator";
import { StreamingText } from "@/components/motion/streaming-text";
import { useAgentStore } from "@/lib/stores/agent-store";
import { useUIStore } from "@/lib/stores/ui-store";
import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import {
  Send,
  Bot,
  User,
  GitBranch,
  Clock,
  Cpu,
  MessageSquare,
  FileCode,
  Terminal as TerminalIcon,
  GitPullRequest,
} from "lucide-react";
import { AgentMessage, LogEntry } from "@/types";

// Mock data
const mockLogs: LogEntry[] = [
  {
    id: "1",
    timestamp: new Date(),
    level: "info",
    message: "Initializing agent environment...",
    source: "bootstrap",
  },
  {
    id: "2",
    timestamp: new Date(),
    level: "success",
    message: "Docker sandbox created: container_7f3a9d",
    source: "sandbox",
  },
  {
    id: "3",
    timestamp: new Date(),
    level: "info",
    message: "Cloning repository github.com/acme/webapp",
    source: "git",
  },
  {
    id: "4",
    timestamp: new Date(),
    level: "debug",
    message: "Analyzing 1,247 files for context...",
    source: "indexer",
  },
  {
    id: "5",
    timestamp: new Date(),
    level: "info",
    message: "Task planning complete. 12 steps identified.",
    source: "planner",
  },
];

const mockMessages: AgentMessage[] = [
  {
    id: "1",
    role: "user",
    content: "Implement OAuth2 authentication with Google and GitHub providers",
    timestamp: new Date(Date.now() - 1000 * 60 * 5),
  },
  {
    id: "2",
    role: "agent",
    content: "I'll implement OAuth2 authentication for your application. Let me start by analyzing the current codebase structure and existing auth patterns.",
    timestamp: new Date(Date.now() - 1000 * 60 * 4),
  },
  {
    id: "3",
    role: "agent",
    content: "Found existing passport.js setup in src/auth/. I'll extend it with Google and GitHub strategies. Creating implementation plan...",
    timestamp: new Date(Date.now() - 1000 * 60 * 3),
  },
];

export default function DashboardPage() {
  const { status, messages, addMessage, isStreaming } = useAgentStore();
  const { terminalOpen, activePanel, setActivePanel } = useUIStore();
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (!input.trim()) return;
    addMessage({
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date(),
    });
    setInput("");
  };

  return (
    <Shell>
      <Sidebar />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Bar */}
        <header className="h-14 border-b border-border flex items-center justify-between px-6 bg-background/50 backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <StatusIndicator
              status={status}
              size="sm"
              showLabel
            />
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Cpu className="w-3.5 h-3.5" />
              <span>2.4 GB / 8 GB</span>
            </div>
            <div className="w-px h-4 bg-border" />
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Clock className="w-3.5 h-3.5" />
              <span>12m 34s</span>
            </div>
          </div>
        </header>

        {/* Workspace */}
        <div className="flex-1 flex overflow-hidden">
          {/* Chat / Main Panel */}
          <div className="flex-1 flex flex-col min-w-0">
            {/* Task Info */}
            <div className="px-6 py-4 border-b border-border">
              <div className="flex items-center gap-3 mb-2">
                <GitBranch className="w-4 h-4 text-accent" />
                <span className="text-sm font-mono text-accent">feature/oauth2-auth</span>
                <span className="text-xs text-muted-foreground">from main</span>
              </div>
              <h2 className="text-lg font-semibold">Implement OAuth2 authentication</h2>
              <p className="text-sm text-muted-foreground mt-1">
                Add Google and GitHub OAuth2 providers with JWT session management
              </p>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-auto px-6 py-4 space-y-6">
              <AnimatePresence>
                {messages.map((msg, i) => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.1 }}
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
                          {msg.role === "user" ? "You" : "Agent"}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {msg.timestamp.toLocaleTimeString()}
                        </span>
                      </div>
                      <div className="text-sm text-foreground leading-relaxed">
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
            </div>

            {/* Input */}
            <div className="p-4 border-t border-border">
              <div className="glass-panel flex items-center gap-3 px-4 py-3">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSend()}
                  placeholder="Ask the agent to do something..."
                  className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/50"
                />
                <button
                  onClick={handleSend}
                  className="p-2 rounded-lg bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Terminal (Collapsible) */}
            <AnimatePresence>
              {terminalOpen && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 280, opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  className="border-t border-border overflow-hidden"
                >
                  <Terminal logs={mockLogs} live title="agent.log" />
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Right Panel */}
          <div className="w-80 border-l border-border bg-background/30 backdrop-blur-sm flex flex-col">
            {/* Tabs */}
            <div className="flex border-b border-border">
              {[
                { id: "chat", icon: MessageSquare, label: "Chat" },
                { id: "diff", icon: GitPullRequest, label: "Diffs" },
                { id: "files", icon: FileCode, label: "Files" },
                { id: "terminal", icon: TerminalIcon, label: "Logs" },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActivePanel(tab.id as any)}
                  className={`flex-1 flex items-center justify-center gap-2 py-3 text-xs transition-colors ${
                    activePanel === tab.id
                      ? "text-accent border-b-2 border-accent bg-accent/5"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <tab.icon className="w-3.5 h-3.5" />
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Panel Content */}
            <div className="flex-1 overflow-auto p-4">
              {activePanel === "diff" && (
                <div className="space-y-3">
                  <GlassCard className="p-3">
                    <div className="text-xs font-mono text-foreground mb-1">src/auth/oauth.ts</div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-terminal-green">+142</span>
                      <span className="text-error">-12</span>
                    </div>
                  </GlassCard>
                  <GlassCard className="p-3">
                    <div className="text-xs font-mono text-foreground mb-1">src/middleware/auth.ts</div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-terminal-green">+89</span>
                      <span className="text-error">-3</span>
                    </div>
                  </GlassCard>
                </div>
              )}

              {activePanel === "files" && (
                <div className="space-y-2">
                  {["src/auth/oauth.ts", "src/auth/strategies/google.ts", "src/auth/strategies/github.ts", "src/middleware/auth.ts", "src/types/auth.d.ts"].map((file) => (
                    <div
                      key={file}
                      className="flex items-center gap-2 px-2 py-1.5 rounded-md text-xs text-muted-foreground hover:text-foreground hover:bg-white/[0.03] cursor-pointer"
                    >
                      <FileCode className="w-3.5 h-3.5" />
                      <span className="truncate">{file}</span>
                    </div>
                  ))}
                </div>
              )}

              {activePanel === "terminal" && (
                <div className="space-y-2 font-mono text-[10px]">
                  {mockLogs.slice(-5).map((log) => (
                    <div key={log.id} className="text-muted-foreground">
                      <span className="text-accent/50">[{log.source}]</span> {log.message}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
