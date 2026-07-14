import { useEffect, useRef, useState } from 'react';
import { SSE_URL } from '../api/client';

export function useSSE(maxItems = 40) {
  const [events, setEvents] = useState([]);
  const esRef = useRef(null);

  useEffect(() => {
    const es = new EventSource(SSE_URL);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        setEvents(prev => [data, ...prev].slice(0, maxItems));
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      // Reconnect is handled automatically by EventSource
    };

    return () => es.close();
  }, [maxItems]);

  return events;
}
