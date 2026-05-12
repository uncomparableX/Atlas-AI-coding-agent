export interface Repository {
  id: string;
  name: string;
  owner: string;
  url: string;
  defaultBranch: string;
  language: string;
  lastSynced: Date;
  status: "syncing" | "ready" | "error";
}

export interface FileNode {
  id: string;
  name: string;
  type: "file" | "directory";
  path: string;
  children?: FileNode[];
  language?: string;
  size?: number;
  lastModified?: Date;
}

export interface AgentTask {
  id: string;
  title: string;
  description: string;
  status: "pending" | "planning" | "coding" | "reviewing" | "complete" | "failed";
  repositoryId: string;
  branch: string;
  createdAt: Date;
  updatedAt: Date;
  progress: number;
  tokensUsed: number;
  executionTime: number;
  logs: LogEntry[];
  diffs: CodeDiff[];
  thoughts: Thought[];
}

export interface LogEntry {
  id: string;
  timestamp: Date;
  level: "info" | "warn" | "error" | "debug" | "success";
  message: string;
  source: string;
  metadata?: Record<string, unknown>;
}

export interface CodeDiff {
  id: string;
  filePath: string;
  oldContent: string;
  newContent: string;
  additions: number;
  deletions: number;
  status: "pending" | "applied" | "rejected";
}

export interface Thought {
  id: string;
  timestamp: Date;
  content: string;
  type: "plan" | "reasoning" | "reflection" | "action";
}

export interface AgentMessage {
  id: string;
  role: "user" | "agent" | "system";
  content: string;
  timestamp: Date;
  attachments?: Attachment[];
}

export interface Attachment {
  type: "file" | "diff" | "image" | "link";
  content: string;
  name: string;
}

export interface ExecutionMetrics {
  timestamp: Date;
  tokensUsed: number;
  latency: number;
  success: boolean;
  memoryUsage: number;
  cost: number;
}

export interface AgentStatus {
  state: "idle" | "thinking" | "coding" | "waiting" | "error";
  currentTask?: string;
  progress: number;
  lastActivity: Date;
}

export interface DockerSandbox {
  id: string;
  status: "creating" | "running" | "paused" | "destroyed";
  containerId: string;
  resources: {
    cpu: number;
    memory: number;
    disk: number;
  };
  uptime: number;
}
