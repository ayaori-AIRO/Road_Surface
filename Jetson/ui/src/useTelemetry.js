import { useEffect, useState } from 'react';
import { mergeRows } from './telemetry';

export default function useTelemetry() {
  const [state, setState] = useState({ rows: [], latest: null, connected: false, online: false, invalid: 0, server_ms: Date.now() });
  useEffect(() => {
    let active = true, after = 0, instance = null, rows = [], timer;
    let controller;
    async function poll() {
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10000);
      try {
        const response = await fetch('/api/data?after=' + after, { signal: controller.signal });
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const data = await response.json();
        if (instance !== null && instance !== data.instance_id) {
          rows = []; after = 0; instance = data.instance_id;
          if (active) setState({ ...data, latest: null, rows: [], online: true });
          return;
        }
        instance = data.instance_id;
        rows = mergeRows(rows, data.rows, data.server_ms);
        if (data.rows.length) after = data.rows[data.rows.length - 1].id;
        if (active) setState({ ...data, rows, online: true });
      } catch {
        if (active) setState(previous => ({ ...previous, online: false }));
      } finally {
        clearTimeout(timeout);
        if (active) timer = setTimeout(poll, 500);
      }
    }
    poll();
    return () => { active = false; clearTimeout(timer); controller?.abort(); };
  }, []);
  return state;
}
