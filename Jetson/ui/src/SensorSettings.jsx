import React, { useState } from 'react';

const fields = [
  ['imu_port','IMU 포트','/dev/ttyUSB1'],
  ['imu_baud','IMU 통신 속도 (baud)',9600],
  ['imu_slave','IMU Modbus 주소 (십진수)',80],
  ['gps_port','GPS 포트','/dev/ttyUSB0'],
  ['gps_baud','GPS 통신 속도 (baud)',4800],
  ['bme_address','BME280 I²C 주소','0x76'],
  ['ct_board','CT100 보드 번호',0],
  ['ct_channel','CT100 전류 입력 채널',1],
  ['ftm_board','FTM02 보드 번호',0],
  ['ftm_humidity','FTM02 습도 전압 채널',1],
  ['ftm_temperature','FTM02 온도 전압 채널',2],
];
const defaults = Object.fromEntries(fields.map(([key,,value])=>[key,value]));
const sensorGroups = [
  ['imu_', 'IMU', 'WT901C485 · 시리얼 / Modbus'],
  ['gps_', 'GPS', 'BU-353N · 시리얼'],
  ['bme_', 'BME280', '온습도·대기압 · I²C'],
  ['ct_', 'CT100', '노면 온도 · 전류 입력'],
  ['ftm_', 'FTM02', '온습도 · 전압 입력'],
];
const storageKey = 'road-surface.sensor-settings.v1';
function validate(values) {
  for (const [key,label,initial] of fields) {
    const value = values[key];
    if (typeof initial === 'number' && (!Number.isInteger(value) || value < 0)) throw Error(`${label}: 0 이상의 정수를 입력하세요.`);
    if (key.endsWith('_port') && (typeof value !== 'string' || !/^\/dev\/[A-Za-z0-9_./-]+$/.test(value) || value.includes('..'))) throw Error(`${label}: /dev/로 시작하는 장치 경로를 입력하세요.`);
  }
  for (const key of ['imu_baud','gps_baud']) if (![1200,2400,4800,9600,19200,38400,57600,115200].includes(values[key])) throw Error('지원 통신 속도: 1200~115200의 표준 baud 값');
  if (values.imu_port===values.gps_port) throw Error('IMU와 GPS에는 서로 다른 포트를 지정하세요.');
  if (values.imu_slave<1 || values.imu_slave>247) throw Error('Modbus 주소는 1~247입니다.');
  if (!['0x76','0x77'].includes(values.bme_address)) throw Error('BME280 주소는 0x76 또는 0x77입니다.');
  for (const key of ['ct_board','ftm_board']) if(values[key]>7) throw Error('보드 번호는 0~7입니다.');
  for (const key of ['ct_channel','ftm_humidity','ftm_temperature']) if(values[key]<1||values[key]>4) throw Error('입력 채널은 1~4입니다.');
  if(values.ftm_humidity===values.ftm_temperature) throw Error('FTM02 온도·습도 채널은 달라야 합니다.');
  return {version:1,...Object.fromEntries(fields.map(([key])=>[key,values[key]]))};
}
export default function SensorSettings() {
  const [values,setValues]=useState(()=>{try {const saved=JSON.parse(localStorage.getItem(storageKey)); return saved?validate(saved):defaults;}catch{return defaults;}});
  const [message,setMessage]=useState('');
  function save(download=false) {
    try {
      const config=validate(values);
      localStorage.setItem(storageKey,JSON.stringify(config));
      if(download){const url=URL.createObjectURL(new Blob([JSON.stringify(config,null,2)+'\n'],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='sensor-settings.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
      setMessage(download?'설정 파일을 내보냈습니다. Raspberry Pi에 복사한 뒤 재실행하세요.':'이 브라우저에 저장했습니다. 장비에는 아직 적용되지 않았습니다.');
    } catch(error){setMessage(error.message);}
  }
  return <section className="panel settings-panel"><div className="toolbar"><h2>센서 설정</h2><span>Raspberry Pi · Python 수집 프로그램</span></div>
    <p>이 화면은 설정 파일을 작성하는 곳입니다. 현재 장비의 설정을 조회하거나 원격 변경하지 않습니다.</p>
    <form onSubmit={e=>{e.preventDefault();save();}}>
      <div className="settings-groups">{sensorGroups.map(([prefix,name,description])=>
        <fieldset className="settings-group" key={prefix}>
          <legend>{name}<span>{description}</span></legend>
          <div className="settings-fields">{fields.filter(([key])=>key.startsWith(prefix)).map(([key,label,initial])=>
            <label key={key}>{label.replace(new RegExp(`^${name} `),'')}<input required type={typeof initial==='number'?'number':'text'} step={typeof initial==='number'?1:undefined} value={values[key]} onChange={e=>setValues({...values,[key]:typeof initial==='number'?(e.target.value===''?'':Number(e.target.value)):e.target.value})}/></label>
          )}</div>
        </fieldset>
      )}</div>
    <div className="settings-actions"><button type="submit">브라우저에 저장</button><button type="button" onClick={()=>save(true)}>설정 JSON 내보내기</button><button type="button" onClick={()=>{setValues({...defaults});setMessage('기본값을 불러왔습니다. 저장 또는 내보내기로 확정하세요.');}}>기본값 불러오기</button></div></form>
    <p role="status">{message}</p><h3>장비에 적용하기</h3><ol><li>JSON 파일을 Raspberry Pi의 프로젝트 폴더에 복사합니다.</li><li>실행 중인 센서 수집 프로그램을 종료합니다.</li><li>프로젝트 루트에서 아래 명령으로 재실행합니다.</li></ol><pre>python3 -m RaspberryPi.python.main --sensor-config sensor-settings.json</pre><p>기존 실행 옵션은 함께 지정하세요. GPS 수집은 기존처럼 --speed-source gps일 때 사용됩니다. BME280 버스는 기존 board.I2C()를 사용하며 주소만 변경합니다. 통신 속도는 센서에 설정된 값과 일치해야 합니다.</p>
  </section>;
}
