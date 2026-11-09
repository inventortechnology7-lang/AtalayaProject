import {useEffect,useState} from 'react';
export function useLive(token:string){
 const [live,setLive]=useState(false),[revision,setRevision]=useState(0);
 useEffect(()=>{if(!token)return;let stopped=false;const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;
  async function connect(){try{const r=await fetch('/api/local/events',{headers:{Authorization:'Bearer '+token},signal:controller.signal});if(!r.ok||!r.body)throw Error('SSE');setLive(true);const reader=r.body.getReader(),decoder=new TextDecoder();let buffer='';while(!stopped){const part=await reader.read();if(part.done)break;buffer+=decoder.decode(part.value,{stream:true}).replace(/\r/g,'');let end;while((end=buffer.indexOf('\n\n'))>=0){buffer=buffer.slice(end+2);setRevision(v=>v+1);}}}catch{}finally{if(!stopped){setLive(false);timer=setTimeout(connect,3000);}}}void connect();const fallback=setInterval(()=>setRevision(v=>v+1),15000);return()=>{stopped=true;controller.abort();clearTimeout(timer);clearInterval(fallback);setLive(false);};
 },[token]);return {live,revision};
}
