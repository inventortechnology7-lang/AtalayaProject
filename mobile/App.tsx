import React,{useState,useEffect,useCallback,useRef} from 'react';
import {SafeAreaView,ScrollView,Text,TextInput,Button,View,Alert,StyleSheet,Platform,AppState} from 'react-native';
import * as SecureStore from 'expo-secure-store';
import * as FileSystem from 'expo-file-system/legacy';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';
import {fetch as streamFetch} from 'expo/fetch';
import type {Dashboard,Door,RecordRow,User} from './types';
import {labels} from './types';
const base=(process.env.EXPO_PUBLIC_API_URL||'').replace(/\/$/,'');
type Snapshot={dashboard:Dashboard;notifications:RecordRow[];history:RecordRow[];at:string};
const cache=FileSystem.documentDirectory+'atalaya-readonly.json';
const message=(e:unknown)=>e instanceof Error?e.message:String(e);
const payload=(r:RecordRow):RecordRow=>{try{return typeof r.payload==='string'?JSON.parse(r.payload):r;}catch{return r;}};
export default function App(){
 const [token,setToken]=useState(''),[correo,setCorreo]=useState(''),[clave,setClave]=useState(''),[user,setUser]=useState<User|null>(null),[data,setData]=useState<Snapshot|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[online,setOnline]=useState(false),[live,setLive]=useState(false),[reason,setReason]=useState('');
 const generation=useRef(0);
 const clear=useCallback(async()=>{generation.current++;setToken('');setUser(null);setData(null);setOnline(false);await SecureStore.deleteItemAsync('atalaya-token');await FileSystem.deleteAsync(cache,{idempotent:true});},[]);
 const request=useCallback(async(path:string,body?:unknown,t=token)=>{
  if(!base.startsWith('https://'))throw Error('Configura EXPO_PUBLIC_API_URL con HTTPS.');
  const r=await fetch(base+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json',...(t?{Authorization:'Bearer '+t}:{})},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(10000)});
  if(!r.ok){if(r.status===401)await clear();throw Error(r.status===409?'Control bloqueado: verifica enlace, estado y validación física.':'Solicitud rechazada ('+r.status+').');}
  const text=await r.text();return text?JSON.parse(text):{};
 },[token,clear]);
 const refresh=useCallback(async()=>{
  const epoch=generation.current;
  try{
   const [dashboard,notifications,history,me]=await Promise.all([request('/api/dashboard'),request('/api/notifications'),request('/api/history'),request('/api/me')]);
   if(epoch!==generation.current)return;
   const snapshot:Snapshot={dashboard,notifications,history,at:new Date().toISOString()};
   setData(snapshot);setUser(me);setOnline(true);setError('');
   await FileSystem.writeAsStringAsync(cache,JSON.stringify({base,email:me.email,snapshot})).catch(()=>{});
  }catch(e){if(epoch===generation.current){setOnline(false);setError(message(e));}}
 },[request]);
 useEffect(()=>{let active=true;void SecureStore.getItemAsync('atalaya-token').then(async t=>{
  if(!active||!t)return;setToken(t);
  try{const saved=JSON.parse(await FileSystem.readAsStringAsync(cache));if(active&&saved.base===base)setData(saved.snapshot);}catch{}
 }).catch(e=>setError(message(e)));return()=>{active=false;};},[]);
 useEffect(()=>{
  if(!token)return;
  void refresh();
  const id=setInterval(refresh,15000);
  const subscription=AppState.addEventListener('change',state=>{if(state==='active')void refresh();else setOnline(false);});
  return()=>{clearInterval(id);subscription.remove();};
 },[token,refresh]);
 useEffect(()=>{
  if(!token||!base.startsWith('https://'))return;
  const controller=new AbortController();let stopped=false;let timer:ReturnType<typeof setTimeout>;
  async function connect(){try{
   const r=await streamFetch(base+'/api/eventos',{headers:{Authorization:'Bearer '+token},signal:controller.signal});
   if(!r.ok||!r.body)throw Error('SSE');
   setLive(true);const reader=r.body.getReader();const decoder=new TextDecoder();let buffer='';
   while(!stopped){const part=await reader.read();if(part.done)break;buffer+=decoder.decode(part.value,{stream:true}).replace(/\r/g,'');let i;while((i=buffer.indexOf('\n\n'))>=0){buffer=buffer.slice(i+2);void refresh();}}
  }catch{}finally{if(!stopped){setLive(false);timer=setTimeout(connect,5000);}}}
  void connect();return()=>{stopped=true;controller.abort();clearTimeout(timer);};
 },[token,refresh]);
 async function login(){setBusy(true);try{await FileSystem.deleteAsync(cache,{idempotent:true});generation.current++;const r=await request('/api/login',{correo,clave},'');await SecureStore.setItemAsync('atalaya-token',r.token);setClave('');setData(null);setToken(r.token);setError('');}catch(e){setError(message(e));}finally{setBusy(false);}}
 async function push(){setBusy(true);try{
  if(!Device.isDevice)throw Error('Expo Push requiere un dispositivo físico y una build configurada.');
  const projectId=Constants.expoConfig?.extra?.eas?.projectId||Constants.easConfig?.projectId;
  if(!projectId)throw Error('Configura el projectId de EAS antes de registrar Expo Push.');
  if(Platform.OS==='android')await Notifications.setNotificationChannelAsync('default',{name:'Alarmas ATALAYA',importance:Notifications.AndroidImportance.HIGH});
  const permission=await Notifications.requestPermissionsAsync();if(permission.status!=='granted')throw Error('Permiso de notificaciones no concedido.');
  const result=await Notifications.getExpoPushTokenAsync({projectId});await request('/api/push-token',{token:result.data});await SecureStore.setItemAsync('atalaya-push',result.data);Alert.alert('Registro guardado','La entrega requiere habilitar Expo Push en el servidor; aún no confirma recepción en el dispositivo.');
 }catch(e){setError(message(e));}finally{setBusy(false);}}
 async function action(path:string,body:unknown){setBusy(true);try{await request(path,body);await refresh();}catch(e){setError(message(e));setOnline(false);}finally{setBusy(false);}}
 async function logout(){try{const push=await SecureStore.getItemAsync('atalaya-push');if(push)await request('/api/push-token/remove',{token:push});await request('/api/logout',{});}catch{}finally{await SecureStore.deleteItemAsync('atalaya-push');await clear();}}
 const dashboard=data?.dashboard;
 const linked=online&&!!dashboard?.pantalla.ultimoContacto&&Date.now()-new Date(dashboard.pantalla.ultimoContacto).getTime()<60000;
 function controls(d:Door){const enabled=linked&&live&&!busy&&user?.role==='ADMIN'&&d.safety_validated&&Date.now()-new Date(d.observed).getTime()<45000&&['cerrada','abierta','trabada'].includes(d.state)&&!!reason.trim();return ['ORDEN','REINICIO'].map(linea=><Button key={linea} title={linea} disabled={!enabled} onPress={()=>Alert.alert('Confirmar intervención',linea+' a puerta '+d.id+'. Confirmo revisión presencial de protecciones y obstrucciones. La entrega TCP no confirma movimiento.',[{text:'Cancelar',style:'cancel'},{text:'Enviar',onPress:()=>action('/api/comandos',{destino:'puerta-'+d.id,linea,origen:'app',confirmed:true,reason})}])}/>);}
 return <SafeAreaView style={s.root}><ScrollView contentContainerStyle={s.body}>
 <Text style={s.brand}>ATALAYA</Text><Text style={s.subtitle}>Supervisión de puertas</Text>
 {!!error&&<Text accessibilityRole="alert" style={s.error}>{error}</Text>}
 {!token?<View style={s.card}><Text style={s.title}>Acceso al sistema</Text><TextInput style={s.input} accessibilityLabel="Correo" placeholder="Correo" autoCapitalize="none" keyboardType="email-address" value={correo} onChangeText={setCorreo}/><TextInput style={s.input} accessibilityLabel="Contraseña" placeholder="Contraseña" secureTextEntry value={clave} onChangeText={setClave}/><Button title="Ingresar" disabled={busy} onPress={login}/></View>:<>
 <View style={s.card}><Text style={s.title}>{linked?'Katana conectado':'Sin enlace reciente'}</Text><Text>{online?'Consulta actualizada':'Caché de solo lectura · datos posiblemente desactualizados'}</Text><Text>{live?'SSE conectado':'SSE reconectando · consulta cada 15 s'}</Text><Text>Última consulta: {data?.at?new Date(data.at).toLocaleString():'Sin datos'}</Text><Button title="Actualizar" onPress={refresh}/></View>
 {!dashboard?.doors.length&&<Text>Sin puertas observadas. No se presupone ningún dispositivo.</Text>}
 {dashboard?.doors.map(d=><View key={d.id} style={s.card}><Text style={s.title}>Puerta {d.id} · {labels[d.state]||d.state}</Text><Text>Nodo {d.node} · {new Date(d.observed).toLocaleString()}</Text><Text>Control {d.safety_validated?'con validación registrada':'bloqueado: falta validación física'}</Text>{controls(d)}</View>)}
 {user?.role==='ADMIN'&&<View style={s.card}><Text>Motivo de intervención</Text><TextInput accessibilityLabel="Motivo" style={s.input} value={reason} onChangeText={setReason}/><Text>Sin recuperación eléctrica automática. Nunca se encolan maniobras offline.</Text></View>}
 {(['alarmas','logs'] as const).map(kind=><View key={kind} style={s.card}><Text style={s.title}>{kind==='alarmas'?'Alarmas':'Actividad'}</Text>{!dashboard?.[kind].length&&<Text>Sin registros.</Text>}{dashboard?.[kind].map(r=><Text key={r.uid} style={s.row}>{String(r.detalle||r.mensaje)} · {String(r.estado||'')} · {String(r.creada||r.t)}</Text>)}</View>)}
 <View style={s.card}><Text style={s.title}>Notificaciones persistentes</Text><Button title="Activar Expo Push" disabled={busy||!online} onPress={push}/>{!data?.notifications.length&&<Text>Sin notificaciones.</Text>}{data?.notifications.map(r=><View key={r.id} style={s.row}><Text>{String(payload(r).detalle)} · {String(payload(r).estado)}</Text><Button title={r.read_at?'Leída':'Marcar leída'} disabled={!!r.read_at||!online||busy} onPress={()=>action('/api/notifications/'+r.id+'/read',{})}/></View>)}</View>
 <View style={s.card}><Text style={s.title}>Historial · 30 días</Text>{!data?.history.length&&<Text>Sin historial.</Text>}{data?.history.map((r,i)=><Text key={i} style={s.row}>{new Date(String(r.day)).toLocaleDateString()} · {String(r.kind)} · {String(r.count)} reportes</Text>)}<Text>Los reportes no certifican movimientos ni disponibilidad física.</Text></View>
 <Button title="Cerrar sesión" onPress={logout}/></>}
 </ScrollView></SafeAreaView>;
}
const s=StyleSheet.create({root:{flex:1,backgroundColor:'#f3f6fa'},body:{padding:24,paddingTop:48},brand:{fontSize:28,fontWeight:'800',letterSpacing:4,color:'#173e75'},subtitle:{color:'#65748a',marginBottom:24},card:{backgroundColor:'white',borderRadius:14,padding:20,marginBottom:18},title:{fontSize:20,fontWeight:'600',marginBottom:16,color:'#18263d'},input:{borderWidth:1,borderColor:'#cbd5e3',padding:12,borderRadius:8,marginVertical:12},error:{padding:16,color:'#a22c20'},row:{paddingVertical:12,borderBottomWidth:1,borderColor:'#edf0f5'}});
