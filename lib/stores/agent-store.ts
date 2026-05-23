import { create } from "zustand";
import { AgentMessage } from "@/types"; // Adjust import path if needed

type AgentStatus = "idle" | "working" | "complete" | "error";

interface AgentStore {
  status: AgentStatus;
  messages: AgentMessage[];
  isStreaming: boolean;
  
  // Actions
  setStatus: (status: AgentStatus) => void;
  addMessage: (message: AgentMessage) => void;
  resetTask: () => void;
}

export const useAgentStore = create<AgentStore>((set) => ({
  status: "idle",
  messages: [],
  isStreaming: false,

  setStatus: (status) => set({ status }),
  
  addMessage: (message) => 
    set((state) => ({
      messages: [...state.messages, message],
    })),

  // Unified reset method to clear the dashboard
  resetTask: () =>
    set({
      messages: [],
      status: "idle",
      isStreaming: false,
    }),
}));
