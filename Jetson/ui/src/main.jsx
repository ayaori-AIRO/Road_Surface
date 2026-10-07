import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import useTelemetry from './useTelemetry';
import { metrics, fmt, clock, csv, statusLabel } from './telemetry';
import './style.css';

function Icon({ name, size = 20 }) {
  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    pulse: <path d="M2 12h5l3-8 4 16 3-8h5"/>,
    history: <><path d="M3 11a9 9 0 1 1 2 7M3 4v7h7"/><path d="M12 7v5l3 2"/></>,
    download: <><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></>,
    snow: <><path d="M12 2v20M3.3 7l17.4 10M3.3 17 20.7 7M8 4l4 3 4-3M8 20l4-3 4 3"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.pulse}</svg>;
}

function Chart({ metric, rows, start, end }) {
  const [hover, setHover] = useState(null);
  const visible = rows.filter(r => r.received_ms >= start && r.received_ms <= end);
  const values = visible.map(r => r[metric.key]).filter(Number.isFinite);
  const min = values.length ? Math.min(...values) : 0, max = values.length ? Math.max(...values) : 1;
  const padding = Math.max((max - min) * .15, .1), low = min - padding, high = max + padding;
  const x = t => 60 + (t - start) / (end - start) * 660;
  const y = v => 175 - (v - low) / (high - low) * 145;
  let previous = null;
  const path = visible.map(row => {
    if (!Number.isFinite(row[metric.key])) { previous = null; return ''; }
    const move = previous === null || row.received_ms - previous > 2500;
    previous = row.received_ms;
    return `${move ? 'M' : 'L'}${x(row.received_ms)},${y(row[metric.key])}`;
  }).join(' ');
  const selected = hover === null ? null : visible.reduce((best, row) => !best || Math.abs(row.received_ms - hover) < Math.abs(best.received_ms - hover) ? row : best, null);
  return <section className="panel chart">
    <div className="panel-head"><h3><span className="dot" style={{ background: metric.color }}/>{metric.label}</h3><span>{metric.unit} · {metric.source}</span></div>
    <svg viewBox="0 0 740 215" role="img" aria-label={`${metric.label} 시간별 그래프`} onPointerLeave={() => setHover(null)} onPointerMove={e => {
      const rect = e.currentTarget.getBoundingClientRect();
      setHover(start + Math.max(0, Math.min(1, ((e.clientX - rect.left) / rect.width * 740 - 60) / 660)) * (end - start));
    }}>
      {[0, 1, 2, 3].map(i => <g key={i}><line x1="60" x2="720" y1={30 + i * 145 / 3} y2={30 + i * 145 / 3} stroke="#263448" strokeDasharray="3 4"/><text x="49" y={34 + i * 145 / 3} textAnchor="end">{fmt(high - i * (high - low) / 3, 1)}</text><text x={60 + i * 220} y="203" textAnchor={i === 0 ? 'start' : i === 3 ? 'end' : 'middle'}>{clock(start + i * (end - start) / 3)}</text></g>)}
      <path d={path} stroke={metric.color} strokeWidth="2.5" fill="none"/>
      {visible.length === 1 && values.length === 1 && <circle cx={x(visible[0].received_ms)} cy={y(values[0])} r="3" fill={metric.color}/>}
      {!values.length && <text x="390" y="105" textAnchor="middle">이 구간에 유효한 데이터가 없습니다</text>}
      {selected && Number.isFinite(selected[metric.key]) && <g><line x1={x(selected.received_ms)} x2={x(selected.received_ms)} y1="25" y2="180" stroke="#8da1b9"/><circle cx={x(selected.received_ms)} cy={y(selected[metric.key])} r="4" fill={metric.color}/></g>}
    </svg>
    <div className="chart-caption">{selected ? `${clock(selected.received_ms)} · ${fmt(selected[metric.key])} ${metric.unit}` : '그래프에 마우스를 올려 측정값 확인 · 음수 원본값 포함'}</div>
  </section>;
}

