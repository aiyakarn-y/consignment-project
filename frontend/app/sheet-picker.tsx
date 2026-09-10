'use client';

import {useEffect,useRef,useState} from 'react';

export type SheetChoice={name:string;kind:string;supported:boolean;reason:string;suggested:boolean};
export type ImportCheck={name:string;same_batch:boolean;previous:{period:string;name:string;batch_id:string}[];sheets:SheetChoice[]};
export type SheetSelection=Record<string,string[]>;
export type SheetRequest={checks:ImportCheck[];resolve:(selection:SheetSelection|null)=>void};

export default function SheetPicker({request,onDone}:{request:SheetRequest;onDone:(selection:SheetSelection|null)=>void}){
 const panel=useRef<HTMLElement>(null);
 const files=request.checks.map((file,index)=>({file,index})).filter(({file})=>file.sheets.length>1);
 const [selected,setSelected]=useState<SheetSelection>(()=>Object.fromEntries(files.map(({file,index})=>[String(index),file.sheets.filter(s=>s.supported).length===1?file.sheets.filter(s=>s.supported).map(s=>s.name):[]])));
 useEffect(()=>{
  const previous=document.activeElement as HTMLElement|null;
  panel.current?.focus();
  const key=(event:KeyboardEvent)=>{
   if(event.key==='Escape'){event.preventDefault();onDone(null);}
   if(event.key==='Tab'){
    const elements=Array.from(panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled)')||[]);
    const first=elements[0],last=elements[elements.length-1];
    if(event.shiftKey&&(document.activeElement===first||document.activeElement===panel.current)){event.preventDefault();last?.focus();}
    else if(!event.shiftKey&&(document.activeElement===last||document.activeElement===panel.current)){event.preventDefault();first?.focus();}
   }
  };
  document.addEventListener('keydown',key);return()=>{document.removeEventListener('keydown',key);previous?.focus();};
 },[onDone]);
 return <div className="drawer-overlay"><section ref={panel} tabIndex={-1} className="drawer" role="dialog" aria-modal="true" aria-labelledby="sheet-picker-title">
  <div className="drawer-heading"><h2 id="sheet-picker-title">เลือกชีตที่จะนำเข้า</h2></div>
  <div className="drawer-body"><p>เลือกเฉพาะชีตรายละเอียดขาย หากมีชีตสรุปยอดเดียวกันให้ข้าม เพื่อไม่รวมซ้ำ ระบบจะบันทึกผลรายชีตให้ตรวจหลังนำเข้า</p>
   {files.map(({file,index})=><fieldset key={index} className="sheet-selection"><legend>{file.name}</legend>{file.sheets.map(sheet=><label className="checkbox" key={sheet.name}>
    <input type="checkbox" aria-label={`นำเข้าชีต ${sheet.name} ของ ${file.name}`} disabled={!sheet.supported} checked={selected[index]?.includes(sheet.name)||false} onChange={event=>setSelected(value=>({...value,[index]:event.target.checked?[...(value[index]||[]),sheet.name]:(value[index]||[]).filter(name=>name!==sheet.name)}))}/>
    <span>{sheet.name}<small>{sheet.supported?sheet.kind:sheet.reason}</small></span>
   </label>)}{!file.sheets.some(s=>s.supported)&&<p role="alert">ยังไม่มีชีตที่ตรงรูปแบบ กรุณาตั้งค่า Mapping ก่อนนำเข้า</p>}</fieldset>)}
  </div>
  <div className="drawer-footer"><button className="button secondary" onClick={()=>onDone(null)}>ยกเลิกการเลือกชีต</button><button className="button primary" disabled={files.some(({index})=>!selected[index]?.length)} onClick={()=>onDone(selected)}>ยืนยันชีตและนำเข้า</button></div>
 </section></div>;
}
