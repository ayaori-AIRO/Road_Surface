"""Build a standalone interactive snow-error chart (no network required)."""
import json
from pathlib import Path

import pandas as pd

ML_DIR = Path(__file__).resolve().parents[1]
SOURCE = ML_DIR / "dataset/predict_noise_snow/RoadSurf_Synthetic_TestSet_02_predicted.xlsx"
OUTPUT = SOURCE.with_name(SOURCE.stem + "_snow_error.html")


def main():
    with pd.ExcelFile(SOURCE) as book:
        sheet = next(s for s in book.sheet_names if "snow_height_absolute_error_m" in
                     pd.read_excel(book, sheet_name=s, nrows=0).columns)
        df = pd.read_excel(book, sheet_name=sheet)
    error = pd.to_numeric(df["snow_height_absolute_error_m"], errors="raise") * 1000
    if error.isna().any() or not error.ge(0).all():
        raise ValueError("Invalid error values")
    # Reset the moving average at each session boundary.
    average = error.groupby(df["run_id"], sort=False).transform(
        lambda values: values.rolling(50, min_periods=1).mean())
    data = {"error": error.tolist(), "average": average.tolist(),
            "run": df.run_id.tolist(), "time": df.time_s.tolist(),
            "scenario": df.scenario.tolist(), "mean": float(error.mean()),
            "p95": float(error.quantile(.95)), "maximum": float(error.max())}
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=True, allow_nan=False))
    OUTPUT.write_text(html, encoding="utf-8")
    print(OUTPUT)
    print(f"Rows={len(df)}; mean={data['mean']:.3f} mm; P95={data['p95']:.3f} mm; max={data['maximum']:.3f} mm")