function App() {
  const data = useTelemetry();
  const [tab, setTab] = useState('overview'), [span, setSpan] = useState(300000), [frozen, setFrozen] = useState(null), [position, setPosition] = useState(1000);
  const [filter, setFilter] = useState('all'), [page, setPage] = useState(0);
  const { latest, rows } = data;
  const fresh = data.online && data.connected && latest && data.server_ms - latest.received_ms < 3000;
  const connection = !data.online ? '서버 연결 확인 중' : !data.connected ? 'Raspberry Pi 연결 대기' : !fresh ? '데이터 갱신 지연' : '실시간 수신 중';
  const current = fresh ? latest : null;
  const end = frozen ?? data.server_ms, start = end - span;
  const titles = { overview: ['실시간 관측', '노면 상태와 환경 변화를 한눈에 확인하세요.'], diagnostics: ['센서 진단', '수신 상태와 지연 원인을 확인하세요.'], history: ['수신 기록', '현재 서버 세션의 최근 1시간 기록을 조회합니다.'] };
  const filtered = rows.filter(r => filter === 'all' || (filter === 'ok' ? r.prediction_status === 'ok' : r.prediction_status !== 'ok')).slice().reverse();
  const safePage = Math.min(page, Math.max(0, Math.ceil(filtered.length / 25) - 1));
  function download() {
    const url = URL.createObjectURL(new Blob([csv(filtered.slice().reverse())], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = `road-surface-${new Date().toISOString().replaceAll(':', '-')}.csv`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <div className="app">
    <aside className="sidebar"><div className="brand"><span className="brand-icon"><Icon name="pulse" size={26}/></span><div>ROAD SURFACE<small>노면 관측 시스템</small></div></div>
      <div className="nav-label">WORKSPACE</div><nav aria-label="주 메뉴">{[['overview', 'grid', '실시간 관측'], ['diagnostics', 'pulse', '센서 진단'], ['history', 'history', '수신 기록']].map(([id, icon, text]) => <button key={id} className={tab === id ? 'selected' : ''} onClick={() => setTab(id)} aria-current={tab === id ? 'page' : undefined}><Icon name={icon}/>{text}<span>›</span></button>)}</nav>
      <div className="sidebar-bottom"><span className="dot"/> JETSON GATEWAY<p>수신 목표 1 Hz<br/>최근 1시간 · 메모리 보관</p></div>
    </aside>
    <div className="workspace"><header><div>ROAD SURFACE <span>/</span> {titles[tab][0]}</div><span className={'badge ' + (fresh ? 'good' : 'neutral')}><span className="dot"/>{connection}</span></header>
      <main><div className="heading"><div><div className="eyebrow">SURFACE OBSERVATORY</div><h1>{titles[tab][0]}</h1><p>{titles[tab][1]}</p></div><div className="updated">마지막 수신<strong>{clock(latest?.received_ms)}</strong></div></div>
      <div className="notice"><span>시험 운전</span>현재 기본 설정은 가상 거리·속도를 사용합니다. 예측 적설 높이는 실제 적설 측정값이 아닙니다.</div>
      {tab === 'overview' && <>
        <div className="overview-grid"><section className="snow-card"><div className="snow-top"><span><Icon name="snow"/>예측 적설 높이</span><span>ML MODEL</span></div><div className="snow-value">{fmt(current?.prediction_status === 'ok' ? current.snow_height_mm : null)}<small>mm</small></div><div className="snow-bottom"><span className="dot"/>{fresh ? statusLabel(latest.prediction_status) : connection}<span>회차 {latest?.cycle_id ?? '—'}</span></div></section>
        <div className="sensor-cards">{metrics.slice(1).map(m => <section className="panel sensor-card" key={m.key}><div className="sensor-title"><span>{m.label}</span><span style={{ color: m.color }}>{m.source}</span></div><div className="sensor-value">{fmt(current?.[m.key])}<small>{m.unit}</small></div><div className="sensor-foot"><span className="dot" style={{ background: Number.isFinite(current?.[m.key]) ? m.color : '#586b80' }}/>{Number.isFinite(current?.[m.key]) ? '정상 수신' : '유효값 대기'}</div></section>)}</div></div>
        <div className="section-heading"><div><h2>시간별 추이</h2><p>{frozen === null ? '실시간으로 갱신되는 센서 데이터' : '선택한 시간 구간을 보고 있습니다'}</p></div><div className="controls">{[[60000,'1분'],[300000,'5분'],[900000,'15분'],[3600000,'1시간']].map(([value,label]) => <button key={value} className={span === value ? 'active' : ''} onClick={() => setSpan(value)}>{label}</button>)}<button className={frozen === null ? 'active' : ''} onClick={() => { setFrozen(null); setPosition(1000); }}>● 실시간</button></div></div>
        <div className="timeline"><span>과거</span><input type="range" aria-label="그래프 조회 시점" min="0" max="1000" value={position} disabled={!rows.length} onChange={e => { const value = Number(e.target.value); setPosition(value); setFrozen(value === 1000 ? null : rows[0].received_ms + (data.server_ms - rows[0].received_ms) * value / 1000); }}/><span>최신</span></div>
        <div className="charts">{metrics.map(m => <Chart key={m.key} metric={m} rows={rows} start={start} end={end}/>)}</div>
      </>}
      {tab === 'diagnostics' && <>
        <div className="diagnostic-summary"><section className="panel"><div className="label">예측 상태</div><h2>{fresh ? statusLabel(latest.prediction_status) : connection}</h2><p>{latest?.prediction_status || '아직 수신한 상태가 없습니다'}</p></section><section className="panel"><div className="label">수신 간격 / 목표 1,000ms</div><h2>{fmt(current?.receive_interval_ms, 1)} <small>ms</small></h2><p>Jetson에서 측정한 패킷 도착 간격</p></section><section className="panel"><div className="label">회차 시작 → 전송 데이터 생성</div><h2>{fmt(current?.prediction_age_ms, 1)} <small>ms</small></h2><p>ML 추론 시간만을 의미하지 않습니다</p></section></div>
        <section className="panel"><div className="panel-head"><h3>센서별 수집 상태</h3><span>마지막 패킷 기준{!fresh && ' · 갱신되지 않은 기록'}</span></div><div className="table-wrap"><table><thead><tr><th>센서</th><th>읽기 시간</th><th>전송 시 수신 후 경과</th></tr></thead><tbody>{['imu','ct100','ftm02','bme280','gps'].map(name => <tr key={name}><td><strong>{name.toUpperCase()}</strong></td><td>{fmt(latest?.sensor_read_ms?.[name], 1)} ms</td><td>{fmt(latest?.sensor_age_ms?.[name], 1)} ms</td></tr>)}</tbody></table></div><p className="footnote">— : 송신 데이터에 없는 항목입니다. IMU 원시 값과 ML 세부 처리 시간은 현재 전송되지 않습니다.</p></section>
        <section className="panel error-panel"><div className="panel-head"><h3>수신 형식 오류</h3><span>{data.invalid}건</span></div><p>{data.last_error?.reason || '기록된 형식 오류가 없습니다.'}</p>{data.last_error && <code>{data.last_error.received_fields?.join(', ')}</code>}</section>
      </>}
      {tab === 'history' && <section className="panel"><div className="panel-head"><div><h3>최근 수신 데이터</h3><p>서버 재시작 시 초기화됩니다. 장기 보관은 CSV로 저장하세요.</p></div><button className="primary" disabled={!filtered.length} onClick={download}><Icon name="download" size={16}/>CSV 내보내기</button></div><div className="history-tools"><label>예측 상태 <select value={filter} onChange={e => {setFilter(e.target.value);setPage(0);}}><option value="all">전체</option><option value="ok">정상</option><option value="error">대기 / 오류</option></select></label><span>{filtered.length.toLocaleString()}건 · CSV는 현재 필터 전체를 저장</span></div><div className="table-wrap"><table><thead><tr><th>수신 시각</th><th>회차</th>{metrics.map(m => <th key={m.key}>{m.label}<small>{m.unit}</small></th>)}<th>예측 상태</th></tr></thead><tbody>{filtered.slice(safePage*25, safePage*25+25).map(r => <tr key={r.id}><td>{clock(r.received_ms)}</td><td>{r.cycle_id ?? '—'}</td>{metrics.map(m => <td key={m.key}>{fmt(r[m.key])}</td>)}<td><span className={'badge ' + (r.prediction_status === 'ok' ? 'good' : 'neutral')}>{statusLabel(r.prediction_status)}</span></td></tr>)}{!filtered.length && <tr><td colSpan="8" className="empty">표시할 수신 기록이 없습니다.</td></tr>}</tbody></table></div><div className="pagination"><button disabled={safePage===0} onClick={() => setPage(safePage-1)}>이전</button><span>{safePage+1} / {Math.max(1,Math.ceil(filtered.length/25))}</span><button disabled={(safePage+1)*25>=filtered.length} onClick={() => setPage(safePage+1)}>다음</button></div></section>}
      <footer><span><span className="dot"/> ROAD SURFACE · JETSON</span><span>최근 1시간 {rows.length.toLocaleString()}건 · 형식 오류 {data.invalid}건</span></footer>
      </main></div></div>;
}

createRoot(document.getElementById('root')).render(<App/>);
