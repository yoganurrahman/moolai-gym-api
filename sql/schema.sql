-- Moolai Gym Database Schema
-- Run this SQL to create the initial database structure

CREATE DATABASE IF NOT EXISTS moolai_gym;
USE moolai_gym;

-- =============================================
-- ROLES & PERMISSIONS
-- =============================================

CREATE TABLE IF NOT EXISTS permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255),
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS role_permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role_id INT NOT NULL,
    permission_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_role_permission (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================================
-- USERS
-- =============================================

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    pin VARCHAR(255),
    pin_version INT DEFAULT 1,
    has_pin TINYINT(1) DEFAULT 0,
    failed_pin_attempts INT DEFAULT 0,
    pin_locked_until DATETIME,
    phone VARCHAR(20),
    role_id INT,
    is_active TINYINT(1) DEFAULT 1,
    token_version INT DEFAULT 1,
    failed_login_attempts INT DEFAULT 0,
    locked_until DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Index for faster lookups
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role_id ON users(role_id);

-- =============================================
-- SEED DATA
-- =============================================

-- Insert default permissions
INSERT INTO permissions (name, description) VALUES
-- User permissions
('user.view', 'Lihat daftar user'),
('user.create', 'Buat user baru'),
('user.update', 'Update data user'),
('user.delete', 'Hapus user'),
-- Role permissions
('role.view', 'Lihat daftar role'),
('role.create', 'Buat role baru'),
('role.update', 'Update role'),
('role.delete', 'Hapus role'),
-- Permission permissions
('permission.view', 'Lihat daftar permission'),
('permission.create', 'Buat permission baru'),
('permission.update', 'Update permission'),
('permission.delete', 'Hapus permission'),
-- Member permissions (untuk fitur gym)
('member.view', 'Lihat daftar member'),
('member.create', 'Daftarkan member baru'),
('member.update', 'Update data member'),
('member.delete', 'Hapus member'),
-- Membership permissions
('membership.view', 'Lihat paket membership'),
('membership.create', 'Buat paket membership'),
('membership.update', 'Update paket membership'),
('membership.delete', 'Hapus paket membership'),
-- Trainer permissions
('trainer.view', 'Lihat daftar trainer'),
('trainer.create', 'Tambah trainer baru'),
('trainer.update', 'Update data trainer'),
('trainer.delete', 'Hapus trainer'),
-- Class permissions
('class.view', 'Lihat jadwal kelas'),
('class.create', 'Buat kelas baru'),
('class.update', 'Update jadwal kelas'),
('class.delete', 'Hapus kelas'),
-- Transaction permissions
('transaction.view', 'Lihat transaksi'),
('transaction.create', 'Buat transaksi baru'),
('transaction.update', 'Update transaksi'),
('transaction.delete', 'Hapus transaksi')
ON DUPLICATE KEY UPDATE description = VALUES(description);

-- Insert default roles
INSERT INTO roles (id, name, description, is_active) VALUES
(1, 'superadmin', 'Super Administrator dengan akses penuh', 1),
(2, 'admin', 'Administrator gym', 1),
(3, 'member', 'Member gym', 1),
(4, 'trainer', 'Personal trainer', 1)
ON DUPLICATE KEY UPDATE description = VALUES(description);

-- Assign all permissions to admin role (superadmin has bypass)
INSERT INTO role_permissions (role_id, permission_id)
SELECT 2, id FROM permissions
ON DUPLICATE KEY UPDATE role_id = role_id;

-- Assign member-specific permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT 3, id FROM permissions WHERE name IN ('class.view', 'membership.view', 'trainer.view')
ON DUPLICATE KEY UPDATE role_id = role_id;

-- Assign trainer permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT 4, id FROM permissions WHERE name IN ('class.view', 'class.update', 'member.view', 'membership.view')
ON DUPLICATE KEY UPDATE role_id = role_id;

-- Insert default users for each role (password: Admin@123, PIN: 123456)
-- Password hash for "Admin@123" using bcrypt
-- PIN hash for "123456" using bcrypt
INSERT INTO users (id, name, email, password, pin, has_pin, pin_version, phone, role_id, is_active, token_version) VALUES
(1, 'Super Admin', 'superadmin@moolaigym.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, 1, '081234567890', 1, 1, 1),
(2, 'Admin Gym', 'admin@moolaigym.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, 1, '081234567891', 2, 1, 1),
(3, 'Member User', 'member@moolaigym.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, 1, '081234567892', 3, 1, 1),
(4, 'Trainer User', 'trainer@moolaigym.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, 1, '081234567893', 4, 1, 1)
ON DUPLICATE KEY UPDATE password = VALUES(password), pin = VALUES(pin), has_pin = VALUES(has_pin);

-- =============================================
-- ADDITIONAL TABLES (for future features)
-- =============================================

-- Members table (gym members with extended info)
CREATE TABLE IF NOT EXISTS members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    membership_id INT,
    join_date DATE,
    expire_date DATE,
    emergency_contact VARCHAR(100),
    emergency_phone VARCHAR(20),
    health_notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Memberships table (membership packages)
CREATE TABLE IF NOT EXISTS memberships (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(12,2) NOT NULL,
    duration_days INT NOT NULL,
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Trainers table
CREATE TABLE IF NOT EXISTS trainers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    specialization VARCHAR(255),
    certification TEXT,
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Gym classes table
CREATE TABLE IF NOT EXISTS gym_classes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    trainer_id INT,
    max_participants INT DEFAULT 20,
    schedule_day VARCHAR(20),
    schedule_time TIME,
    duration_minutes INT DEFAULT 60,
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (trainer_id) REFERENCES trainers(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Audit logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(100),
    record_id INT,
    action VARCHAR(20),
    user_id INT,
    old_data JSON,
    new_data JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- OTP Verifications table
CREATE TABLE IF NOT EXISTS otp_verifications (
    otp_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    otp_type ENUM('password_reset', 'email_verification', 'phone_verification', 'two_factor_auth', 'transaction_verification', 'login_verification', 'registration_verification') NOT NULL,
    contact_type ENUM('email', 'phone') NOT NULL,
    contact_value VARCHAR(255) NOT NULL,
    otp_code VARCHAR(10) NOT NULL,
    is_used TINYINT(1) DEFAULT 0,
    is_expired TINYINT(1) DEFAULT 0,
    expires_at DATETIME NOT NULL,
    used_at DATETIME,
    metadata JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Index for faster OTP lookups
CREATE INDEX idx_otp_contact_value ON otp_verifications(contact_value);
CREATE INDEX idx_otp_type ON otp_verifications(otp_type);
CREATE INDEX idx_otp_expires_at ON otp_verifications(expires_at);
