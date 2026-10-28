# Deployment Scripts

Scripts y configuraciones para desplegar el sistema en VPS.

---

## 📦 Archivos de Deployment

### Scripts de Deployment
- **deploy_simple.ps1** - Script PowerShell para deployment desde Windows
- **deploy_to_vps.sh** - Script bash para ejecutar en el VPS
- **upload_and_deploy.ps1** - Upload de código y deployment automático
- **setup_vps.sh** - Setup inicial del VPS

### Configuraciones de Sistema
- **cipher-api.service** - Systemd service file (auto-start con 4 workers)
- **nginx_cipher_api.conf** - Configuración de Nginx (reverse proxy)
- **nginx-cipher-api.conf** - Configuración alternativa de Nginx
- **cipher_admin.conf** - Configuración del panel de admin

---

## 🚀 Uso Rápido

### Deployment Completo desde Windows

```powershell
cd CipherAPI/deployment
.\deploy_simple.ps1
```

Este script:
1. Sube el código al VPS
2. Instala dependencias
3. Configura servicios
4. Reinicia la API

### Deployment Manual

```bash
# 1. Conectar al VPS
ssh -i "C:\ruta\a\clave.pem" ubuntu@<IP_DEL_VPS>

# 2. Ejecutar script de deployment
cd /opt/cipher-api
bash deployment/deploy_to_vps.sh
```

---

## 📋 Configuración de Servicios

### Systemd Service (cipher-api.service)

Ubicación en VPS: `/etc/systemd/system/cipher-api.service`

```bash
# Habilitar auto-start
sudo systemctl enable cipher-api

# Iniciar servicio
sudo systemctl start cipher-api

# Ver estado
sudo systemctl status cipher-api

# Ver logs
sudo journalctl -u cipher-api -f
```

### Nginx (nginx_cipher_api.conf)

Ubicación en VPS: `/etc/nginx/sites-available/cipher-api`

```bash
# Habilitar sitio
sudo ln -s /etc/nginx/sites-available/cipher-api /etc/nginx/sites-enabled/

# Verificar configuración
sudo nginx -t

# Recargar Nginx
sudo systemctl reload nginx
```

---

## 🔧 Actualizar Código en Producción

### Método 1: Script Automático (Recomendado)

```powershell
cd CipherAPI/deployment
.\deploy_simple.ps1
```

### Método 2: Manual

```powershell
# Subir código
$PEM_KEY = "C:\ruta\a\clave.pem"
scp -i $PEM_KEY -r ../api_server ubuntu@<IP_DEL_VPS>:/opt/cipher-api/

# Reiniciar servicio
ssh -i $PEM_KEY ubuntu@<IP_DEL_VPS> "sudo systemctl restart cipher-api"
```

---

## 🐛 Troubleshooting

### Servicio no inicia

```bash
# Ver logs detallados
sudo journalctl -u cipher-api -n 100 --no-pager

# Verificar permisos
ls -la /opt/cipher-api/

# Verificar .env
cat /opt/cipher-api/api_server/.env
```

### Nginx 502 Bad Gateway

```bash
# Verificar que gunicorn está corriendo
sudo systemctl status cipher-api

# Verificar puerto
sudo netstat -tlnp | grep 5000

# Ver logs de Nginx
tail -f /var/log/nginx/cipher-api-error.log
```

### Puerto ocupado

```bash
# Ver qué proceso usa el puerto
sudo lsof -i :5000

# Matar proceso
sudo fuser -k 5000/tcp

# Reiniciar servicio
sudo systemctl restart cipher-api
```

---

## 📞 Información del VPS

**VPS Details:**
- IP: <IP_DEL_VPS>
- Instance: CipherAuth (t3.micro)
- Region: us-east-2
- OS: Ubuntu 24.04 LTS

**SSH Access:**
```bash
ssh -i "C:\ruta\a\clave.pem" ubuntu@<IP_DEL_VPS>
```

**Rutas en VPS:**
- Application: `/opt/cipher-api/`
- Logs: `/opt/cipher-api/api_server.log`
- Service: `/etc/systemd/system/cipher-api.service`
- Nginx: `/etc/nginx/sites-available/cipher-api`

---

## ✅ Verificación Post-Deployment

```bash
# Health check
curl http://<IP_DEL_VPS>/health

# Verificar servicios
sudo systemctl status cipher-api
sudo systemctl status nginx

# Ver logs
tail -f /opt/cipher-api/api_server.log
```

---

**Última actualización**: 26 de Febrero, 2026
