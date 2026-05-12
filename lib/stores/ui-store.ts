import { create } from "zustand";

interface UIStore {
  sidebarOpen: boolean;
  rightPanelOpen: boolean;
  terminalOpen: boolean;
  theme: "dark" | "light" | "system";
  activePanel: "chat" | "logs" | "diff" | "terminal";
  
  toggleSidebar: () => void;
  toggleRightPanel: () => void;
  toggleTerminal: () => void;
  setActivePanel: (panel: UIStore["activePanel"]) => void;
  setTheme: (theme: UIStore["theme"]) => void;
}

export const useUIStore = create<UIStore>((set) => ({
  sidebarOpen: true,
  rightPanelOpen: true,
  terminalOpen: true,
  theme: "dark",
  activePanel: "chat",
  
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  toggleRightPanel: () => set((s) => ({ rightPanelOpen: !s.rightPanelOpen })),
  toggleTerminal: () => set((s) => ({ terminalOpen: !s.terminalOpen })),
  setActivePanel: (panel) => set({ activePanel: panel }),
  setTheme: (theme) => set({ theme }),
}));
