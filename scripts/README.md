# Scripts de Utilidad

Scripts para gestión de base de datos, encriptación y migración.

---

## 📋 Scripts Disponibles

### 🗄️ Base de Datos

#### init_database.py
Inicializa la base de datos con el schema completo.

```bash
python scripts/init_database.py
```

**Funcionalidad:**
- Crea tablas (licenses, sessions, auth_logs)
- Crea índices optimizados
- Verifica conexión a Supabase

#### migrate_db.py
Script de migración de base de datos.

```bash
python scripts/migrate_db.py
```

#### migrate_from_hwid.py
Migra licencias desde el sistema antiguo basado en HWID.

```bash
python scripts/migrate_from_hwid.py --input old_licenses.json --output mapping.csv
```

**Parámetros:**
- `--input`: Archivo JSON con licencias antiguas
- `--output`: Archivo CSV con mapeo HWID → License Key

---

### 🔐 Encriptación

#### encrypt_binaries.py
Encripta binarios con AES-256-CBC para deployment.

```bash
# Encriptar un binario
python scripts/encrypt_binaries.py --input loader.exe --output loader.bin

# Encriptar múltiples binarios
python scripts/encrypt_binaries.py --batch
```

**Funcionalidad:**
- Genera IV aleatorio de 16 bytes
- Encripta con AES-256-CBC
- Aplica PKCS7 padding
- Prepend IV al ciphertext

**Archivos esperados:**
- `loader.exe` → `loader.bin`
- `driver.sys` → `driver.bin`
- `cheat.dll` → `cheat.bin`

---

### 📊 Schema SQL

#### schema_supabase.sql
Schema SQL optimizado para Supabase PostgreSQL.

```sql
-- Ejecutar en Supabase SQL Editor
-- O desde CLI:
psql $DATABASE_URL < scripts/schema_supabase.sql
```

**Tablas:**
- `licenses` - Licencias con key, status, expires_at, max_sessions
- `sessions` - Sesiones activas con JWT hash, IP, last_seen
- `auth_logs` - Logs de intentos de autenticación

**Índices:**
- `licenses.key` (UNIQUE)
- `sessions.license_key`
- `sessions.expires_at`
- `sessions(license_key, expires_at)` (composite)
- `auth_logs.timestamp`

#### schema.sql
Schema SQL genérico (alternativo).

---

## 🔧 Uso Común

### Setup Inicial de Base de Datos

```bash
# 1. Inicializar schema
python scripts/init_database.py

# 2. Verificar
python tests/verify_database_performance.py
```

### Preparar Binarios para Deployment

```bash
# 1. Encriptar binarios
python scripts/encrypt_binaries.py --batch

# 2. Subir al VPS
scp -i "C:\ruta\a\clave.pem" *.bin ubuntu@<IP_DEL_VPS>:/opt/cipher-api/api_server/binaries/

# 3. Verificar
ssh -i "C:\ruta\a\clave.pem" ubuntu@<IP_DEL_VPS> "ls -lh /opt/cipher-api/api_server/binaries/"
```

### Migración desde Sistema Antiguo

```bash
# 1. Preparar archivo JSON con licencias antiguas
# Formato: [{"hwid": "ABC123", "expires_at": "2025-12-31"}, ...]

# 2. Ejecutar migración
python scripts/migrate_from_hwid.py --input old_licenses.json --output mapping.csv

# 3. Distribuir mapping.csv a usuarios
# El CSV contiene: HWID,LicenseKey
```

---

## 📝 Notas Importantes

### Encriptación
- La clave AES está en `.env` como `AES_ENCRYPTION_KEY`
- Los binarios encriptados NO deben commitearse a git
- Mantén backups de los binarios originales

### Base de Datos
- Usa Connection Pooler de Supabase para IPv4
- El schema incluye todos los índices necesarios
- Los logs de auth se guardan en `auth_logs` table

### Migración
- El script preserva las fechas de expiración
- Genera license keys únicos de 25 caracteres
- Crea mapping CSV para notificar a usuarios

---

## 🐛 Troubleshooting

### Error de conexión a base de datos

```bash
# Verificar .env
cat api_server/.env | grep DATABASE_URL

# Probar conexión
python -c "from api_server.database import init_db; init_db(); print('OK')"
```

### Error de encriptación

```bash
# Verificar que existe la clave AES
cat api_server/.env | grep AES_ENCRYPTION_KEY

# Verificar que existen los binarios
ls -la *.exe *.sys *.dll
```

### Error de migración

```bash
# Verificar formato del JSON
python -c "import json; print(json.load(open('old_licenses.json')))"

# Verificar permisos de escritura
touch mapping.csv && rm mapping.csv
```

---

## 📞 Soporte

Para problemas con scripts:
1. Verificar que estás en el directorio correcto
2. Verificar que el entorno virtual está activado
3. Verificar que las dependencias están instaladas: `pip install -r api_server/requirements.txt`
4. Consultar logs de error completos

---

**Última actualización**: 26 de Febrero, 2026
