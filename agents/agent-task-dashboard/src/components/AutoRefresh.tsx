"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

interface AutoRefreshProps {
  endpointPath: string;
  intervalMs?: number;
}

export default function AutoRefresh({ endpointPath, intervalMs = 10000 }: AutoRefreshProps) {
  const router = useRouter();

  useEffect(() => {
    const refresh = async () => {
      try {
        await fetch(endpointPath, { cache: "no-store" });
        router.refresh();
      } catch (e) {
        console.error("[AutoRefresh] refresh failed:", e);
      }
    };

    refresh();
    const interval = setInterval(refresh, intervalMs);

    return () => clearInterval(interval);
  }, [endpointPath, intervalMs, router]);

  return null;
}
