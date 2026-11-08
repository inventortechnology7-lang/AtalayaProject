#!/usr/bin/env python3
"""Crea un usuario del gestor de Katana (la clave se pide oculta y se guarda con scrypt en usuarios.db)."""
import getpass, sys
import auth

correo = input("Correo: ").strip()
nombre = input("Nombre: ").strip()
rol = (input("Rol [admin/tecnico/operador] (admin): ").strip() or "admin")
clave = getpass.getpass("Clave (mín. 8): ")
if clave != getpass.getpass("Repite la clave: "):
    sys.exit("Las claves no coinciden.")
ok, msg = auth.crear(correo, nombre, rol, clave, por="crear_usuario.py")
print(msg); sys.exit(0 if ok else 1)