TEMPLATE = r'''<!doctype html>
<html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>눈 높이 절대오차 · TestSet 02</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#0b1019;color:#dce5f2;font:14px system-ui,sans-serif}
main{max-width:1600px;margin:auto;padding:28px}h1{font-size:25px;margin:8px 0}.muted{color:#8c9db4;line-height:1.7}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}.card{background:#141e2d;border:1px solid #263449;border-radius:10px;padding:18px}.value{font-size:27px;margin-top:8px;font-weight:650}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:16px 0}button,select{background:#1b293c;color:#e0e9f5;border:1px solid #35465d;padding:9px 13px;border-radius:6px;cursor:pointer}
.panel{background:#101925;border:1px solid #28384e;border-radius:12px;padding:15px;position:relative}canvas{width:100%;display:block;touch-action:none}#chart{height:460px;cursor:crosshair}#overview{height:75px;margin-top:12px;cursor:pointer}
.legend{display:flex;gap:22px;flex-wrap:wrap;color:#9caec4;margin:6px 0 12px}.teal{color:#34d4b4}.gold{color:#ffc861}.purple{color:#bb9cff}
#tip{position:absolute;display:none;background:#1d2b3ef2;border:1px solid #52708c;padding:12px;border-radius:7px;pointer-events:none;line-height:1.7;z-index:2}
.range{display:flex;align-items:center;gap:10px;margin-top:15px}.range input{flex:1;accent-color:#34d4b4}.foot{margin-top:16px}@media(max-width:650px){main{padding:12px}.cards{grid-template-columns:repeat(2,1fr)}#chart{height:350px}.value{font-size:23px}}
</style>
<main><div class="muted">ROAD SURFACE / MODEL DIAGNOSTICS</div><h1>눈 높이 절대오차 <span class="teal">TestSet 02</span></h1>
<div class="muted">snow_height_absolute_error_m × 1,000 · 단위 mm · 작을수록 정확합니다</div>
<div class="cards"><div class="card">전체 평균 절대오차<div class="value teal" id="mean"></div></div><div class="card">전체 95백분위<div class="value" id="p95"></div></div><div class="card">최대 절대오차<div class="value gold" id="maximum"></div></div><div class="card">현재 구간 평균<div class="value" id="visible"></div></div></div>
<div class="toolbar"><select id="session"><option value="all">전체 30개 세션</option></select><button id="all">전체 보기</button><button id="in">확대 +</button><button id="out">축소 −</button><span class="muted">휠: 확대/축소 · 드래그: 좌우 이동 · 마우스: 상세값</span></div>
<div class="panel"><div class="legend"><span class="teal">━ 행별 절대오차</span><span class="gold">━ 50개 샘플 이동평균 (세션별)</span><span class="purple">┄ 전체 평균</span></div><canvas id="chart"></canvas><canvas id="overview"></canvas><div id="tip"></div><div class="range"><span>구간 이동</span><input id="pan" type="range" min="0" step="1" value="0"><span id="rangeText"></span></div></div>
<div class="muted foot">가로축은 엑셀 행 번호(2~18,001)입니다. 1행은 헤더이며, 엑셀의 m 값에 1,000을 곱해 mm로 표시합니다. 각 세션의 time_s가 다시 시작하므로 전체를 하나의 연속 시간으로 해석하지 않습니다. 세로 점선은 세션 경계이며, 이동평균은 세션마다 초기화합니다. 50개 샘플은 이 데이터의 약 5초에 해당합니다. 원자료를 유지하며, 확대하면 개별 오차를 확인할 수 있습니다.</div></main>
<script>
const D=__DATA__,N=D.error.length,c=document.querySelector('#chart'),o=document.querySelector('#overview'),tip=document.querySelector('#tip');
let start=0,end=N,hover=-1,drag=null;
const $=s=>document.querySelector(s),fmt=v=>v.toFixed(2)+' mm';
for(const k of ['mean','p95','maximum'])$('#'+k).textContent=fmt(D[k]);
const sessions=[];for(let i=0;i<N;i++)if(i===0||D.run[i]!==D.run[i-1])sessions.push(i);
sessions.forEach((s,i)=>{const opt=document.createElement('option');opt.value=i;opt.textContent=D.run[s]+' · '+D.scenario[s];$('#session').append(opt)});
function setup(canvas){const r=canvas.getBoundingClientRect(),ratio=devicePixelRatio||1;canvas.width=Math.round(r.width*ratio);canvas.height=Math.round(r.height*ratio);const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);return [ctx,r.width,r.height]}
function windowTo(s,e){let size=Math.min(N,Math.max(30,Math.round(e-s)));start=Math.max(0,Math.min(N-size,Math.round(s)));end=start+size;hover=-1;tip.style.display='none';draw()}
function draw(){const [ctx,w,h]=setup(c),L=66,R=w-22,T=22,B=h-38,pw=R-L,ph=B-T;const vals=D.error.slice(start,end),ymax=Math.max(.1,...vals)*1.12;
 const X=i=>L+(i-start)/Math.max(1,end-start-1)*pw,Y=v=>B-v/ymax*ph;
 ctx.font='12px system-ui';ctx.lineWidth=1;for(let j=0;j<=5;j++){let y=T+ph*j/5;ctx.strokeStyle='#263347';ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(R,y);ctx.stroke();ctx.fillStyle='#8fa2bc';ctx.fillText((ymax*(1-j/5)).toFixed(1),8,y+4)}ctx.fillText('오차 (mm)',8,12);
 for(let j=0;j<=5;j++){let i=Math.round(start+(end-start-1)*j/5);ctx.fillText((i+2).toLocaleString(),Math.min(R-38,Math.max(L-10,X(i)-15)),h-12)}
 ctx.save();ctx.beginPath();ctx.rect(L,T,pw,ph);ctx.clip();ctx.setLineDash([3,5]);ctx.strokeStyle='#354760';for(const s of sessions)if(s>start&&s<end){ctx.beginPath();ctx.moveTo(X(s),T);ctx.lineTo(X(s),B);ctx.stroke()}ctx.setLineDash([]);
 function line(values,color,width){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();for(let i=start;i<end;i++){if(i===start||D.run[i]!==D.run[i-1])ctx.moveTo(X(i),Y(values[i]));else ctx.lineTo(X(i),Y(values[i]))}ctx.stroke()}
 line(D.error,'#34d4b499',1);line(D.average,'#ffc861',1.7);ctx.strokeStyle='#bb9cff';ctx.setLineDash([7,5]);ctx.beginPath();ctx.moveTo(L,Y(D.mean));ctx.lineTo(R,Y(D.mean));ctx.stroke();ctx.setLineDash([]);
 if(hover>=start&&hover<end){ctx.strokeStyle='#a5b4c9';ctx.beginPath();ctx.moveTo(X(hover),T);ctx.lineTo(X(hover),B);ctx.moveTo(L,Y(D.error[hover]));ctx.lineTo(R,Y(D.error[hover]));ctx.stroke()}ctx.restore();
 $('#visible').textContent=fmt(vals.reduce((a,b)=>a+b,0)/vals.length);$('#pan').max=N-(end-start);$('#pan').value=start;$('#rangeText').textContent=(start+2).toLocaleString()+'–'+(end+1).toLocaleString();
 const [oc,ow,oh]=setup(o),max=D.maximum||1;oc.strokeStyle='#34d4b480';oc.beginPath();D.error.forEach((v,i)=>{const x=i/(N-1)*ow,y=oh-5-v/max*(oh-10);i?oc.lineTo(x,y):oc.moveTo(x,y)});oc.stroke();oc.fillStyle='#82b4f52b';oc.fillRect(start/N*ow,0,(end-start)/N*ow,oh);oc.strokeStyle='#91aaca';oc.strokeRect(start/N*ow,.5,(end-start)/N*ow,oh-1);
}
function zoom(f,anchor=.5){let width=(end-start)*f;windowTo(start+(end-start-width)*anchor,start+(end-start-width)*anchor+width)}
c.addEventListener('wheel',e=>{e.preventDefault();zoom(e.deltaY>0?1.3:1/1.3,Math.max(0,Math.min(1,(e.offsetX-66)/(c.clientWidth-88))));$('#session').value='all'},{passive:false});
c.addEventListener('pointerdown',e=>{drag={x:e.clientX,s:start,n:end-start};c.setPointerCapture(e.pointerId)});
c.addEventListener('pointerup',()=>drag=null);c.addEventListener('pointercancel',()=>drag=null);
c.addEventListener('pointermove',e=>{if(drag){const delta=-(e.clientX-drag.x)/(c.clientWidth-88)*drag.n;windowTo(drag.s+delta,drag.s+delta+drag.n);$('#session').value='all';return}const r=c.getBoundingClientRect();hover=Math.max(start,Math.min(end-1,Math.round(start+(e.clientX-r.left-66)/(r.width-88)*(end-start-1))));draw();tip.style.display='block';tip.textContent='';const lines=[D.run[hover]+' · '+D.scenario[hover],'엑셀 행 '+(hover+2)+' (데이터 '+(hover+1)+') / 세션 시간 '+D.time[hover].toFixed(1)+' s','절대오차 '+fmt(D.error[hover]),'이동평균 '+fmt(D.average[hover])];for(const text of lines){const div=document.createElement('div');div.textContent=text;tip.append(div)}tip.style.left=Math.max(5,Math.min(e.clientX-r.left+25,r.width-285))+'px';tip.style.top='65px'});
c.addEventListener('pointerleave',()=>{hover=-1;tip.style.display='none';draw()});
$('#session').onchange=e=>{if(e.target.value==='all')windowTo(0,N);else{const i=+e.target.value;windowTo(sessions[i],sessions[i+1]||N)}};
$('#all').onclick=()=>{$('#session').value='all';windowTo(0,N)};$('#in').onclick=()=>zoom(.5);$('#out').onclick=()=>zoom(2);
$('#pan').oninput=e=>{const n=end-start;windowTo(+e.target.value,+e.target.value+n);$('#session').value='all'};
o.onclick=e=>{const n=end-start;const center=e.offsetX/o.clientWidth*N;windowTo(center-n/2,center+n/2)};
window.addEventListener('resize',draw);draw();
</script></html>'''

if __name__ == "__main__":
    main()
