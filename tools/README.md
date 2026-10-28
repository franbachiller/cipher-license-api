# Herramientas de Administración

Herramientas CLI y web para gestión de licencias y sesiones.

---

## 🛠️ Herramientas Disponibles

### 1. Admin CLI (admin.py)

Herramienta de línea de comandos para gestión de licencias.

#### Comandos Disponibles

##### Crear Licencia
```bash
python tools/admin.py create --expires "2027-12-31" --sessions 1 --note "Cliente X"
```

**Parámetros:**
- `--expires`: Fecha de expiración (YYYY-MM-DD)
- `--sessions`: Número máximo de sesiones simultáneas
- `--note`: Nota descriptiva (opcional)

**Output:**
```
✅ License created successfully!
   License Key:  ABC123XYZ456DEF789GHI012J
   Status:       active
   Expires:      2027-12-31 00:00:00
   Max Sessions: 1
   Note:         Cliente X
```

##### Listar Licencias
```bash
# Todas las licencias
python tools/admin.py list

# Solo activas
python tools/admin.py list --status active

# Con límite
python tools/admin.py list --limit 10
```

**Parámetros:**
- `--status`: Filtrar por estado (active, revoked, expired)
- `--limit`: Número máximo de resultados

##### Revocar Licencia
```bash
python tools/admin.py revoke --key "ABC123XYZ456DEF789GHI012J"
```

**Efecto:**
- Cambia status a "revoked"
- Termina todas las sesiones activas
- Bloquea nuevas autenticaciones

##### Extender Licencia
```bash
python tools/admin.py extend --key "ABC123XYZ456DEF789GHI012J" --expires "2028-12-31"
```

**Parámetros:**
- `--key`: License key a extender
- `--expires`: Nueva fecha de expiración

##### Ver Sesiones
```bash
# Todas las sesiones activas
python tools/admin.py sessions

# Sesiones de una licencia específica
python tools/admin.py sessions --key "ABC123XYZ456DEF789GHI012J"
```

---

### 2. Web Admin Panel (web_admin.py)

Panel web para gestión visual de licencias y sesiones.

#### Iniciar Panel

```bash
# Método 1: Python directo
python tools/web_admin.py

# Método 2: Launcher Windows
tools\START_WEB_ADMIN.bat

# Método 3: Launcher alternativo
tools\ADMIN_PANEL.bat
```

**Acceso:** http://localhost:8080

#### Funcionalidades

##### Dashboard
- Total de licencias (activas, revocadas, expiradas)
- Sesiones activas en tiempo real
- Gráficos de uso

##### Gestión de Licencias
- Crear nueva licencia
- Ver lista de licencias con filtros
- Revocar licencias
- Extender expiración
- Ver detalles completos

##### Gestión de Sesiones
- Ver sesiones activas
- Filtrar por license key
- Ver IP address y last_seen
- Terminar sesiones manualmente

##### Autenticación
- Login con ADMIN_TOKEN
- Sesión persistente
- Logout seguro

---

### 3. Otros Scripts

#### panel.py
Panel alternativo de administración.

```bash
python tools/panel.py
```

#### server.py
Servidor de desarrollo alternativo.

```bash
python tools/server.py
```

---

## 🚀 Uso Rápido

### Workflow Típico de Administrador

```bash
# 1. Crear licencia para nuevo cliente
python tools/admin.py create --expires "2027-12-31" --sessions 1 --note "Cliente Premium"

# 2. Copiar license key y enviar al cliente
# Output: ABC123XYZ456DEF789GHI012J

# 3. Verificar sesiones activas
python tools/admin.py sessions

# 4. Si necesitas revocar
python tools/admin.py revoke --key "ABC123XYZ456DEF789GHI012J"
```

### Uso del Web Panel

```bash
# 1. Iniciar panel
python tools/web_admin.py

# 2. Abrir navegador en http://localhost:8080

# 3. Login con ADMIN_TOKEN (desde .env)

# 4. Gestionar licencias visualmente
```

---

## 🔐 Autenticación

### CLI Tool (admin.py)

Requiere acceso directo a la base de datos. Configuración en `api_server/.env`:

```env
DATABASE_URL=postgresql://...
```

### Web Panel (web_admin.py)

Requiere ADMIN_TOKEN para login. Token en `api_server/.env`:

```env
ADMIN_TOKEN=<ADMIN_TOKEN>
```

---

## 📊 Ejemplos de Uso

### Crear múltiples licencias

```bash
# Licencia de 1 mes
python tools/admin.py create --expires "2026-03-26" --sessions 1 --note "Trial 1 mes"

# Licencia de 1 año
python tools/admin.py create --expires "2027-02-26" --sessions 1 --note "Anual"

# Licencia con múltiples sesiones
python tools/admin.py create --expires "2027-02-26" --sessions 3 --note "Team License"
```

### Auditoría de licencias

```bash
# Ver todas las licencias activas
python tools/admin.py list --status active

# Ver licencias expiradas
python tools/admin.py list --status expired

# Ver licencias revocadas
python tools/admin.py list --status revoked
```

### Monitoreo de sesiones

```bash
# Ver todas las sesiones activas
python tools/admin.py sessions

# Ver sesiones de un cliente específico
python tools/admin.py sessions --key "ABC123XYZ456DEF789GHI012J"
```

---

## 🐛 Troubleshooting

### Error: "Database connection failed"

```bash
# Verificar .env
cat api_server/.env | grep DATABASE_URL

# Probar conexión
python -c "from api_server.database import init_db; init_db(); print('OK')"
```

### Error: "Invalid ADMIN_TOKEN"

```bash
# Verificar token en .env
cat api_server/.env | grep ADMIN_TOKEN

# Usar el token correcto en el login del web panel
```

### Web panel no inicia

```bash
# Verificar puerto 8080 disponible
netstat -an | findstr :8080

# Usar puerto alternativo
python tools/web_admin.py --port 8081
```

---

## 📝 Notas Importantes

### CLI Tool
- Requiere acceso directo a la base de datos
- Ideal para uso en VPS o local
- No requiere que la API esté corriendo

### Web Panel
- Requiere que la API esté corriendo (usa endpoints admin)
- Ideal para gestión visual
- Accesible desde navegador

### Seguridad
- ADMIN_TOKEN debe mantenerse secreto
- No compartir credenciales de base de datos
- Usar HTTPS en producción

---

## 📞 Uso en VPS

### Conectar y usar CLI

```bash
# 1. Conectar al VPS
ssh -i "C:\ruta\a\clave.pem" ubuntu@<IP_DEL_VPS>

# 2. Activar entorno virtual
cd /opt/cipher-api
source venv/bin/activate

# 3. Usar admin CLI
python tools/admin.py create --expires "2027-12-31" --sessions 1 --note "Cliente VIP"
```

### Web Panel en VPS

```bash
# Iniciar panel (solo accesible desde localhost)
python tools/web_admin.py

# Para acceso remoto, usar SSH tunnel:
# ssh -i "key.pem" -L 8080:localhost:8080 ubuntu@<IP_DEL_VPS>
```

---

**Última actualización**: 26 de Febrero, 2026
