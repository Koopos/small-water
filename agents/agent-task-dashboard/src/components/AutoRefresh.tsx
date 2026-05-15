"use client";

import { useEffect } from "react";
import { syncFromGitHub } from "@/app/actions";

interface AutoRefreshProps {
  projectId: string;
  intervalMs?: number;
}

export default function AutoRefresh({ projectId, intervalMs = 30000 }: AutoRefreshProps) {
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        await syncFromGitHub(projectId);
      } catch (e) {
        console.error("[AutoSync] syncFromGitHub failed:", e);
      }
    }, intervalMs);

    return () => clearInterval(interval);
  }, [projectId, intervalMs]);

  return null;
}
