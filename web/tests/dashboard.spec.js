import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import net from 'node:net';
import path from 'node:path';
const env={...Object.fromEntries(fs.readFileSync(path.resolve('..',process.env.KATANA_ENV_FILE||'.env'),'utf8').split('\n').filter(x=>x.includes('=')&&!x.startsWith('#')).map(x=>{const i=x.indexOf('=');return [x.slice(0,i),x.slice(i+1)];})),...process.env};
async function board(){const socket=net.createConnection({host:process.env.KATANA_TCP_HOST||'127.0.0.1',port:Number(process.env.KATANA_TCP_PORT||18300)});socket.on('error',()=>{});await new Promise((ok,no)=>{socket.once('connect',ok);socket.once('error',no);});await new Promise((ok,no)=>{socket.once('data',b=>b.toString().startsWith('HORA ')?ok():no(Error('Missing HORA')));socket.write('TOKEN '+env.PLACA_TOKEN+'\n');});const alarm=[[0,2,0,1794090000,'Alarma de banco · Sensor 2']];socket.write(JSON.stringify({cfg:{cor:['Puertas'],version:'simulador'},st:{pue:'A',puerta:'cerrada',el:[0,1,0],al:alarm},log:{t:1794090000,v:1,s:'Puertas',m:'Puerta A registro de banco'},m:[['Puertas','voltaje',12.3,'V']]})+'\n');socket.write(JSON.stringify({st:{pue:'B',puerta:'abierta',el:[0,0,0],al:alarm}})+'\n');return socket;}
for(const viewport of [{width:1440,height:1000},{width:390,height:844}])test('Katana real TCP/API '+viewport.width,async({page})=>{
 await page.setViewportSize(viewport);const socket=await board();try{
 await page.goto('/');await expect(page.getByRole('heading',{name:'Bienvenido a Katana'})).toBeVisible();await page.getByLabel('Correo',{exact:true}).fill(env.ADMIN_EMAIL);await page.getByLabel('Contraseña',{exact:true}).fill(env.ADMIN_PASSWORD);await page.getByRole('button',{name:'Ingresar →',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Resumen',exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'Puerta A',exact:true})).toBeVisible();await expect(page.getByText('Falla reportada',{exact:true})).toBeVisible();await expect(page.getByText('● En vivo',{exact:true})).toBeVisible();
 await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:`test-results/katana-${viewport.width}.png`,fullPage:true});
 for(const [path,title] of [['/doors','Puertas'],['/nodes','Nodos'],['/alarms','Alarmas'],['/logs','Registros'],['/history','Historial'],['/telemetry','Telemetría'],['/settings','Usuarios y configuración']]){await page.locator(`nav a[href="${path}"]`).click();await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();if(path==='/logs'){await page.getByLabel('Buscar',{exact:true}).fill('registro de banco');await expect(page.getByRole('cell',{name:'Puerta A registro de banco',exact:true})).toBeVisible();}if(path==='/telemetry')await expect(page.getByRole('cell',{name:'voltaje',exact:true}).first()).toBeVisible();}
 await page.getByRole('button',{name:'Cambiar tema'}).click();await page.screenshot({path:`test-results/katana-settings-${viewport.width}.png`,fullPage:true});
 await page.locator('nav a[href="/"]').click();socket.end();await expect(page.getByText('Sin datos actuales',{exact:true}).first()).toBeVisible({timeout:20000});await expect(page.locator('body')).not.toContainText('Centro de operación');await expect(page.getByRole('button',{name:/ORDEN|REINICIO/})).toHaveCount(0);
 await page.getByRole('button',{name:'Cerrar sesión',exact:true}).click();await expect(page.getByRole('heading',{name:'Bienvenido a Katana'})).toBeVisible();
 }finally{socket.destroy();}
});
