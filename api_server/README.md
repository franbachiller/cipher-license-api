# VPS-Based Streaming License System API Server

Flask-based REST API server for the Cipher CS2 cheat loader license system.

## Features

- **License Key Authentication**: JWT-based authentication with 5-minute token expiration
- **Binary Streaming**: On-demand streaming of encrypted binaries (loader, driver, cheat)
- **Session Management**: Active session tracking with heartbeat mechanism
- **Admin Panel**: License management endpoints (create, revoke, extend, list)
- **Rate Limiting**: Protection against abuse (10 req/min for auth, 60 req/min for API)
- **Database Connection Pooling**: Efficient PostgreSQL connection management

## Project Structure

```
api_server/
├── app.py                 # Flask application entry point
├── config.py              # Configuration management
├── database.py            # Database connection pooling
├── routes/
│   ├── __init__.py       # Blueprint registration
│   ├── auth.py           # /api/auth endpoint
│   ├── download.py       # /api/download/* endpoints
│   ├── heartbeat.py      # /api/heartbeat endpoint
│   └── admin.py          # /admin/* endpoints
├── middleware/
│   ├── jwt_validator.py  # JWT validation decorator
│   └── rate_limiter.py   # Rate limiting configuration
├── utils/
│   ├── encryption.py     # AES encryption/decryption
│   ├── key_generator.py  # License key generation
│   └── logger.py         # Logging configuration
└── requirements.txt
```

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up PostgreSQL database:
```bash
# Create database and user
createdb cipher_license
createuser cipher_user

# Run schema migration
psql cipher_license < ../schema.sql
```

3. Configure environment variables (see `.env.example`):
```bash
cp .env.example .env
# Edit .env with your configuration
```

## Configuration

All configuration is loaded from environment variables. See `config.py` for available options.

### Required Environment Variables

- `DATABASE_URL`: PostgreSQL connection string
- `JWT_SECRET_KEY`: Secret key for JWT signing (generate with `openssl rand -hex 32`)
- `AES_ENCRYPTION_KEY`: 32-byte key for binary encryption (hex-encoded)
- `ADMIN_TOKEN`: Admin authentication token

### Optional Environment Variables

- `SECRET_KEY`: Flask secret key (default: dev key)
- `DEBUG`: Enable debug mode (default: False)
- `DB_POOL_SIZE`: Connection pool size (default: 10)
- `RATE_LIMIT_AUTH`: Auth endpoint rate limit (default: "10 per minute")
- `LOG_LEVEL`: Logging level (default: INFO)

## Running the Server

### Development

```bash
python -m api_server.app
```

### Production (with Gunicorn)

```bash
gunicorn -w 4 -b 0.0.0.0:5000 api_server.app:app
```

### With systemd

```bash
sudo systemctl start cipher-api
sudo systemctl enable cipher-api
```

## API Endpoints

### Authentication
- `POST /api/auth` - Authenticate with license key, receive JWT token

### Binary Downloads
- `GET /api/download/loader` - Download encrypted GDRVLoader.exe
- `GET /api/download/driver` - Download encrypted driver.sys
- `GET /api/download/cheat` - Download encrypted Cipher.exe

### Session Management
- `POST /api/heartbeat` - Update session keep-alive timestamp

### Admin Operations
- `POST /admin/license/create` - Create new license
- `POST /admin/license/revoke` - Revoke license
- `POST /admin/license/extend` - Extend license expiration
- `GET /admin/licenses` - List licenses with filtering
- `GET /admin/sessions` - View active sessions

### Health Check
- `GET /health` - Server health status

## Security

- All endpoints use HTTPS in production
- JWT tokens expire after 5 minutes
- Rate limiting prevents brute force attacks
- IP address validation for JWT tokens
- Admin endpoints require authentication token
- Database credentials stored in environment variables

## Development Status

This is the initial structure implementation (Task 2.1). Individual endpoints are placeholders and will be implemented in subsequent tasks.

## License

Proprietary - Cipher CS2 Project
