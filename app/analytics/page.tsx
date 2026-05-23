"use client";

import { Sidebar } from "@/components/layout/sidebar";
import { GlassCard } from "@/components/glass/glass-card";
import { Zap, Activity } from "lucide-react";

export default function AnalyticsPage() {
  return (
    <div className="flex h-screen w-full bg-background text-foreground overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 bg-background/50">
        <div className="h-14 border-b border-border flex items-center px-6 bg-background/50 backdrop-blur-sm">
          <Activity className="w-4 h-4 text-accent mr-2" />
          <h1 className="font-semibold tracking-wide">ATLAS Usage Dashboard</h1>
        </div>

        <div className="p-6 max-w-3xl mx-auto w-full mt-8">
          <GlassCard className="p-8">
            <div className="flex items-center gap-3 mb-8">
              <div className="p-3 bg-accent/10 rounded-lg">
                <Zap className="w-6 h-6 text-accent" />
              </div>
              <div>
                <h2 className="text-2xl font-bold">ATLAS Credits</h2>
                <p className="text-sm text-muted-foreground">Manage your workspace execution limits.</p>
              </div>
            </div>

            <div className="mb-10">
              <div className="flex justify-between text-sm mb-3">
                <span className="text-foreground font-medium">Credits Remaining</span>
                <span className="text-accent font-mono font-bold">78%</span>
              </div>
              <div className="h-3 w-full bg-white/5 rounded-full overflow-hidden border border-white/10">
                <div className="h-full bg-accent w-[78%] rounded-full shadow-[0_0_15px_rgba(var(--accent),0.5)]" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div className="p-6 rounded-lg bg-white/5 border border-white/10 flex flex-col items-center text-center">
                <div className="text-sm text-muted-foreground mb-2">Requests Used Today</div>
                <div className="text-4xl font-bold text-foreground">43</div>
              </div>
              <div className="p-6 rounded-lg bg-white/5 border border-white/10 flex flex-col items-center text-center">
                <div className="text-sm text-muted-foreground mb-2">Daily Limit</div>
                <div className="text-4xl font-bold text-foreground">1,000</div>
              </div>
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
