import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import useTelemetry from "./useTelemetry";
import { metrics, fmt, clock, csv, statusLabel } from "./telemetry";
import "./style.css";
import unieyeLogo from "./assets/unieye-logo.png";
import LocationPanel from "./LocationPanel";
import SensorSettings from "./SensorSettings";
function Icon({ name, size = 20 }) {
  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    pulse: <path d="M2 12h5l3-8 4 16 3-8h5" />,
    history: <><path d="M3 11a9 9 0 1 1 2 7M3 4v7h7" /><path d="M12 7v5l3 2" /></>,
    download: <><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" /></>,
    snow: <><path d="M12 2v20M3.3 7l17.4 10M3.3 17 20.7 7M8 4l4 3 4-3M8 20l4-3 4 3" /></>
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.pulse}</svg>;
}
function Chart({ metric, rows, start, end }) {
  const [hover, setHover] = useState(null);
  const visible = rows.filter((r) => r.received_ms >= start && r.received_ms <= end);
  const series = metric.series || [metric];
  const values = visible.flatMap((r) => series.map((m) => r[m.key])).filter(Number.isFinite);
  const min = values.length ? Math.min(...values) : 0, max = values.length ? Math.max(...values) : 1;
  const padding = Math.max((max - min) * 0.15, 0.1), low = min - padding, high = max + padding;
  const x = (t) => 60 + (t - start) / (end - start) * 660;
  const y = (v) => 175 - (v - low) / (high - low) * 145;
  const makePath = (key) => {
    let previous = null;
    return visible.map((row) => {
      if (!Number.isFinite(row[key])) {
        previous = null;
        return "";
      }
      const move = previous === null || row.received_ms - previous > 2500;
      previous = row.received_ms;
      return `${move ? "M" : "L"}${x(row.received_ms)},${y(row[key])}`;
    }).join(" ");
  };
  const selected = hover === null ? null : visible.reduce((best, row) => !best || Math.abs(row.received_ms - hover) < Math.abs(best.received_ms - hover) ? row : best, null);
  return <section className="panel chart">
    <div className="panel-head"><h3><span className="dot" style={{ background: metric.color }} />{metric.label}</h3><span>{metric.unit} · {metric.source}</span></div>
    <svg viewBox="0 0 740 215" role="img" aria-label={`${metric.label} 시간별 그래프`} onPointerLeave={() => setHover(null)} onPointerMove={(e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setHover(start + Math.max(0, Math.min(1, ((e.clientX - rect.left) / rect.width * 740 - 60) / 660)) * (end - start));
  }}>
      {[0, 1, 2, 3].map((i) => <g key={i}><line x1="60" x2="720" y1={30 + i * 145 / 3} y2={30 + i * 145 / 3} stroke="#263448" strokeDasharray="3 4" /><text x="49" y={34 + i * 145 / 3} textAnchor="end">{fmt(high - i * (high - low) / 3, 1)}</text><text x={60 + i * 220} y="203" textAnchor={i === 0 ? "start" : i === 3 ? "end" : "middle"}>{clock(start + i * (end - start) / 3)}</text></g>)}
      {series.map((m) => <path key={m.key} d={makePath(m.key)} stroke={m.color} strokeWidth="2" fill="none" />)}
      {visible.length === 1 && values.length === 1 && <circle cx={x(visible[0].received_ms)} cy={y(values[0])} r="3" fill={metric.color} />}
      {!values.length && <text x="390" y="105" textAnchor="middle">이 구간에 유효한 데이터가 없습니다</text>}
      {selected && Number.isFinite(selected[metric.key]) && <g><line x1={x(selected.received_ms)} x2={x(selected.received_ms)} y1="25" y2="180" stroke="#8da1b9" /><circle cx={x(selected.received_ms)} cy={y(selected[metric.key])} r="4" fill={metric.color} /></g>}
    </svg>
    <div className="chart-caption">{selected ? `${clock(selected.received_ms)} · ${series.map((m) => `${m.label}: ${fmt(selected[m.key])} ${metric.unit}`).join(" / ")}` : "그래프에 마우스를 올려 측정값 확인 · 음수 원본값 포함"}</div>
  </section>;
}
const sensors = [["ct100", "CT100", "노면 온도", "road_temperature_c"], ["ftm02", "FTM02", "온습도", "air_temperature_c"], ["bme280", "BME280", "대기압", "pressure_hpa"], ["imu", "IMU", "가속도·각속도", null], ["gps", "GPS", "속도", null]];
function Records({ rows, selected, onSelect }) {
  return <div className="table-wrap"><table><thead><tr><th>회차</th><th>수신 시각</th>{metrics.map((m) => <th key={m.key}>{m.label}<small>{m.unit}</small></th>)}<th>예측 상태</th><th>수신 간격<small>ms</small></th></tr></thead><tbody>{rows.map((r) => <tr key={r.id} className={selected === r.id ? "chosen" : ""}><td><button className="row-select" onClick={() => onSelect(r.id)} aria-label={`회차 ${r.cycle_id ?? r.id} 상세 보기`}>{r.cycle_id ?? "—"}</button></td><td>{clock(r.received_ms)}</td>{metrics.map((m) => <td key={m.key}>{fmt(r[m.key])}</td>)}<td className={r.prediction_status === "ok" ? "success" : "warning"}>{statusLabel(r.prediction_status)}</td><td>{fmt(r.receive_interval_ms, 0)}</td></tr>)}{!rows.length && <tr><td colSpan="9" className="empty">수신 기록을 기다리고 있습니다.</td></tr>}</tbody></table></div>;
}
function App() {
  const data = useTelemetry(), { rows, latest } = data;
  const [tab, setTab] = useState("overview"), [span, setSpan] = useState(3e5), [frozen, setFrozen] = useState(null), [position, setPosition] = useState(1e3);
  const [filter, setFilter] = useState("all"), [page, setPage] = useState(0), [selected, setSelected] = useState(null);
  const fresh = Boolean(data.online && data.connected && latest && data.server_ms - latest.received_ms < 3e3);
  const current = fresh ? latest : null;
  const connection = !data.online ? "서버 연결 확인 중" : !data.connected ? "Raspberry Pi 연결 대기" : !fresh ? "데이터 갱신 지연" : "연결됨 · 1초 갱신";
  const end = frozen ?? data.server_ms, start = end - span;
  const filtered = rows.filter((r) => filter === "all" || (filter === "ok" ? r.prediction_status === "ok" : r.prediction_status !== "ok")).slice().reverse();
  const pages = Math.max(1, Math.ceil(filtered.length / 25)), safePage = Math.min(page, pages - 1);
  const detail = rows.find((r) => r.id === selected);
  const chartRows = rows.map((r) => ({ ...r, ...Object.fromEntries(sensors.map(([id]) => [id, r.sensor_read_ms?.[id]])) }));
  function download() {
    const url = URL.createObjectURL(new Blob([csv(filtered.slice().reverse())], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "road-surface-records.csv";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1e3);
  }
  const summary = <section className="panel measurements"><div className="panel-head"><h3>{tab === "overview" ? "현재 측정값" : "진단 요약"}</h3><span>{clock(latest?.received_ms)}</span></div>{tab === "overview" && metrics.map((m) => <div className="measurement" key={m.key}><span>{m.label}</span><strong>{fmt(current?.[m.key])}<small>{m.unit}</small></strong></div>)}<div className="summary-block"><h3>예측 상태</h3><p className={fresh && latest.prediction_status === "ok" ? "success" : "warning"}>{fresh ? statusLabel(latest.prediction_status) : connection}</p></div><div className="measurement"><span>수신 간격</span><strong>{fmt(current?.receive_interval_ms, 0)}<small>ms</small></strong></div><div className="measurement"><span>회차 시작 → 전송 생성</span><strong>{fmt(current?.prediction_age_ms, 0)}<small>ms</small></strong></div><p>마지막 항목은 ML 추론 시간만을 의미하지 않습니다.</p></section>;
  return <div className="app"><header className="topbar"><div className="brand" aria-label="UniEye RoadSurface"><img src={unieyeLogo} alt="UniEye" width="123" height="47" /><span className="brand-product">RoadSurface</span></div><nav aria-label="검색 및 탐색">{[["overview", "실시간"], ["diagnostics", "센서 진단"], ["history", "수신 기록"], ["settings", "설정"]].map(([id, label]) => <button key={id} className={tab === id ? "selected" : ""} aria-current={tab === id ? "page" : void 0} onClick={() => setTab(id)}>{label}</button>)}</nav><span className={fresh ? "success" : "muted"}>● {connection}</span></header><div className="shell"><LocationPanel /><main><div className="notice">시험 운영 · 기본 설정은 가상 거리·속도를 사용합니다. 예측 적설 높이는 실제 적설 측정값이 아닙니다.</div>
  {tab === "settings" && <SensorSettings />}
  {tab === "overview" && <><div className="toolbar"><h2>실시간 관측</h2><div className="controls">{[[6e4, "1분"], [3e5, "5분"], [9e5, "15분"], [36e5, "1시간"]].map(([v, l]) => <button key={v} className={span === v ? "active" : ""} onClick={() => setSpan(v)}>{l}</button>)}<button onClick={() => {
    setFrozen(null);
    setPosition(1e3);
  }}>실시간 복귀</button></div></div><div className="timeline"><span>과거</span><input type="range" aria-label="그래프 조회 시점" min="0" max="1000" value={position} disabled={!rows.length} onChange={(e) => {
    const v = Number(e.target.value);
    setPosition(v);
    setFrozen(v === 1e3 ? null : rows[0].received_ms + (data.server_ms - rows[0].received_ms) * v / 1e3);
  }} /><span>{frozen === null ? "실시간" : clock(frozen)}</span></div><div className="analysis-grid"><div className="plot-area"><Chart metric={metrics[0]} rows={rows} start={start} end={end} /><div className="mini-charts">{metrics.slice(1, 4).map((m) => <Chart key={m.key} metric={m} rows={rows} start={start} end={end} />)}</div><details><summary>대기압 추이</summary><Chart metric={metrics[4]} rows={rows} start={start} end={end} /></details></div>{summary}</div><section className="panel records"><h3>최근 수신 기록 · 최근 8건</h3><Records rows={rows.slice(-8).reverse()} selected={selected} onSelect={(id) => {
    setSelected(id);
    setTab("history");
  }} /></section></>}
  {tab === "diagnostics" && <><div className="toolbar"><h2>{tab === "history" ? "수신 기록" : "센서 진단"}</h2><span>마지막 패킷 기준{!fresh ? " · 갱신되지 않은 기록" : ""}</span></div><div className="analysis-grid"><section className="panel"><h3>센서 수집 상태</h3><div className="table-wrap"><table><thead><tr><th>센서</th><th>측정 항목</th><th>수신 정보</th><th>읽기 시간 (ms)</th><th>전송 전 수신 후 경과 (ms)</th></tr></thead><tbody>{sensors.map(([id, label, desc, key]) => <tr key={id}><td>{label}</td><td>{desc}</td><td>{!fresh ? "갱신 대기" : key ? Number.isFinite(current?.[key]) ? "값 수신" : "값 없음" : "상세 상태 미제공"}</td><td>{fmt(latest?.sensor_read_ms?.[id], 1)}</td><td>{fmt(latest?.sensor_age_ms?.[id], 1)}</td></tr>)}</tbody></table></div><p>—: 패킷에 없는 항목입니다. 읽기 시간만으로 수신 성공 여부를 판단하지 않습니다.</p></section>{summary}</div><Chart metric={{ key: "receive_interval_ms", label: "수신 간격 추이", unit: "ms", source: "목표 1,000 ms", color: "#72b7ff" }} rows={rows} start={data.server_ms - 6e4} end={data.server_ms} /><Chart metric={{ key: "imu", label: "센서 읽기 시간 추이", unit: "ms", source: "CT100 · FTM02 · BME280 · IMU", series: sensors.slice(0, 4).map(([id, label], i) => ({ key: id, label, color: metrics[i].color })) }} rows={chartRows} start={data.server_ms - 6e4} end={data.server_ms} /><div className="legend">{sensors.slice(0, 4).map(([id, label], i) => <span key={id} style={{ color: metrics[i].color }}>━ {label}</span>)}</div><section className="panel"><div className="panel-head"><h3>최근 예측 상태 기록</h3><span>최근 8건</span></div><div className="table-wrap"><table><thead><tr><th>회차</th><th>수신 시각</th><th>예측 상태</th></tr></thead><tbody>{rows.slice(-8).reverse().map((r) => <tr key={r.id}><td>{r.cycle_id ?? "—"}</td><td>{clock(r.received_ms)}</td><td className={r.prediction_status === "ok" ? "success" : "warning"}>{statusLabel(r.prediction_status)}</td></tr>)}</tbody></table></div><p>수신 형식 오류 {data.invalid}건 · {data.last_error?.reason || "기록된 형식 오류 없음"}</p></section></>}
  {tab === "history" && <><section className="panel"><div className="toolbar"><div><h2>{tab === "history" ? "수신 기록" : "센서 진단"}</h2><p>현재 서버 세션 · 최근 1시간</p></div><button onClick={download} disabled={!filtered.length}><Icon name="download" size={16} />CSV 내보내기</button></div><div className="toolbar"><label>예측 상태 <select value={filter} onChange={(e) => {
    setFilter(e.target.value);
    setPage(0);
  }}><option value="all">전체</option><option value="ok">정상</option><option value="error">대기 / 오류</option></select></label><span>전체 {rows.length}건 | 예측 정상 {rows.filter((r) => r.prediction_status === "ok").length}건 | 필터 결과 {filtered.length}건</span></div><Records rows={filtered.slice(safePage * 25, safePage * 25 + 25)} selected={selected} onSelect={setSelected} /><div className="pagination"><span>{filtered.length ? safePage * 25 + 1 : 0}–{Math.min((safePage + 1) * 25, filtered.length)} / {filtered.length}건</span><button disabled={!safePage} onClick={() => setPage(safePage - 1)}>이전</button><span>{safePage + 1} / {pages}</span><button disabled={safePage + 1 >= pages} onClick={() => setPage(safePage + 1)}>다음</button></div><p>CSV는 현재 필터의 전체 기록을 저장합니다. 서버 재시작 시 기록이 초기화됩니다.</p></section><section className="panel"><h3>선택 기록 {detail ? `· 회차 ${detail.cycle_id ?? "—"}` : ""}</h3>{detail ? <><p>{new Date(detail.received_ms).toLocaleString("ko-KR")} · {statusLabel(detail.prediction_status)}</p><div className="detail-values">{metrics.map((m) => <div key={m.key}><span>{m.label}</span><strong>{fmt(detail[m.key])} <small>{m.unit}</small></strong></div>)}</div></> : <p>표의 회차 번호를 선택하면 상세 측정값을 표시합니다.</p>}</section></>}
  <footer><span>ROAD SURFACE · JETSON</span><span>최근 1시간 {rows.length.toLocaleString()}건 · 형식 오류 {data.invalid}건</span></footer></main></div></div>;
}
createRoot(document.getElementById("root")).render(<App />);
