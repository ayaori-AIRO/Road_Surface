import React, { useEffect, useRef, useState } from "react";

function CameraView({ name, title }) {
  const image = useRef(null);
  const [state, setState] = useState("연결 중");
  useEffect(() => {
    let stopped = false, timer, objectUrl;
    const controller = new AbortController();
    async function refresh() {
      const timeout = setTimeout(() => controller.abort(), 10000);
      try {
        const response = await fetch(`/api/camera/${name}`, { cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error("unavailable");
        const blob = await response.blob();
        if (stopped) return;
        const previous = objectUrl;
        objectUrl = URL.createObjectURL(blob);
        image.current.src = objectUrl;
        if (previous) URL.revokeObjectURL(previous);
        setState("라이브");
      } catch {
        if (stopped) return;
        image.current.removeAttribute("src");
        setState("영상 수신 대기 · 카메라 연결을 확인하세요");
      } finally {
        clearTimeout(timeout);
        if (!stopped && !controller.signal.aborted) timer = setTimeout(refresh, 100);
        else if (!stopped) setState("서버 응답 지연 · 다시 연결을 눌러주세요");
      }
    }
    refresh();
    return () => {
      stopped = true;
      controller.abort();
      clearTimeout(timer);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [name]);
  return <section className="panel live-camera">
    <div className="panel-head"><h3>{title}</h3><span className={state === "라이브" ? "success" : "warning"} role="status">{state}</span></div>
    <div className="live-viewport"><img ref={image} alt={`${title} 라이브 영상`} />{state !== "라이브" && <div className="live-placeholder">{state}</div>}</div>
  </section>;
}

export default function LivePanel() {
  const [session, setSession] = useState(0);
  return <>
    <div className="toolbar"><div><h2>라이브 화면</h2><p>일반 영상과 열화상 영상을 함께 확인합니다.</p></div><button onClick={() => setSession((value) => value + 1)}>다시 연결</button></div>
    <div className="live-grid" key={session}><CameraView name="visible" title="일반 카메라" /><CameraView name="thermal" title="열화상 카메라" /></div>
    <p>두 영상은 각 채널에서 독립적으로 수신됩니다. 열화상 영상은 카메라의 영상 설정을 사용하며, 온도 수치 측정은 포함하지 않습니다.</p>
  </>;
}
