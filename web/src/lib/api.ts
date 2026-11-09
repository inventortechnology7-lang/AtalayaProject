export type Row = Record<string, unknown>;
export type User = {email:string;name:string;role:'ADMIN'|'TECNICO'|'OPERADOR'};
export type Door = {id:string;node:string;state:string;unavailable:boolean;sensor_1:number|null;sensor_2:number|null;motor:number|null;observed_at:string;last_contact:string};
export type Dashboard = {nodes:number;connected_nodes:number;active_alarms:number;faults:number;last_contact:string|null;doors:Door[];at:string;site:string};
export type Page = {content:Row[];total:number;page:number;size:number};
export class Api {
 constructor(public token:string, private expired:()=>void){}
 async get<T>(path:string,body?:unknown,method=body===undefined?'GET':'POST'):Promise<T>{
  const response=await fetch('/api/local'+path,{method,headers:{'Content-Type':'application/json',...(this.token?{Authorization:'Bearer '+this.token}:{})},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(10000)});
  if(!response.ok){if(response.status===401&&this.token)this.expired();let message='No se pudo completar la solicitud ('+response.status+').';try{message=(await response.json()).error||message;}catch{}throw Error(message);}
  const text=await response.text();return (text?JSON.parse(text):undefined) as T;
 }
}
export const date=(value:unknown)=>value?new Date(String(value)).toLocaleString('es-PE'):'Sin dato';
export const text=(value:unknown)=>value==null?'—':typeof value==='object'?JSON.stringify(value):String(value);
