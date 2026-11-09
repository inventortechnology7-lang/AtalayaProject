export type User={email:string;name:string;role:string};
export type Row=Record<string,unknown>;
export type Door={id:string;node:string;state:string;unavailable:boolean;sensor_1:number|null;sensor_2:number|null;motor:number|null;observed_at:string};
export type Dashboard={connected_nodes:number;nodes:number;active_alarms:number;last_contact:string|null;doors:Door[]};
export type Snapshot={dashboard:Dashboard;alarms:Row[];logs:Row[];history:Row[];at:string};
