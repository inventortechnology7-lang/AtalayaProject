export interface Door {id:string;node:string;state:string;reported_state:string;observed:string;raw:string;safety_validated:boolean}
export interface User {email:string;role:string;condo:number}
export interface RecordRow {uid?:string;id?:number;[key:string]:unknown}
export interface Dashboard {doors:Door[];pantalla:{ultimoContacto?:string};alarmas:RecordRow[];logs:RecordRow[];muestras:RecordRow[];comandos:RecordRow[]}
export const labels:Record<string,string>={cerrada:'Cerrada',abriendo:'Abriendo',abierta:'Abierta',cerrando:'Cerrando',trabada:'Trabada',desconocida:'Desconocida',sin_comunicacion:'Sin comunicación con nodo',edge_sin_enlace:'Katana sin enlace'};
