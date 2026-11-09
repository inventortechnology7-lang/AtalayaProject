import * as SecureStore from 'expo-secure-store';
import {Platform} from 'react-native';
// Web preview deliberately keeps sensitive data in memory only.
const memory=new Map<string,string>();
export async function read(key:string){return Platform.OS==='web'?memory.get(key)||null:SecureStore.getItemAsync(key);}
export async function write(key:string,value:string){if(Platform.OS==='web')memory.set(key,value);else await SecureStore.setItemAsync(key,value,{keychainAccessible:SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY});}
export async function remove(key:string){if(Platform.OS==='web')memory.delete(key);else await SecureStore.deleteItemAsync(key);}
export async function saveCache(value:unknown){const serialized=JSON.stringify(value);if(serialized.length>90000)return;const old=await read('katana-cache-meta');const version=String(Date.now());const chunks=Math.ceil(serialized.length/1500);for(let i=0;i<chunks;i++)await write('katana-cache-'+version+'-'+i,serialized.slice(i*1500,(i+1)*1500));await write('katana-cache-meta',JSON.stringify({version,chunks}));if(old){const previous=JSON.parse(old);for(let i=0;i<previous.chunks;i++)await remove('katana-cache-'+previous.version+'-'+i);}}
export async function loadCache(){const raw=await read('katana-cache-meta');if(!raw)return null;const {version,chunks}=JSON.parse(raw);let result='';for(let i=0;i<chunks;i++){const chunk=await read('katana-cache-'+version+'-'+i);if(chunk===null)return null;result+=chunk;}return JSON.parse(result);}
export async function clearCache(){const raw=await read('katana-cache-meta');await remove('katana-cache-meta');if(raw){const {version,chunks}=JSON.parse(raw);for(let i=0;i<chunks;i++)await remove('katana-cache-'+version+'-'+i);}}
