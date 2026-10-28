-- VPS-Based Streaming License System Database Schema
-- PostgreSQL 14+ (Supabase Compatible)
-- This schema implements Requirements 8.1, 8.2, 8.3, 8.4, 8.5

-- Drop tables if they exist (for clean migration)
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS licenses CASCADE;
DROP TABLE IF EXISTS auth_logs CASCADE;

-- Create licenses table
CREATE TABLE licenses (
    id SERIAL PRIMARY KEY,
    key VARCHAR(25) UNIQUE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    expires_at TIMESTAMP NOT NULL,
    max_sessions INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note TEXT,
    hwid TEXT,
    
    -- Constraints
    CONSTRAINT chk_status CHECK (status IN ('active', 'expired', 'revoked')),
    CONSTRAINT chk_max_sessions CHECK (max_sessions > 0)
);

-- Create sessions table
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR(25) NOT NULL,
    jwt_token_hash VARCHAR(64) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    last_seen TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint with CASCADE delete
    CONSTRAINT fk_license FOREIGN KEY (license_key) 
        REFERENCES licenses(key) ON DELETE CASCADE
);

-- Create indexes for licenses table
CREATE INDEX idx_licenses_key ON licenses(key);
CREATE INDEX idx_licenses_status ON licenses(status);
CREATE INDEX idx_licenses_expires_at ON licenses(expires_at);

-- Create indexes for sessions table
CREATE INDEX idx_sessions_license_key ON sessions(license_key);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX idx_sessions_last_seen ON sessions(last_seen);
CREATE INDEX idx_sessions_composite ON sessions(license_key, expires_at);

-- Optional but recommended: auth_logs table for security auditing
CREATE TABLE auth_logs (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR(25),
    ip_address VARCHAR(45) NOT NULL,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_auth_logs_timestamp ON auth_logs(timestamp);
CREATE INDEX idx_auth_logs_license_key ON auth_logs(license_key);

-- Verification query (run this separately to verify)
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
