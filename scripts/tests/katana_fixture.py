"""Synthetic migration data; never served to an application or production dashboard."""
import hashlib
import json
import sqlite3


def create(root):
    with sqlite3.connect(root/'katana.db') as db:
        db.executescript('''
CREATE TABLE nodos(nodo TEXT PRIMARY KEY,direccion TEXT,sistemas TEXT,primera_conexion REAL,ultimo_contacto REAL,conectado INTEGER);
CREATE TABLE puertas(pue TEXT PRIMARY KEY,nodo TEXT,puerta TEXT,el TEXT,up INTEGER,actualizado REAL,caida INTEGER);
CREATE TABLE alarmas(uid TEXT PRIMARY KEY,nodo TEXT,sistema TEXT,sev INTEGER,reconocida INTEGER,t REAL,detalle TEXT,abierta INTEGER,cerrada_en REAL);
CREATE TABLE logs(uid TEXT PRIMARY KEY,nodo TEXT,t REAL,sev INTEGER,sistema TEXT,msg TEXT);
CREATE TABLE muestras(uid TEXT PRIMARY KEY,nodo TEXT,recibido REAL,sistema TEXT,magnitud TEXT,valor REAL,unidad TEXT);
CREATE TABLE pantalla(id INTEGER PRIMARY KEY,nodo TEXT,cfg TEXT,st TEXT,version INTEGER,cambiado REAL);
CREATE TABLE outbox(id INTEGER PRIMARY KEY,uid TEXT,tipo TEXT,payload TEXT,creado REAL,enviado REAL);
CREATE TABLE ordenes_web(id INTEGER PRIMARY KEY,linea TEXT,estado TEXT);
''')
        db.execute('INSERT INTO nodos VALUES(?,?,?,?,?,?)',('192.0.2.1','192.0.2.1:8300','["Puertas"]',1794090000,1794090020,1))
        db.execute('INSERT INTO puertas VALUES(?,?,?,?,?,?,?)',('A','192.0.2.1','cerrada','[0,1,0]',100,1794090020,0))
        db.execute('INSERT INTO alarmas VALUES(?,?,?,?,?,?,?,?,?)',('alarm-1','192.0.2.1','Puertas',2,1,1794090001,"Sensor 'uno' $$",0,1794090010))
        db.execute('INSERT INTO logs VALUES(?,?,?,?,?,?)',("log-'$$1",'192.0.2.1',1794090002000,0,'Puertas',"Texto Unicode: conexión \\ ' $$"))
        db.execute('INSERT INTO muestras VALUES(?,?,?,?,?,?,?)',('sample-1','192.0.2.1',1794090003,'Puertas','voltaje',12.3,'V'))
        db.execute('INSERT INTO pantalla VALUES(?,?,?,?,?,?)',(1,'127.0.0.1','{"cor":["Pantalla"]}','{"red":3}',2,1794090004))
        db.execute('INSERT INTO outbox VALUES(?,?,?,?,?,?)',(1,'archived','log','{"msg":"histórico"}',1794090005,None))
        db.execute('INSERT INTO ordenes_web VALUES(?,?,?)',(1,'ORDEN','pendiente'))
    with sqlite3.connect(root/'usuarios.db') as db:
        db.executescript('''CREATE TABLE usuarios(correo TEXT PRIMARY KEY,nombre TEXT,rol TEXT,sal BLOB,clave BLOB,activo INTEGER,creado REAL);
CREATE TABLE accesos(id INTEGER PRIMARY KEY,t REAL,correo TEXT,evento TEXT,detalle TEXT);''')
        db.execute('INSERT INTO usuarios VALUES(?,?,?,?,?,?,?)',('operator@example.invalid','Operador','operador',b'salt',b'incompatible-hash',1,1794090000))
        db.execute('INSERT INTO accesos VALUES(?,?,?,?,?)',(1,1794090001,'operator@example.invalid','login_ok',''))
    manifest={'files':{}}
    for name in ('katana.db','usuarios.db'):
        with sqlite3.connect(root/name) as db:
            tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            counts={t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in tables}
        manifest['files'][name]={'sha256':hashlib.sha256((root/name).read_bytes()).hexdigest(),'rows':counts}
    (root/'manifest.json').write_text(json.dumps(manifest))
