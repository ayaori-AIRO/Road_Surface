import React, { useEffect, useRef, useState } from 'react';
import { advanceDistance, positionAt, route } from './locationSimulation';

export default function LocationPanel() {
  const [speed, setSpeed] = useState(30);
  const [running, setRunning] = useState(true);
  const [follow, setFollow] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [sample, setSample] = useState(() => ({ distance: 0, time: Date.now() }));
  const engine = useRef({ distance: 0, tick: performance.now(), speed: 30, running: true });
  function sync() {
    const now = performance.now(), e = engine.current;
    e.distance = advanceDistance(e.distance, e.running ? e.speed : 0, (now - e.tick) / 1000);
    e.tick = now;
    setSample({ distance: e.distance, time: Date.now() });
  }
  useEffect(() => {
    const timer = setInterval(sync, 250);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!expanded) return;
    const close = e => { if (e.key === 'Escape') setExpanded(false); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [expanded]);
  const pos = positionAt(sample.distance);
  function map() {
    const cx = follow ? pos.x : 225, cy = follow ? -pos.y : -150;
    return <svg className="location-map" viewBox={`${cx - 350} ${cy - 300} 700 600`} role="img" aria-label="모의 GPS 순환 경로와 현재 위치. 실제 도로 지도 아님">
      <rect x={cx - 350} y={cy - 300} width="700" height="600" fill="#0e1a28" />
      {[-600,-400,-200,0,200,400,600,800].map(n => <g key={n} stroke="#1e3043" strokeWidth="1"><line x1={n} y1="-1000" x2={n} y2="1000"/><line x1="-1000" y1={n} x2="1200" y2={n}/></g>)}
      <polyline points={route.map(([x,y])=>`${x},${-y}`).join(' ')} fill="none" stroke="#2d4860" strokeWidth="22" strokeLinejoin="round"/>
      <polyline points={route.map(([x,y])=>`${x},${-y}`).join(' ')} fill="none" stroke="#72b7ff" strokeWidth="3" strokeDasharray="9 9"/>
      <text x="225" y="-160" textAnchor="middle" fill="#8da1b9" fontSize="24">가상 시험 경로</text>
      <text x="225" y="-120" textAnchor="middle" fill="#8da1b9" fontSize="20">1.50 km 순환</text>
      <circle cx={pos.x} cy={-pos.y} r="22" fill="#55dfbd" fillOpacity=".18"/>
      <path d="M0 -16 L10 12 L0 7 L-10 12 Z" fill="#55dfbd" stroke="#ecf3fc" strokeWidth="2" transform={`translate(${pos.x} ${-pos.y}) rotate(${pos.heading})`}/>
    </svg>;
  }
  return <aside className="sidebar location-panel">
    <div className="location-title"><h3>현재 위치</h3><span className="simulation-badge">모의 GPS</span></div>
    {map()}
    <div className="location-actions"><button onClick={()=>setFollow(!follow)} aria-pressed={follow}>{follow?'위치 추적 켜짐':'전체 경로'}</button><button onClick={()=>setExpanded(true)}>크게 보기</button></div>
    <p>가상 시험 구간 · 실제 주소 없음</p>
    <dl><dt>위도</dt><dd>{pos.latitude.toFixed(6)}°</dd><dt>경도</dt><dd>{pos.longitude.toFixed(6)}°</dd><dt>이동 속도</dt><dd>{running?speed:0} km/h</dd><dt>이동 거리</dt><dd>{(sample.distance/1000).toFixed(3)} km</dd><dt>방위</dt><dd>{pos.heading.toFixed(0)}°</dd><dt>모의 위치 갱신</dt><dd>{new Date(sample.time).toLocaleTimeString('ko-KR',{hour12:false})}</dd></dl>
    <label className="speed-control">설정 속도 · {speed} km/h<input aria-label="모의 이동 속도" type="range" min="0" max="100" step="5" value={speed} onChange={e=>{sync();const v=Number(e.target.value);engine.current.speed=v;setSpeed(v);}}/></label>
    <div className="location-actions"><button onClick={()=>{sync();engine.current.running=!running;setRunning(!running);}}>{running?'일시정지':'이동 재개'}</button><button onClick={()=>{engine.current.distance=0;engine.current.tick=performance.now();setSample({distance:0,time:Date.now()});}}>처음 위치</button></div>
    <p className="location-disclaimer">{running&&speed>0?'모의 이동 중':'모의 이동 정지'} · 실제 GPS 수신 아님<br/>UI 전용 시뮬레이션입니다. ML 입력·수신 기록과 별개이며 새로고침하면 초기화됩니다.</p>
    {expanded&&<div className="map-overlay"><section role="dialog" aria-modal="true" aria-label="모의 위치 확대" className="map-dialog"><div className="location-title"><h3>모의 GPS · 오프라인 경로도</h3><button autoFocus onClick={()=>setExpanded(false)}>닫기</button></div>{map()}<p>{pos.latitude.toFixed(6)}, {pos.longitude.toFixed(6)} · {running?speed:0} km/h · 실제 도로 지도 아님</p></section></div>}
  </aside>;
}
