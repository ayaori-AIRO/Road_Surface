export const metrics = [
  { key: 'snow_height_mm', label: '예측 적설 높이', unit: 'mm', source: 'ML 예측', color: '#55dfbd' },
  { key: 'road_temperature_c', label: '노면 온도', unit: '°C', source: 'CT100', color: '#ffbd76' },
  { key: 'air_temperature_c', label: '대기 온도', unit: '°C', source: 'FTM02', color: '#72b7ff' },
  { key: 'humidity_pct', label: '대기 습도', unit: '%', source: 'FTM02', color: '#b69aff' },
  { key: 'pressure_hpa', label: '대기압', unit: 'hPa', source: 'BME280', color: '#f2d572' },
];
const statuses = {
  ok: '예측 정상', warming_up: 'IMU 이력 수집 중', cycle_late: '수집·예측 시간 초과',
  cycle_mismatch: '센서 회차 불일치', imu_missing: 'IMU 수신 실패',
  ftm02_missing: '온습도 수신 실패', ct100_missing: '노면 온도 수신 실패',
  gps_missing: 'GPS 수신 실패', prediction_stale: '예측 결과 갱신 지연',
  imu_processing_late: 'IMU 처리 지연', waiting_for_ftm02: '온습도 수신 대기',
  ftm02_stale: '온습도 갱신 지연', waiting_for_gps_speed: 'GPS 속도 수신 대기',
  gps_speed_stale: 'GPS 갱신 지연', invalid_input: '모델 입력 오류',
};
export const statusLabel = value => statuses[value] || value || '수신 대기';
export const fmt = (value, digits = 2) => Number.isFinite(value) ? value.toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits }) : '—';
export const clock = value => value ? new Date(value).toLocaleTimeString('ko-KR', { hour12: false }) : '—';
export function mergeRows(rows, incoming, now) {
  const byId = new Map(rows.map(row => [row.id, row]));
  incoming.forEach(row => byId.set(row.id, row));
  return [...byId.values()].filter(row => row.received_ms >= now - 3600000).sort((a, b) => a.id - b.id).slice(-3600);
}
export function csv(rows) {
  const keys = ['timestamp', 'received_ms', 'cycle_id', ...metrics.map(m => m.key), 'prediction_status', 'receive_interval_ms', 'prediction_age_ms'];
  const escape = value => {
    let text = String(value ?? '');
    if (typeof value === 'string' && /^[=+@\-\t\r]/.test(text)) text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
  };
  return '\uFEFF' + [keys.join(','), ...rows.map(row => keys.map(key => escape(row[key])).join(','))].join('\r\n');
}
