/**
 * useSSE.js — Serverless-compatible activity feed hook.
 *
 * Previously used EventSource (SSE) which requires a persistent connection.
 * Vercel serverless functions terminate after each response, so SSE caused
 * immediate 500 errors. This hook polls /activity/stream every 5 seconds
 * instead — same external API, no component changes needed.
 */
import { useEffect, useRef, useState } from 'react';
import { SSE_URL } from '../api/client';

export function useSSE(maxItems = 40) {
  const [events, setEvents] = useState([]);
  const seenIds = useRef(new Set());

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch(SSE_URL);
        if (!res.ok) return;
        const items = await res.json();

        if (cancelled) return;

        // items is an array (newest first from backend)
        const newItems = [];
        for (const item of items) {
          if (!seenIds.current.has(item.id)) {
            seenIds.current.add(item.id);
            newItems.push(item);
          }
        }

        if (newItems.length > 0) {
          setEvents(prev => [...newItems, ...prev].slice(0, maxItems));
        }
      } catch {
        // ignore transient network errors — will retry on next interval
      }
    }

    // Initial fetch immediately
    poll();

    // Then poll every 5 seconds
    const interval = setInterval(poll, 5000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [maxItems]);

  return events;
}
