/*
 Navicat Premium Dump SQL

 Source Server         : MACBOOK
 Source Server Type    : MySQL
 Source Server Version : 100428 (10.4.28-MariaDB)
 Source Host           : localhost:3306
 Source Schema         : moolai_gym

 Target Server Type    : MySQL
 Target Server Version : 100428 (10.4.28-MariaDB)
 File Encoding         : 65001

 Date: 28/01/2026 12:00:00
*/

/*
================================================================================
                        MOOLAI GYM DATABASE SCHEMA
================================================================================

Database ini dirancang untuk sistem manajemen gym MULTI-CABANG yang mencakup:
- Branch Management (Multi-Cabang)
- Authentication & User Management
- Membership Management (berlaku di semua cabang)
- Check-in System (per cabang)
- Personal Training (PT) (per cabang)
- Class Management (per cabang)
- Products & POS (stock per cabang)
- Transactions (per cabang)
- Subscriptions (Recurring Billing)
- Promos & Vouchers
- Notifications

MULTI-BRANCH RULES:
- Membership berlaku di SEMUA cabang
- Trainer bisa pindah-pindah antar cabang
- Penawaran (paket, harga, class type) SAMA di setiap cabang
- Setiap aktivitas operasional dicatat di cabang mana

================================================================================
                            ENTITY RELATIONSHIP DIAGRAM
================================================================================

┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│   roles     │────<│ role_permissions │>────│ permissions │
└─────────────┘     └─────────────────┘     └─────────────┘
       │
       │ 1:N
       ▼
┌─────────────┐     ┌──────────────────┐     ┌──────────────────────┐
│   users     │────<│ member_memberships│>────│ membership_packages  │
└─────────────┘     └──────────────────┘     └──────────────────────┘
       │
       ├────────────────────────────────────────────────┐
       │                                                │
       │ 1:N                                            │ 1:N
       ▼                                                ▼
┌─────────────────┐                           ┌─────────────────┐
│ member_checkins │                           │    trainers     │
└─────────────────┘                           └─────────────────┘
                                                       │
                                                       │ 1:N
                                                       ▼
┌─────────────────┐     ┌─────────────────────┐     ┌───────────────┐
│  pt_bookings    │────<│ member_pt_sessions   │────<│  pt_packages  │
└─────────────────┘     └─────────────────────┘     └───────────────┘

┌─────────────────┐     ┌─────────────────────┐     ┌───────────────┐
│ class_bookings  │────<│  class_schedules     │────<│  class_types  │
└─────────────────┘     └─────────────────────┘     └───────────────┘

┌─────────────────┐     ┌─────────────────────┐     ┌───────────────┐
│   products      │────<│ product_categories   │     │  transactions │
└─────────────────┘     └─────────────────────┘     └───────────────┘
                                                           │
                                                           │ 1:N
                                                           ▼
                                                    ┌──────────────────┐
                                                    │ transaction_items│
                                                    └──────────────────┘

================================================================================
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- BRANCHES (MULTI-CABANG)
-- ============================================================================

-- ----------------------------
-- Table: branches
-- ----------------------------
-- FUNGSI: Menyimpan daftar cabang/lokasi gym
-- RELASI:
--   - ONE-TO-MANY ke semua tabel operasional (checkins, schedules, bookings, transactions)
--   - ONE-TO-MANY ke trainer_branches (trainer assignment)
--   - ONE-TO-MANY ke branch_product_stock (stock per cabang)
-- FITUR:
--   - code: Kode unik cabang untuk ID di transaction code (JKT, TNG, BDG)
--   - opening_time/closing_time: Jam operasional per cabang
--   - sort_order: Urutan tampilan di UI
-- ----------------------------
DROP TABLE IF EXISTS `branches`;
CREATE TABLE `branches` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `code` varchar(20) NOT NULL COMMENT 'Kode unik cabang (JKT, TNG, BDG)',
  `name` varchar(100) NOT NULL COMMENT 'Nama cabang',
  `address` text DEFAULT NULL,
  `city` varchar(100) DEFAULT NULL,
  `province` varchar(100) DEFAULT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `email` varchar(100) DEFAULT NULL,
  `timezone` varchar(50) DEFAULT 'Asia/Jakarta',
  `opening_time` time DEFAULT '06:00:00',
  `closing_time` time DEFAULT '22:00:00',
  `is_active` tinyint(1) DEFAULT 1,
  `sort_order` int(11) DEFAULT 0,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of branches
-- ----------------------------
INSERT INTO `branches` (`id`, `code`, `name`, `address`, `city`, `province`, `phone`, `email`, `opening_time`, `closing_time`, `sort_order`) VALUES
(1, 'JKT', 'Moolai Gym Jakarta', 'Jl. Sudirman No. 100, Jakarta Pusat', 'Jakarta', 'DKI Jakarta', '021-1234567', 'jakarta@moolaigym.com', '06:00:00', '22:00:00', 1),
(2, 'TNG', 'Moolai Gym Tangerang', 'Jl. BSD Raya No. 50, Tangerang Selatan', 'Tangerang', 'Banten', '021-7654321', 'tangerang@moolaigym.com', '06:00:00', '22:00:00', 2),
(3, 'BDG', 'Moolai Gym Bandung', 'Jl. Dago No. 75, Bandung', 'Bandung', 'Jawa Barat', '022-1234567', 'bandung@moolaigym.com', '06:00:00', '21:00:00', 3);

-- ============================================================================
-- AUTH & USERS
-- ============================================================================

-- ----------------------------
-- Table: roles
-- ----------------------------
-- FUNGSI: Menyimpan daftar role/jabatan dalam sistem
-- RELASI:
--   - ONE-TO-MANY ke users (1 role punya banyak user)
--   - MANY-TO-MANY ke permissions via role_permissions
-- ----------------------------
DROP TABLE IF EXISTS `roles`;
CREATE TABLE `roles` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of roles
-- ----------------------------
INSERT INTO `roles` (`id`, `name`, `description`, `is_active`) VALUES
(1, 'superadmin', 'Super Administrator dengan akses penuh', 1),
(2, 'admin', 'Administrator gym', 1),
(3, 'member', 'Member gym', 1),
(4, 'trainer', 'Personal trainer', 1),
(5, 'staff', 'Staff kasir/front desk', 1);

-- ----------------------------
-- Table: permissions
-- ----------------------------
-- FUNGSI: Menyimpan daftar hak akses/permission dalam sistem
-- RELASI:
--   - MANY-TO-MANY ke roles via role_permissions
-- PERMISSION NAMING CONVENTION: {module}.{action}
--   - module: user, role, permission, member, package, trainer, class, transaction, product, checkin, report, promo, settings
--   - action: view, create, update, delete
-- ----------------------------
DROP TABLE IF EXISTS `permissions`;
CREATE TABLE `permissions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of permissions
-- ----------------------------
INSERT INTO `permissions` (`id`, `name`, `description`) VALUES
-- User Management
(1, 'user.view', 'Lihat daftar user'),
(2, 'user.create', 'Buat user baru'),
(3, 'user.update', 'Update data user'),
(4, 'user.delete', 'Hapus user'),
-- Role Management
(5, 'role.view', 'Lihat daftar role'),
(6, 'role.create', 'Buat role baru'),
(7, 'role.update', 'Update role'),
(8, 'role.delete', 'Hapus role'),
-- Permission Management
(9, 'permission.view', 'Lihat daftar permission'),
(10, 'permission.create', 'Buat permission baru'),
(11, 'permission.update', 'Update permission'),
(12, 'permission.delete', 'Hapus permission'),
-- Member Management
(13, 'member.view', 'Lihat daftar member'),
(14, 'member.create', 'Daftarkan member baru'),
(15, 'member.update', 'Update data member'),
(16, 'member.delete', 'Hapus member'),
-- Membership Package Management
(17, 'package.view', 'Lihat paket membership'),
(18, 'package.create', 'Buat paket membership'),
(19, 'package.update', 'Update paket membership'),
(20, 'package.delete', 'Hapus paket membership'),
-- Trainer Management
(21, 'trainer.view', 'Lihat daftar trainer'),
(22, 'trainer.create', 'Tambah trainer baru'),
(23, 'trainer.update', 'Update data trainer'),
(24, 'trainer.delete', 'Hapus trainer'),
-- Class Management
(25, 'class.view', 'Lihat jadwal kelas'),
(26, 'class.create', 'Buat kelas baru'),
(27, 'class.update', 'Update jadwal kelas'),
(28, 'class.delete', 'Hapus kelas'),
-- Transaction Management
(29, 'transaction.view', 'Lihat transaksi'),
(30, 'transaction.create', 'Buat transaksi baru'),
(31, 'transaction.update', 'Update transaksi'),
(32, 'transaction.delete', 'Hapus transaksi'),
-- Product Management
(33, 'product.view', 'Lihat daftar produk'),
(34, 'product.create', 'Tambah produk baru'),
(35, 'product.update', 'Update produk'),
(36, 'product.delete', 'Hapus produk'),
-- Check-in Management
(37, 'checkin.view', 'Lihat history check-in'),
(38, 'checkin.create', 'Manual check-in member'),
-- Report
(39, 'report.view', 'Lihat laporan'),
-- Promo Management
(40, 'promo.view', 'Lihat daftar promo'),
(41, 'promo.create', 'Buat promo baru'),
(42, 'promo.update', 'Update promo'),
(43, 'promo.delete', 'Hapus promo'),
-- Settings
(44, 'settings.view', 'Lihat pengaturan'),
(45, 'settings.update', 'Update pengaturan'),
-- Branch Management
(46, 'branch.view', 'Lihat daftar cabang'),
(47, 'branch.create', 'Buat cabang baru'),
(48, 'branch.update', 'Update cabang'),
(49, 'branch.delete', 'Hapus cabang');

-- ----------------------------
-- Table: role_permissions
-- ----------------------------
-- FUNGSI: Tabel pivot/junction untuk relasi many-to-many antara roles dan permissions
-- RELASI:
--   - MANY-TO-ONE ke roles (role_id)
--   - MANY-TO-ONE ke permissions (permission_id)
-- ----------------------------
DROP TABLE IF EXISTS `role_permissions`;
CREATE TABLE `role_permissions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `role_id` int(11) NOT NULL,
  `permission_id` int(11) NOT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_role_permission` (`role_id`,`permission_id`),
  KEY `permission_id` (`permission_id`),
  CONSTRAINT `role_permissions_ibfk_1` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `role_permissions_ibfk_2` FOREIGN KEY (`permission_id`) REFERENCES `permissions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of role_permissions
-- ----------------------------
-- SUPERADMIN (role_id=1): Semua permission (1-45)
INSERT INTO `role_permissions` (`role_id`, `permission_id`) VALUES
-- Superadmin - All permissions
(1, 1), (1, 2), (1, 3), (1, 4),     -- user.*
(1, 5), (1, 6), (1, 7), (1, 8),     -- role.*
(1, 9), (1, 10), (1, 11), (1, 12),  -- permission.*
(1, 13), (1, 14), (1, 15), (1, 16), -- member.*
(1, 17), (1, 18), (1, 19), (1, 20), -- package.*
(1, 21), (1, 22), (1, 23), (1, 24), -- trainer.*
(1, 25), (1, 26), (1, 27), (1, 28), -- class.*
(1, 29), (1, 30), (1, 31), (1, 32), -- transaction.*
(1, 33), (1, 34), (1, 35), (1, 36), -- product.*
(1, 37), (1, 38),                   -- checkin.*
(1, 39),                            -- report.view
(1, 40), (1, 41), (1, 42), (1, 43), -- promo.*
(1, 44), (1, 45),                   -- settings.*
(1, 46), (1, 47), (1, 48), (1, 49), -- branch.*

-- ADMIN (role_id=2): Semua kecuali role & permission management
(2, 1), (2, 2), (2, 3), (2, 4),     -- user.*
(2, 5),                             -- role.view only
(2, 9),                             -- permission.view only
(2, 13), (2, 14), (2, 15), (2, 16), -- member.*
(2, 17), (2, 18), (2, 19), (2, 20), -- package.*
(2, 21), (2, 22), (2, 23), (2, 24), -- trainer.*
(2, 25), (2, 26), (2, 27), (2, 28), -- class.*
(2, 29), (2, 30), (2, 31), (2, 32), -- transaction.*
(2, 33), (2, 34), (2, 35), (2, 36), -- product.*
(2, 37), (2, 38),                   -- checkin.*
(2, 39),                            -- report.view
(2, 40), (2, 41), (2, 42), (2, 43), -- promo.*
(2, 44), (2, 45),                   -- settings.*
(2, 46), (2, 48),                   -- branch.view, branch.update

-- MEMBER (role_id=3): View only untuk beberapa modul
(3, 17),                            -- package.view (lihat paket membership)
(3, 25),                            -- class.view (lihat jadwal kelas)
(3, 46),                            -- branch.view (lihat daftar cabang)

-- TRAINER (role_id=4): Akses untuk trainer
(4, 13),                            -- member.view (lihat member untuk PT)
(4, 21), (4, 23),                   -- trainer.view, trainer.update (update profil & complete PT)
(4, 25), (4, 27),                   -- class.view, class.update (untuk kelas yang diajar)
(4, 37),                            -- checkin.view (lihat siapa yang check-in)
(4, 46),                            -- branch.view (lihat daftar cabang)

-- STAFF (role_id=5): Akses untuk kasir/front desk
(5, 1),                             -- user.view
(5, 13), (5, 14),                   -- member.view, member.create
(5, 17),                            -- package.view
(5, 21),                            -- trainer.view
(5, 25),                            -- class.view
(5, 29), (5, 30),                   -- transaction.view, transaction.create
(5, 33),                            -- product.view
(5, 37), (5, 38),                   -- checkin.*
(5, 40),                            -- promo.view
(5, 46);                            -- branch.view

-- ----------------------------
-- Table: users
-- ----------------------------
-- FUNGSI: Menyimpan data semua pengguna sistem (superadmin, admin, staff, trainer, member)
-- RELASI:
--   - MANY-TO-ONE ke roles (role_id) - setiap user punya 1 role
--   - ONE-TO-MANY ke member_memberships - member bisa punya banyak membership
--   - ONE-TO-MANY ke member_checkins - member bisa punya banyak record check-in
--   - ONE-TO-MANY ke trainers - user dengan role trainer punya data trainer
--   - ONE-TO-MANY ke transactions - user bisa punya banyak transaksi
--   - ONE-TO-MANY ke notifications - user bisa punya banyak notifikasi
--   - ONE-TO-MANY ke otp_verifications - untuk verifikasi OTP
-- FITUR:
--   - PIN untuk verifikasi transaksi sensitif (6 digit)
--   - Token version untuk invalidate semua session saat logout dari semua device
--   - Failed login attempts & locking untuk keamanan
-- ----------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password` varchar(255) NOT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `avatar` varchar(255) DEFAULT NULL,
  `date_of_birth` date DEFAULT NULL,
  `gender` enum('male','female') DEFAULT NULL,
  `address` text DEFAULT NULL,
  `role_id` int(11) DEFAULT NULL,
  `default_branch_id` int(11) DEFAULT NULL COMMENT 'Default cabang user (staff/admin untuk CMS, member untuk preferensi)',
  `is_active` tinyint(1) DEFAULT 1,
  -- PIN untuk verifikasi transaksi
  `pin` varchar(255) DEFAULT NULL,
  `has_pin` tinyint(1) DEFAULT 0,
  `pin_version` int(11) DEFAULT 1,
  `failed_pin_attempts` int(11) DEFAULT 0,
  `pin_locked_until` datetime DEFAULT NULL,
  -- Token version untuk invalidate sessions
  `token_version` int(11) DEFAULT 1,
  `failed_login_attempts` int(11) DEFAULT 0,
  `locked_until` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`),
  KEY `idx_users_email` (`email`),
  KEY `idx_users_role_id` (`role_id`),
  KEY `idx_users_branch` (`default_branch_id`),
  CONSTRAINT `users_ibfk_1` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE SET NULL,
  CONSTRAINT `users_branch_fk` FOREIGN KEY (`default_branch_id`) REFERENCES `branches` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of users (default users, password: admin123, pin: 123456)
-- ----------------------------
INSERT INTO `users` (`id`, `name`, `email`, `password`, `pin`, `has_pin`, `phone`, `role_id`, `default_branch_id`, `is_active`) VALUES
(1, 'Super Admin', 'superadmin@moolaigym.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567890', 1, 1, 1),
(2, 'Admin Gym', 'admin@moolaigym.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567891', 2, 1, 1),
(3, 'Staff Kasir', 'staff@moolaigym.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567892', 5, 1, 1),
(4, 'Member User', 'member@moolaigym.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567893', 3, NULL, 1),
(5, 'Coach Eko', 'trainer@moolaigym.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567894', 4, NULL, 1);

-- ----------------------------
-- Table: otp_verifications
-- ----------------------------
-- FUNGSI: Menyimpan kode OTP untuk berbagai keperluan verifikasi
-- RELASI:
--   - MANY-TO-ONE ke users (user_id) - OTP untuk user tertentu (bisa NULL untuk registration)
-- OTP TYPES:
--   - registration: Verifikasi email saat registrasi
--   - password_reset: Verifikasi untuk reset password
--   - email_verification: Verifikasi email baru
--   - phone_verification: Verifikasi nomor HP baru
--   - transaction: Verifikasi untuk transaksi besar
-- ----------------------------
DROP TABLE IF EXISTS `otp_verifications`;
CREATE TABLE `otp_verifications` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `otp_type` enum('registration','password_reset','email_verification','phone_verification','transaction') NOT NULL,
  `contact_type` enum('email','phone') NOT NULL,
  `contact_value` varchar(255) NOT NULL,
  `otp_code` varchar(10) NOT NULL,
  `is_used` tinyint(1) DEFAULT 0,
  `is_expired` tinyint(1) DEFAULT 0,
  `expires_at` datetime NOT NULL,
  `used_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_otp_contact` (`contact_value`, `otp_type`),
  CONSTRAINT `otp_verifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table: audit_logs
-- ----------------------------
-- FUNGSI: Menyimpan log perubahan data untuk audit trail
-- RELASI:
--   - MANY-TO-ONE ke users (user_id) - siapa yang melakukan aksi
-- USAGE:
--   - Tracking create, update, delete di semua tabel penting
--   - Menyimpan old_data dan new_data dalam format JSON
--   - Menyimpan IP address dan user agent untuk keamanan
-- ----------------------------
DROP TABLE IF EXISTS `audit_logs`;
CREATE TABLE `audit_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `branch_id` int(11) DEFAULT NULL COMMENT 'Cabang tempat aksi dilakukan',
  `table_name` varchar(100) DEFAULT NULL,
  `record_id` int(11) DEFAULT NULL,
  `action` enum('create','update','delete') DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `old_data` json DEFAULT NULL,
  `new_data` json DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `user_agent` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_audit_table` (`table_name`, `record_id`),
  KEY `idx_audit_user` (`user_id`),
  KEY `idx_audit_branch` (`branch_id`),
  CONSTRAINT `audit_logs_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================================
-- MEMBERSHIP PACKAGES
-- ============================================================================

-- ----------------------------
-- Table: membership_packages
-- ----------------------------
-- FUNGSI: Menyimpan paket membership yang tersedia untuk dijual
-- RELASI:
--   - ONE-TO-MANY ke member_memberships - 1 paket bisa dibeli banyak member
-- PACKAGE TYPES:
--   - daily: Akses 1 hari
--   - weekly: Akses 7 hari
--   - monthly: Akses 30 hari
--   - quarterly: Akses 90 hari
--   - yearly: Akses 365 hari
--   - visit: Berdasarkan jumlah kunjungan (bukan durasi)
-- FITUR:
--   - duration_days: Untuk paket time-based (NULL untuk visit)
--   - visit_quota: Untuk paket visit-based (NULL untuk time-based)
--   - include_classes: Apakah termasuk akses kelas gratis
--   - class_quota: Jumlah kelas gratis (NULL = unlimited)
--   - facilities: JSON array fasilitas ["gym", "pool", "sauna", "locker"]
-- ----------------------------
DROP TABLE IF EXISTS `membership_packages`;
CREATE TABLE `membership_packages` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `package_type` enum('daily','weekly','monthly','quarterly','yearly','visit') NOT NULL DEFAULT 'monthly',
  `duration_days` int(11) DEFAULT NULL COMMENT 'Durasi dalam hari (NULL untuk visit-based)',
  `visit_quota` int(11) DEFAULT NULL COMMENT 'Jumlah visit untuk paket visit-based',
  `price` decimal(12,2) NOT NULL,
  -- Class access
  `include_classes` tinyint(1) DEFAULT 0 COMMENT 'Apakah include akses kelas gratis',
  `class_quota` int(11) DEFAULT NULL COMMENT 'Jumlah kelas gratis per periode (NULL = unlimited)',
  -- Facilities
  `facilities` json DEFAULT NULL COMMENT '["gym", "pool", "sauna", "locker"]',
  `is_active` tinyint(1) DEFAULT 1,
  `sort_order` int(11) DEFAULT 0,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of membership_packages
-- ----------------------------
-- CATATAN include_classes:
--   0 = Tidak termasuk kelas, harus beli class pass terpisah
--   1 = Termasuk akses SEMUA kelas GRATIS (unlimited jika class_quota NULL)
--   class_quota = Batasan jumlah kelas per periode (NULL = unlimited)
INSERT INTO `membership_packages` (`name`, `description`, `package_type`, `duration_days`, `visit_quota`, `price`, `include_classes`, `class_quota`, `facilities`, `sort_order`) VALUES
('Daily Pass', 'Akses gym 1 hari', 'daily', 1, NULL, 50000.00, 0, NULL, '["gym"]', 1),                                    -- NO class access
('Weekly Pass', 'Akses gym 7 hari', 'weekly', 7, NULL, 150000.00, 0, NULL, '["gym"]', 2),                                 -- NO class access
('Basic Monthly', 'Akses gym 1 bulan', 'monthly', 30, NULL, 300000.00, 0, NULL, '["gym"]', 3),                            -- NO class access
('Premium Monthly', 'Akses gym + pool + sauna + KELAS UNLIMITED', 'monthly', 30, NULL, 500000.00, 1, NULL, '["gym", "pool", "sauna"]', 4),  -- FREE unlimited classes
('VIP Monthly', 'All access + KELAS UNLIMITED', 'monthly', 30, NULL, 1000000.00, 1, NULL, '["gym", "pool", "sauna", "locker"]', 5),         -- FREE unlimited classes
('Quarterly Basic', 'Akses gym 3 bulan', 'quarterly', 90, NULL, 800000.00, 0, NULL, '["gym"]', 6),                        -- NO class access
('Yearly Basic', 'Akses gym 1 tahun + 48 kelas/tahun', 'yearly', 365, NULL, 2500000.00, 1, 48, '["gym"]', 7),             -- FREE 48 classes/year
('10 Visit Pass', 'Akses gym 10 kali kunjungan', 'visit', NULL, 10, 400000.00, 0, NULL, '["gym"]', 8);                    -- NO class access

-- ----------------------------
-- Table: member_memberships
-- ----------------------------
-- FUNGSI: Menyimpan membership aktif yang dimiliki member
-- RELASI:
--   - MANY-TO-ONE ke users (user_id) - membership milik user mana
--   - MANY-TO-ONE ke membership_packages (package_id) - membership dari paket mana
--   - MANY-TO-ONE ke transactions (transaction_id) - transaksi pembelian
--   - ONE-TO-MANY ke member_checkins - record check-in menggunakan membership ini
-- STATUS:
--   - active: Membership sedang aktif
--   - expired: Sudah melewati end_date atau visit habis
--   - frozen: Dibekukan sementara (tidak bisa check-in)
--   - cancelled: Dibatalkan
-- FITUR:
--   - membership_code: Kode unik untuk QR Code check-in
--   - end_date: NULL untuk visit-based (expired berdasarkan visit_remaining)
--   - visit_remaining: Untuk visit-based, berkurang setiap check-in
--   - class_remaining: Kuota kelas tersisa (jika include_classes)
--   - auto_renew: Untuk integrasi dengan subscription
-- ----------------------------
DROP TABLE IF EXISTS `member_memberships`;
CREATE TABLE `member_memberships` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `package_id` int(11) NOT NULL,
  `transaction_id` int(11) DEFAULT NULL COMMENT 'FK ke transaksi pembelian',
  `membership_code` varchar(50) NOT NULL COMMENT 'Kode unik membership untuk QR',
  `start_date` date NOT NULL,
  `end_date` date DEFAULT NULL COMMENT 'NULL untuk visit-based',
  `visit_remaining` int(11) DEFAULT NULL COMMENT 'Sisa visit untuk visit-based',
  `class_remaining` int(11) DEFAULT NULL COMMENT 'Sisa kuota kelas',
  `status` enum('active','expired','frozen','cancelled') NOT NULL DEFAULT 'active',
  `frozen_at` datetime DEFAULT NULL,
  `frozen_until` date DEFAULT NULL,
  `freeze_reason` varchar(255) DEFAULT NULL,
  `cancelled_at` datetime DEFAULT NULL,
  `cancellation_reason` varchar(255) DEFAULT NULL,
  `auto_renew` tinyint(1) DEFAULT 0,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `membership_code` (`membership_code`),
  KEY `idx_member_membership_user` (`user_id`),
  KEY `idx_member_membership_status` (`status`),
  CONSTRAINT `member_memberships_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `member_memberships_ibfk_2` FOREIGN KEY (`package_id`) REFERENCES `membership_packages` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================================
-- CHECK-IN SYSTEM
-- ============================================================================

-- ----------------------------
-- Table: member_checkins
-- ----------------------------
-- FUNGSI: Menyimpan record check-in dan check-out ke GYM
-- RELASI:
--   - MANY-TO-ONE ke users (user_id) - member yang check-in
--   - MANY-TO-ONE ke member_memberships (membership_id) - jika pakai membership
--   - MANY-TO-ONE ke member_class_passes (class_pass_id) - jika HANYA ikut kelas
--   - MANY-TO-ONE ke users (checked_in_by) - staff yang manual check-in
--
-- CHECKIN METHODS:
--   - qr_code: Scan QR code dari app member
--   - manual: Staff input manual
--   - card: Tap kartu member
--
-- ACCESS TYPES (checkin_type):
--   - gym: Akses penuh gym (butuh membership aktif)
--   - class_only: Akses HANYA untuk kelas (bisa tanpa membership, pakai class pass)
--
-- ============ BUSINESS RULES ============
--
-- 1. CHECK-IN GYM (checkin_type='gym'):
--    - WAJIB punya membership aktif
--    - membership_id harus diisi
--    - Kurangi visit_remaining untuk membership visit-based
--
-- 2. CHECK-IN CLASS ONLY (checkin_type='class_only'):
--    - Untuk orang yang HANYA ikut kelas tanpa membership gym
--    - Bisa pakai:
--      a) Membership dengan include_classes=1 → isi membership_id
--      b) Class pass → isi class_pass_id
--    - Akses TERBATAS hanya ke area kelas (studio)
--    - TIDAK bisa akses gym floor, pool, sauna, dll
--
-- 3. VALIDASI:
--    - Saat check-in, sistem cek apakah ada booking kelas hari ini
--    - Jika class_only tapi tidak ada booking → TOLAK atau beri warning
--
-- ----------------------------
DROP TABLE IF EXISTS `member_checkins`;
CREATE TABLE `member_checkins` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `branch_id` int(11) NOT NULL COMMENT 'Cabang tempat check-in',
  `user_id` int(11) NOT NULL,
  -- Tipe akses
  `checkin_type` enum('gym','class_only') NOT NULL DEFAULT 'gym' COMMENT 'gym=akses penuh, class_only=hanya area kelas',
  -- Sumber akses (minimal salah satu harus diisi)
  `membership_id` int(11) DEFAULT NULL COMMENT 'Jika pakai membership',
  `class_pass_id` int(11) DEFAULT NULL COMMENT 'Jika HANYA ikut kelas tanpa membership',
  -- Waktu
  `checkin_time` datetime NOT NULL DEFAULT current_timestamp(),
  `checkout_time` datetime DEFAULT NULL,
  -- Metode
  `checkin_method` enum('qr_code','manual','card') NOT NULL DEFAULT 'qr_code',
  `checked_in_by` int(11) DEFAULT NULL COMMENT 'Staff yang check-in manual',
  `notes` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_checkin_branch` (`branch_id`),
  KEY `idx_checkin_user` (`user_id`),
  KEY `idx_checkin_date` (`checkin_time`),
  KEY `idx_checkin_type` (`checkin_type`),
  CONSTRAINT `member_checkins_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`),
  CONSTRAINT `member_checkins_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `member_checkins_ibfk_2` FOREIGN KEY (`membership_id`) REFERENCES `member_memberships` (`id`) ON DELETE SET NULL,
  CONSTRAINT `member_checkins_ibfk_3` FOREIGN KEY (`checked_in_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `member_checkins_ibfk_4` FOREIGN KEY (`class_pass_id`) REFERENCES `member_class_passes` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================================
-- TRAINERS & PERSONAL TRAINING
-- ============================================================================

-- ----------------------------
-- Table: trainers
-- ----------------------------
-- FUNGSI: Menyimpan data tambahan untuk user dengan role trainer
-- RELASI:
--   - ONE-TO-ONE ke users (user_id) - data dasar ada di users
--   - ONE-TO-MANY ke pt_packages (trainer_id) - trainer punya paket PT khusus
--   - ONE-TO-MANY ke member_pt_sessions (trainer_id) - trainer handle banyak session member
--   - ONE-TO-MANY ke pt_bookings (trainer_id) - trainer punya banyak booking
--   - ONE-TO-MANY ke class_schedules (trainer_id) - trainer mengajar kelas
-- FITUR:
--   - specialization: Keahlian trainer (Strength, Cardio, Yoga, dll)
--   - certifications: JSON array sertifikasi ["ACE Certified", "NASM CPT"]
--   - rate_per_session: Harga per session jika freelance
--   - commission_percentage: Komisi dari PT session (untuk trainer tetap)
-- ----------------------------
DROP TABLE IF EXISTS `trainers`;
CREATE TABLE `trainers` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `specialization` varchar(255) DEFAULT NULL COMMENT 'Strength, Cardio, Yoga, dll',
  `bio` text DEFAULT NULL,
  `certifications` json DEFAULT NULL COMMENT '["ACE Certified", "NASM CPT"]',
  `experience_years` int(11) DEFAULT 0,
  `rate_per_session` decimal(12,2) DEFAULT NULL COMMENT 'Harga per session jika freelance',
  `commission_percentage` decimal(5,2) DEFAULT 0.00 COMMENT 'Komisi dari PT session',
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `trainers_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of trainers
-- ----------------------------
INSERT INTO `trainers` (`user_id`, `specialization`, `bio`, `certifications`, `experience_years`, `rate_per_session`, `commission_percentage`) VALUES
(5, 'Strength & Conditioning', 'Certified personal trainer dengan pengalaman 5 tahun di bidang strength training dan body transformation. Spesialis program fat loss dan muscle building.', '["ACE Certified Personal Trainer", "NASM Performance Enhancement Specialist", "First Aid & CPR Certified"]', 5, 250000.00, 30.00);

-- ----------------------------
-- Table: trainer_branches
-- ----------------------------
-- FUNGSI: Junction table untuk assignment trainer ke cabang
-- RELASI:
--   - MANY-TO-ONE ke trainers (trainer_id)
--   - MANY-TO-ONE ke branches (branch_id)
-- FITUR:
--   - is_primary: Menandai cabang utama trainer
--   - Trainer bisa assigned ke beberapa cabang sekaligus
-- ----------------------------
DROP TABLE IF EXISTS `trainer_branches`;
CREATE TABLE `trainer_branches` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `trainer_id` int(11) NOT NULL,
  `branch_id` int(11) NOT NULL,
  `is_primary` tinyint(1) DEFAULT 0 COMMENT 'Cabang utama trainer',
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_trainer_branch` (`trainer_id`, `branch_id`),
  KEY `idx_branch_trainers` (`branch_id`),
  CONSTRAINT `trainer_branches_ibfk_1` FOREIGN KEY (`trainer_id`) REFERENCES `trainers` (`id`) ON DELETE CASCADE,
  CONSTRAINT `trainer_branches_ibfk_2` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of trainer_branches (assigned setelah trainer tambahan dibuat di sample data)
-- ----------------------------

-- ----------------------------
-- Table: pt_packages
-- ----------------------------
-- FUNGSI: Menyimpan paket Personal Training yang tersedia untuk dijual
-- RELASI:
--   - MANY-TO-ONE ke trainers (trainer_id) - paket khusus trainer tertentu (NULL = semua trainer)
--   - ONE-TO-MANY ke member_pt_sessions - paket dibeli oleh banyak member
-- FITUR:
--   - session_count: Jumlah session dalam paket
--   - session_duration: Durasi per session dalam menit (default 60)
--   - valid_days: Masa berlaku paket dalam hari (default 90)
--   - trainer_id: NULL artinya bisa pilih trainer mana saja
-- ----------------------------
DROP TABLE IF EXISTS `pt_packages`;
CREATE TABLE `pt_packages` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `session_count` int(11) NOT NULL COMMENT 'Jumlah session',
  `session_duration` int(11) DEFAULT 60 COMMENT 'Durasi per session dalam menit',
  `price` decimal(12,2) NOT NULL,
  `valid_days` int(11) DEFAULT 90 COMMENT 'Masa berlaku paket dalam hari',
  `trainer_id` int(11) DEFAULT NULL COMMENT 'NULL = semua trainer',
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `trainer_id` (`trainer_id`),
  CONSTRAINT `pt_packages_ibfk_1` FOREIGN KEY (`trainer_id`) REFERENCES `trainers` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of pt_packages
-- ----------------------------
INSERT INTO `pt_packages` (`name`, `description`, `session_count`, `price`, `valid_days`) VALUES
('PT 1 Session', 'Single personal training session', 1, 250000.00, 30),
('PT 5 Sessions', '5 personal training sessions', 5, 1100000.00, 60),
('PT 10 Sessions', '10 personal training sessions', 10, 2000000.00, 90),
('PT 20 Sessions', '20 personal training sessions', 20, 3500000.00, 120);

-- ----------------------------
-- Table: member_pt_sessions
-- ----------------------------
-- FUNGSI: Menyimpan paket PT yang dimiliki member (saldo session)
-- RELASI:
--   - MANY-TO-ONE ke users (user_id) - member pemilik
--   - MANY-TO-ONE ke pt_packages (pt_package_id) - paket yang dibeli
--   - MANY-TO-ONE ke transactions (transaction_id) - transaksi pembelian
--   - MANY-TO-ONE ke trainers (trainer_id) - trainer yang dipilih
--   - ONE-TO-MANY ke pt_bookings - booking session dari paket ini
-- FITUR:
--   - total_sessions: Jumlah session yang dibeli
--   - used_sessions: Jumlah session yang sudah digunakan
--   - remaining_sessions: GENERATED COLUMN (total - used)
--   - expire_date: Tanggal kadaluarsa paket
-- STATUS:
--   - active: Masih ada sisa session dan belum expired
--   - expired: Sudah melewati expire_date
--   - completed: Semua session sudah digunakan
-- ----------------------------
DROP TABLE IF EXISTS `member_pt_sessions`;
CREATE TABLE `member_pt_sessions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `pt_package_id` int(11) NOT NULL,
  `transaction_id` int(11) DEFAULT NULL,
  `trainer_id` int(11) DEFAULT NULL COMMENT 'Trainer yang dipilih',
  `total_sessions` int(11) NOT NULL,
  `used_sessions` int(11) DEFAULT 0,
  `remaining_sessions` int(11) GENERATED ALWAYS AS (`total_sessions` - `used_sessions`) STORED,
  `start_date` date NOT NULL,
  `expire_date` date NOT NULL,
  `status` enum('active','expired','completed') NOT NULL DEFAULT 'active',
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_pt_session_user` (`user_id`),
  CONSTRAINT `member_pt_sessions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `member_pt_sessions_ibfk_2` FOREIGN KEY (`pt_package_id`) REFERENCES `pt_packages` (`id`),
  CONSTRAINT `member_pt_sessions_ibfk_3` FOREIGN KEY (`trainer_id`) REFERENCES `trainers` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table: pt_bookings
-- ----------------------------
-- FUNGSI: Menyimpan booking jadwal Personal Training
-- RELASI:
--   - MANY-TO-ONE ke member_pt_sessions (member_pt_session_id) - dari paket PT mana
--   - MANY-TO-ONE ke users (user_id) - member yang booking
--   - MANY-TO-ONE ke trainers (trainer_id) - trainer yang dipilih
--   - MANY-TO-ONE ke users (completed_by) - trainer yang mark complete
-- STATUS:
--   - booked: Sudah di-booking
--   - completed: Session selesai dilakukan
--   - cancelled: Dibatalkan
--   - no_show: Member tidak datang
-- BUSINESS RULES:
--   - Saat booking, cek remaining_sessions > 0
--   - Saat complete, increment used_sessions di member_pt_sessions
--   - Cancel harus minimal X jam sebelumnya (setting: pt_cancel_hours)
-- ----------------------------
DROP TABLE IF EXISTS `pt_bookings`;
CREATE TABLE `pt_bookings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `branch_id` int(11) NOT NULL COMMENT 'Cabang tempat PT session',
  `member_pt_session_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `trainer_id` int(11) NOT NULL,
  `booking_date` date NOT NULL,
  `start_time` time NOT NULL,
  `end_time` time NOT NULL,
  `status` enum('booked','completed','cancelled','no_show') NOT NULL DEFAULT 'booked',
  `notes` text DEFAULT NULL,
  `cancelled_at` datetime DEFAULT NULL,
  `cancellation_reason` varchar(255) DEFAULT NULL,
  `completed_at` datetime DEFAULT NULL,
  `completed_by` int(11) DEFAULT NULL COMMENT 'Trainer yang mark complete',
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_pt_booking_branch` (`branch_id`),
  KEY `idx_pt_booking_date` (`booking_date`),
  KEY `idx_pt_booking_trainer` (`trainer_id`, `booking_date`),
  CONSTRAINT `pt_bookings_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`),
  CONSTRAINT `pt_bookings_ibfk_1` FOREIGN KEY (`member_pt_session_id`) REFERENCES `member_pt_sessions` (`id`),
  CONSTRAINT `pt_bookings_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `pt_bookings_ibfk_3` FOREIGN KEY (`trainer_id`) REFERENCES `trainers` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================================
-- CLASS MANAGEMENT
-- ============================================================================

-- ----------------------------
-- Table: class_types
-- ----------------------------
-- FUNGSI: Menyimpan jenis-jenis kelas yang tersedia
-- RELASI:
--   - ONE-TO-MANY ke class_schedules - 1 jenis kelas punya banyak jadwal
--   - ONE-TO-MANY ke class_packages (class_type_id) - paket kelas khusus jenis tertentu
-- FITUR:
--   - default_duration: Durasi default dalam menit
--   - default_capacity: Kapasitas default peserta
--   - color: Warna untuk tampilan calendar (hex format)
--   - image: Gambar kelas untuk display
-- ----------------------------
DROP TABLE IF EXISTS `class_types`;
CREATE TABLE `class_types` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `default_duration` int(11) DEFAULT 60 COMMENT 'Durasi default dalam menit',
  `default_capacity` int(11) DEFAULT 20,
  `color` varchar(7) DEFAULT '#3B82F6' COMMENT 'Warna untuk calendar',
  `image` varchar(255) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of class_types
-- ----------------------------
INSERT INTO `class_types` (`name`, `description`, `default_duration`, `default_capacity`, `color`) VALUES
('Yoga', 'Kelas yoga untuk fleksibilitas dan ketenangan', 60, 20, '#10B981'),
('Spinning', 'Cardio cycling workout', 45, 15, '#EF4444'),
('Zumba', 'Dance fitness party', 60, 25, '#F59E0B'),
('Pilates', 'Core strength and flexibility', 60, 15, '#8B5CF6'),
('HIIT', 'High Intensity Interval Training', 30, 20, '#EC4899'),
('Boxing', 'Cardio boxing workout', 60, 15, '#1F2937'),
('Body Combat', 'Martial arts inspired workout', 55, 25, '#DC2626');

-- ----------------------------
-- Table: class_schedules
-- ----------------------------
-- FUNGSI: Menyimpan jadwal kelas (recurring atau one-time)
-- RELASI:
--   - MANY-TO-ONE ke class_types (class_type_id) - jenis kelas
--   - MANY-TO-ONE ke trainers (trainer_id) - instruktur kelas
--   - ONE-TO-MANY ke class_bookings - banyak member booking jadwal ini
-- FITUR:
--   - day_of_week: 0=Sunday, 1=Monday, ..., 6=Saturday
--   - is_recurring: true = jadwal berulang setiap minggu
--   - specific_date: Untuk kelas one-time/special event
--   - name: Override nama kelas (NULL = pakai nama dari class_type)
--   - room: Nama ruangan (Studio A, Studio B, Spinning Room)
--   - capacity: MAKSIMAL peserta per kelas
-- BUSINESS RULES - KAPASITAS KELAS:
--   - Sebelum booking, cek: SELECT COUNT(*) FROM class_bookings
--     WHERE schedule_id=? AND class_date=? AND status IN ('booked','attended')
--   - Jika count >= capacity, masukkan ke waitlist (waitlist_position)
--   - Jika ada yang cancel, pindahkan dari waitlist ke booked (FIFO)
-- ----------------------------
DROP TABLE IF EXISTS `class_schedules`;
CREATE TABLE `class_schedules` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `branch_id` int(11) NOT NULL COMMENT 'Cabang tempat kelas diadakan',
  `class_type_id` int(11) NOT NULL,
  `trainer_id` int(11) DEFAULT NULL,
  `name` varchar(100) DEFAULT NULL COMMENT 'Override nama kelas',
  `day_of_week` tinyint(1) NOT NULL COMMENT '0=Sunday, 1=Monday, ..., 6=Saturday',
  `start_time` time NOT NULL,
  `end_time` time NOT NULL,
  `capacity` int(11) NOT NULL DEFAULT 20,
  `room` varchar(50) DEFAULT NULL COMMENT 'Studio A, Studio B, dll',
  `is_recurring` tinyint(1) DEFAULT 1 COMMENT 'Jadwal berulang tiap minggu',
  `specific_date` date DEFAULT NULL COMMENT 'Untuk kelas one-time',
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_schedule_branch` (`branch_id`),
  KEY `idx_schedule_day` (`day_of_week`, `start_time`),
  CONSTRAINT `class_schedules_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`),
  CONSTRAINT `class_schedules_ibfk_1` FOREIGN KEY (`class_type_id`) REFERENCES `class_types` (`id`),
  CONSTRAINT `class_schedules_ibfk_2` FOREIGN KEY (`trainer_id`) REFERENCES `trainers` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of class_schedules
-- ----------------------------
-- Jadwal kelas Jakarta (schedule_id = urutan insert)
INSERT INTO `class_schedules` (`branch_id`, `class_type_id`, `trainer_id`, `day_of_week`, `start_time`, `end_time`, `capacity`, `room`) VALUES
(1, 1, 1, 1, '07:00:00', '08:00:00', 20, 'Studio A'),  -- id=1: Yoga Monday @JKT
(1, 1, 1, 3, '07:00:00', '08:00:00', 20, 'Studio A'),  -- id=2: Yoga Wednesday @JKT
(1, 2, 1, 2, '18:00:00', '18:45:00', 15, 'Spinning Room'),  -- id=3: Spinning Tuesday @JKT
(1, 2, 1, 4, '18:00:00', '18:45:00', 15, 'Spinning Room'),  -- id=4: Spinning Thursday @JKT
(1, 3, 1, 6, '09:00:00', '10:00:00', 25, 'Studio B'),  -- id=5: Zumba Saturday @JKT
(1, 4, 2, 1, '18:00:00', '19:00:00', 15, 'Studio A'),  -- id=6: Pilates Monday @JKT (Coach Maya)
(1, 4, 2, 2, '09:00:00', '10:00:00', 15, 'Studio A');  -- id=7: Pilates Tuesday @JKT (Coach Maya)

-- ----------------------------
-- Table: class_bookings
-- ----------------------------
-- FUNGSI: Menyimpan booking kelas oleh member
-- RELASI:
--   - MANY-TO-ONE ke users (user_id) - member yang booking
--   - MANY-TO-ONE ke class_schedules (schedule_id) - jadwal kelas yang di-booking
--   - MANY-TO-ONE ke member_memberships (membership_id) - jika pakai benefit membership
--   - MANY-TO-ONE ke member_class_passes (class_pass_id) - jika pakai class pass
-- STATUS:
--   - booked: Sudah di-booking, belum hadir
--   - attended: Member hadir di kelas
--   - cancelled: Dibatalkan oleh member/admin
--   - no_show: Member tidak hadir tanpa cancel
-- FITUR:
--   - class_date: Tanggal spesifik kelas (bukan recurring)
--   - waitlist_position: Posisi di waiting list jika kelas penuh (NULL = tidak di waitlist)
--   - UNIQUE constraint: 1 member tidak bisa booking jadwal & tanggal yang sama 2x
--
-- ============ BUSINESS RULES ============
--
-- 1. VALIDASI PEMBAYARAN (sebelum booking):
--    - Cek apakah user punya akses kelas:
--      a) Membership aktif dengan include_classes=1 DAN (class_quota NULL ATAU class_remaining > 0)
--      b) Class pass aktif dengan used_classes < total_classes
--    - Jika tidak punya akses → TOLAK booking
--
-- 2. VALIDASI KAPASITAS (sebelum booking):
--    SELECT COUNT(*) FROM class_bookings
--    WHERE schedule_id=? AND class_date=? AND status IN ('booked','attended')
--    - Jika count < capacity → booking berhasil (status='booked', waitlist_position=NULL)
--    - Jika count >= capacity → masuk waitlist (status='booked', waitlist_position=urutan)
--
-- 3. CANCEL POLICY:
--    - Cancel harus minimal X jam sebelum kelas (setting: class_cancel_hours)
--    - Jika cancel → kuota dikembalikan (class_remaining++ atau used_classes--)
--    - Member di waitlist otomatis naik posisi
--
-- 4. NO SHOW POLICY:
--    - Jika tidak hadir tanpa cancel → status='no_show'
--    - Kuota TIDAK dikembalikan (sudah terpakai)
--    - Bisa ada penalti (setting: no_show_penalty)
--
-- TRACKING AKSES KELAS:
--   - access_type: Sumber akses kelas (membership/class_pass)
--   - membership_id: Jika pakai benefit membership (include_classes=1)
--   - class_pass_id: Jika pakai class pass yang dibeli terpisah
-- ----------------------------
DROP TABLE IF EXISTS `class_bookings`;
CREATE TABLE `class_bookings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `branch_id` int(11) NOT NULL COMMENT 'Cabang tempat kelas',
  `user_id` int(11) NOT NULL,
  `schedule_id` int(11) NOT NULL,
  `class_date` date NOT NULL COMMENT 'Tanggal kelas yang di-booking',
  -- Tracking sumber akses kelas (untuk validasi & kuota)
  `access_type` enum('membership','class_pass') NOT NULL COMMENT 'Sumber akses: membership benefit atau class pass',
  `membership_id` int(11) DEFAULT NULL COMMENT 'FK ke member_memberships jika pakai benefit membership',
  `class_pass_id` int(11) DEFAULT NULL COMMENT 'FK ke member_class_passes jika pakai class pass',
  -- Status booking
  `status` enum('booked','attended','cancelled','no_show') NOT NULL DEFAULT 'booked',
  `booked_at` datetime DEFAULT current_timestamp(),
  `cancelled_at` datetime DEFAULT NULL,
  `cancellation_reason` varchar(255) DEFAULT NULL,
  `attended_at` datetime DEFAULT NULL,
  `waitlist_position` int(11) DEFAULT NULL COMMENT 'Posisi di waitlist jika penuh',
  `notes` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_booking` (`user_id`, `schedule_id`, `class_date`),
  KEY `idx_class_booking_branch` (`branch_id`),
  KEY `idx_class_booking_date` (`class_date`),
  KEY `idx_class_booking_membership` (`membership_id`),
  KEY `idx_class_booking_class_pass` (`class_pass_id`),
  CONSTRAINT `class_bookings_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`),
  CONSTRAINT `class_bookings_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `class_bookings_ibfk_2` FOREIGN KEY (`schedule_id`) REFERENCES `class_schedules` (`id`),
  CONSTRAINT `class_bookings_ibfk_3` FOREIGN KEY (`membership_id`) REFERENCES `member_memberships` (`id`) ON DELETE SET NULL,
  CONSTRAINT `class_bookings_ibfk_4` FOREIGN KEY (`class_pass_id`) REFERENCES `member_class_passes` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table: class_packages
-- ----------------------------
-- FUNGSI: Menyimpan paket kelas untuk non-member atau member tanpa include_classes
-- RELASI:
--   - MANY-TO-ONE ke class_types (class_type_id) - untuk paket jenis kelas tertentu (NULL = semua)
--   - ONE-TO-MANY ke member_class_passes - dibeli oleh banyak member
-- FITUR:
--   - class_count: Jumlah kelas (999 = unlimited)
--   - valid_days: Masa berlaku dalam hari
--   - class_type_id: NULL = bisa ikut semua jenis kelas
-- ----------------------------
DROP TABLE IF EXISTS `class_packages`;
CREATE TABLE `class_packages` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `class_count` int(11) NOT NULL COMMENT 'Jumlah kelas',
  `price` decimal(12,2) NOT NULL,
  `valid_days` int(11) DEFAULT 30 COMMENT 'Masa berlaku dalam hari',
  `class_type_id` int(11) DEFAULT NULL COMMENT 'NULL = semua jenis kelas',
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  CONSTRAINT `class_packages_ibfk_1` FOREIGN KEY (`class_type_id`) REFERENCES `class_types` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of class_packages
-- ----------------------------
INSERT INTO `class_packages` (`name`, `description`, `class_count`, `price`, `valid_days`) VALUES
('Single Class', 'Ikut 1 kelas', 1, 50000.00, 7),
('5 Class Pass', 'Paket 5 kelas', 5, 200000.00, 30),
('10 Class Pass', 'Paket 10 kelas', 10, 350000.00, 60),
('Unlimited Monthly', 'Unlimited kelas 1 bulan', 999, 500000.00, 30);

-- ----------------------------
-- Table: member_class_passes
-- ----------------------------
-- FUNGSI: Menyimpan paket kelas yang dimiliki member (saldo kelas)
-- RELASI:
--   - MANY-TO-ONE ke users (user_id) - member pemilik
--   - MANY-TO-ONE ke class_packages (class_package_id) - paket yang dibeli
--   - MANY-TO-ONE ke transactions (transaction_id) - transaksi pembelian
-- FITUR:
--   - total_classes: Jumlah kelas yang dibeli
--   - used_classes: Jumlah kelas yang sudah digunakan
--   - remaining_classes: GENERATED COLUMN (total - used)
--   - expire_date: Tanggal kadaluarsa paket
-- STATUS:
--   - active: Masih ada sisa dan belum expired
--   - expired: Sudah melewati expire_date
--   - completed: Semua kelas sudah digunakan
-- ----------------------------
DROP TABLE IF EXISTS `member_class_passes`;
CREATE TABLE `member_class_passes` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `class_package_id` int(11) NOT NULL,
  `transaction_id` int(11) DEFAULT NULL,
  `total_classes` int(11) NOT NULL,
  `used_classes` int(11) DEFAULT 0,
  `remaining_classes` int(11) GENERATED ALWAYS AS (`total_classes` - `used_classes`) STORED,
  `start_date` date NOT NULL,
  `expire_date` date NOT NULL,
  `status` enum('active','expired','completed') NOT NULL DEFAULT 'active',
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_class_pass_user` (`user_id`),
  CONSTRAINT `member_class_passes_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `member_class_passes_ibfk_2` FOREIGN KEY (`class_package_id`) REFERENCES `class_packages` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================================
-- PRODUCTS & INVENTORY (POS SYSTEM)
-- ============================================================================

-- ----------------------------
-- Table: product_categories
-- ----------------------------
-- FUNGSI: Menyimpan kategori produk untuk POS
-- RELASI:
--   - ONE-TO-MANY ke products - 1 kategori punya banyak produk
-- CONTOH KATEGORI:
--   - Supplements: Whey protein, BCAA, dll
--   - Beverages: Minuman, shake
--   - Snacks: Energy bar, dll
--   - Apparel: Baju, celana olahraga
--   - Accessories: Sarung tangan, botol, dll
--   - Rental: Handuk, locker (untuk penyewaan)
-- ----------------------------
DROP TABLE IF EXISTS `product_categories`;
CREATE TABLE `product_categories` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `image` varchar(255) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `sort_order` int(11) DEFAULT 0,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of product_categories
-- ----------------------------
INSERT INTO `product_categories` (`name`, `description`, `sort_order`) VALUES
('Supplements', 'Suplemen fitness dan kesehatan', 1),
('Beverages', 'Minuman dan shake', 2),
('Snacks', 'Snack sehat dan energy bar', 3),
('Apparel', 'Baju dan perlengkapan olahraga', 4),
('Accessories', 'Aksesoris gym', 5),
('Rental', 'Penyewaan perlengkapan', 6);

-- ----------------------------
-- Table: products
-- ----------------------------
-- FUNGSI: Menyimpan data produk untuk POS
-- RELASI:
--   - MANY-TO-ONE ke product_categories (category_id) - produk dalam kategori mana
--   - ONE-TO-MANY ke product_stock_logs - history perubahan stock
--   - ONE-TO-MANY ke transaction_items - produk masuk ke transaksi
-- FITUR:
--   - sku: Stock Keeping Unit (kode unik produk)
--   - cost_price: Harga modal untuk hitung profit
--   - min_stock: Minimum stock untuk warning low stock
--   - is_rental: Produk rental (handuk, locker) tidak mengurangi stock
--   - rental_duration: per_day, per_visit untuk produk rental
-- ----------------------------
DROP TABLE IF EXISTS `products`;
CREATE TABLE `products` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `category_id` int(11) DEFAULT NULL,
  `sku` varchar(50) DEFAULT NULL,
  `name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `price` decimal(12,2) NOT NULL,
  `cost_price` decimal(12,2) DEFAULT NULL COMMENT 'Harga modal',
  `stock` int(11) DEFAULT 0,
  `min_stock` int(11) DEFAULT 5 COMMENT 'Minimum stock warning',
  `is_rental` tinyint(1) DEFAULT 0 COMMENT 'Produk rental (towel, locker)',
  `rental_duration` varchar(50) DEFAULT NULL COMMENT 'per_day, per_visit',
  `image` varchar(255) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `sku` (`sku`),
  KEY `idx_product_category` (`category_id`),
  CONSTRAINT `products_ibfk_1` FOREIGN KEY (`category_id`) REFERENCES `product_categories` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of products
-- ----------------------------
INSERT INTO `products` (`category_id`, `sku`, `name`, `description`, `price`, `cost_price`, `stock`, `is_rental`, `rental_duration`) VALUES
(1, 'SUP-WHEY-001', 'Whey Protein 1kg', 'Whey protein isolate', 350000.00, 280000.00, 20, 0, NULL),
(1, 'SUP-BCAA-001', 'BCAA 300g', 'Branched-chain amino acids', 250000.00, 180000.00, 15, 0, NULL),
(2, 'BEV-SHAKE-001', 'Protein Shake', 'Ready to drink protein shake', 35000.00, 20000.00, 50, 0, NULL),
(2, 'BEV-WATER-001', 'Mineral Water 600ml', 'Air mineral', 8000.00, 4000.00, 100, 0, NULL),
(3, 'SNK-BAR-001', 'Energy Bar', 'High protein energy bar', 25000.00, 15000.00, 40, 0, NULL),
(4, 'APP-SHIRT-001', 'Gym T-Shirt', 'Kaos olahraga', 150000.00, 80000.00, 30, 0, NULL),
(5, 'ACC-GLOVE-001', 'Gym Gloves', 'Sarung tangan gym', 120000.00, 60000.00, 25, 0, NULL),
(6, 'RNT-TOWEL-001', 'Towel Rental', 'Sewa handuk', 10000.00, 2000.00, 0, 1, 'per_visit'),
(6, 'RNT-LOCKER-001', 'Locker Rental', 'Sewa locker harian', 15000.00, 0.00, 0, 1, 'per_day');

-- ----------------------------
-- Table: product_stock_logs
-- ----------------------------
-- FUNGSI: Menyimpan log perubahan stock produk (audit trail inventory)
-- RELASI:
--   - MANY-TO-ONE ke products (product_id) - produk yang berubah stocknya
--   - MANY-TO-ONE ke users (created_by) - siapa yang melakukan perubahan
-- LOG TYPES:
--   - in: Stock masuk (purchase order, return)
--   - out: Stock keluar (penjualan)
--   - adjustment: Adjustment manual (stock opname, expired, rusak)
-- USAGE:
--   - Tracking perubahan stock untuk audit
--   - Reference ke transaksi atau PO yang menyebabkan perubahan
-- ----------------------------
DROP TABLE IF EXISTS `product_stock_logs`;
CREATE TABLE `product_stock_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `branch_id` int(11) NOT NULL COMMENT 'Cabang tempat perubahan stock',
  `product_id` int(11) NOT NULL,
  `type` enum('in','out','adjustment') NOT NULL,
  `quantity` int(11) NOT NULL,
  `stock_before` int(11) NOT NULL,
  `stock_after` int(11) NOT NULL,
  `reference_type` varchar(50) DEFAULT NULL COMMENT 'transaction, purchase_order, adjustment',
  `reference_id` int(11) DEFAULT NULL,
  `notes` varchar(255) DEFAULT NULL,
  `created_by` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_stock_log_branch` (`branch_id`),
  KEY `idx_stock_log_product` (`product_id`),
  CONSTRAINT `product_stock_logs_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`),
  CONSTRAINT `product_stock_logs_ibfk_1` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE,
  CONSTRAINT `product_stock_logs_ibfk_2` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table: branch_product_stock
-- ----------------------------
-- FUNGSI: Menyimpan stock produk per cabang
-- RELASI:
--   - MANY-TO-ONE ke branches (branch_id)
--   - MANY-TO-ONE ke products (product_id)
-- FITUR:
--   - Katalog produk global, stock per cabang
--   - min_stock: Batas minimum stock per cabang
-- ----------------------------
DROP TABLE IF EXISTS `branch_product_stock`;
CREATE TABLE `branch_product_stock` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `branch_id` int(11) NOT NULL,
  `product_id` int(11) NOT NULL,
  `stock` int(11) NOT NULL DEFAULT 0,
  `min_stock` int(11) DEFAULT 5,
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_branch_product` (`branch_id`, `product_id`),
  KEY `idx_product_stock` (`product_id`),
  CONSTRAINT `branch_product_stock_ibfk_1` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`) ON DELETE CASCADE,
  CONSTRAINT `branch_product_stock_ibfk_2` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================================
-- TRANSACTIONS
-- ============================================================================

-- ----------------------------
-- Table: transactions
-- ----------------------------
-- FUNGSI: Menyimpan header transaksi (invoice)
-- RELASI:
--   - MANY-TO-ONE ke users (user_id) - member yang beli (NULL untuk walk-in)
--   - MANY-TO-ONE ke users (staff_id) - kasir yang proses
--   - ONE-TO-MANY ke transaction_items - detail item yang dibeli
--   - ONE-TO-MANY ke member_memberships (transaction_id) - membership yang dibeli
--   - ONE-TO-MANY ke member_pt_sessions (transaction_id) - PT package yang dibeli
--   - ONE-TO-MANY ke member_class_passes (transaction_id) - class pass yang dibeli
-- PAYMENT METHODS:
--   - cash: Tunai
--   - transfer: Transfer bank
--   - qris: QRIS
--   - card: Kartu debit/kredit
--   - ewallet: E-wallet (GoPay, OVO, dll)
--   - other: Lainnya
-- PAYMENT STATUS:
--   - pending: Menunggu pembayaran
--   - paid: Sudah dibayar
--   - failed: Gagal
--   - refunded: Sudah di-refund
--   - partial: Pembayaran sebagian
-- PRICING:
--   - subtotal: Total sebelum diskon
--   - discount_amount: Jumlah diskon
--   - subtotal_after_discount: Subtotal setelah diskon
--   - tax_amount: Jumlah pajak
--   - service_charge_amount: Jumlah service charge
--   - grand_total: Total akhir yang harus dibayar
-- ----------------------------
DROP TABLE IF EXISTS `transactions`;
CREATE TABLE `transactions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `branch_id` int(11) NOT NULL COMMENT 'Cabang tempat transaksi',
  `transaction_code` varchar(50) NOT NULL,
  `user_id` int(11) DEFAULT NULL COMMENT 'Member yang beli (NULL untuk walk-in)',
  `staff_id` int(11) DEFAULT NULL COMMENT 'Kasir/staff',
  `customer_name` varchar(100) DEFAULT NULL COMMENT 'Nama customer walk-in',
  `customer_phone` varchar(20) DEFAULT NULL,
  `customer_email` varchar(100) DEFAULT NULL,
  -- Pricing
  `subtotal` decimal(12,2) NOT NULL DEFAULT 0,
  `discount_type` enum('percentage','fixed') DEFAULT NULL,
  `discount_value` decimal(12,2) DEFAULT 0,
  `discount_amount` decimal(12,2) DEFAULT 0,
  `subtotal_after_discount` decimal(12,2) NOT NULL DEFAULT 0,
  `tax_percentage` decimal(5,2) DEFAULT 0,
  `tax_amount` decimal(12,2) DEFAULT 0,
  `service_charge_percentage` decimal(5,2) DEFAULT 0,
  `service_charge_amount` decimal(12,2) DEFAULT 0,
  `grand_total` decimal(12,2) NOT NULL DEFAULT 0,
  -- Payment
  `payment_method` enum('cash','transfer','qris','card','ewallet','other') DEFAULT NULL,
  `payment_status` enum('pending','paid','failed','refunded','partial') NOT NULL DEFAULT 'pending',
  `paid_amount` decimal(12,2) DEFAULT 0,
  `change_amount` decimal(12,2) DEFAULT 0,
  `paid_at` datetime DEFAULT NULL,
  -- Promo & Voucher
  `promo_id` int(11) DEFAULT NULL,
  `promo_discount` decimal(12,2) DEFAULT 0 COMMENT 'Jumlah diskon dari promo',
  `voucher_code` varchar(50) DEFAULT NULL,
  `voucher_discount` decimal(12,2) DEFAULT 0 COMMENT 'Jumlah diskon dari voucher',
  `notes` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `transaction_code` (`transaction_code`),
  KEY `idx_transaction_branch` (`branch_id`),
  KEY `idx_transaction_user` (`user_id`),
  KEY `idx_transaction_date` (`created_at`),
  KEY `idx_transaction_status` (`payment_status`),
  CONSTRAINT `transactions_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`),
  CONSTRAINT `transactions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `transactions_ibfk_2` FOREIGN KEY (`staff_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table: transaction_items
-- ----------------------------
-- FUNGSI: Menyimpan detail item dalam transaksi
-- RELASI:
--   - MANY-TO-ONE ke transactions (transaction_id) - transaksi induk
-- ITEM TYPES:
--   - membership: Pembelian membership package
--   - class_pass: Pembelian class package
--   - pt_package: Pembelian PT package
--   - product: Pembelian produk POS
--   - rental: Penyewaan (handuk, locker)
--   - service: Layanan lainnya
-- FITUR:
--   - item_id: FK ke tabel terkait (membership_packages.id, products.id, dll)
--   - metadata: JSON untuk data tambahan (trainer_id, start_date, dll)
--   - Diskon per item terpisah dari diskon transaksi
-- ----------------------------
DROP TABLE IF EXISTS `transaction_items`;
CREATE TABLE `transaction_items` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `transaction_id` int(11) NOT NULL,
  `item_type` enum('membership','class_pass','pt_package','product','rental','service') NOT NULL,
  `item_id` int(11) DEFAULT NULL COMMENT 'FK ke tabel terkait',
  `item_name` varchar(100) NOT NULL,
  `item_description` varchar(255) DEFAULT NULL,
  `quantity` int(11) NOT NULL DEFAULT 1,
  `unit_price` decimal(12,2) NOT NULL,
  -- Diskon per item
  `discount_type` enum('percentage','fixed') DEFAULT NULL,
  `discount_value` decimal(12,2) DEFAULT 0,
  `discount_amount` decimal(12,2) DEFAULT 0,
  `subtotal` decimal(12,2) NOT NULL,
  -- Metadata tambahan (untuk membership: durasi, untuk PT: trainer_id, dll)
  `metadata` json DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_transaction_item` (`transaction_id`),
  CONSTRAINT `transaction_items_ibfk_1` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================================
-- RECURRING / SUBSCRIPTIONS
-- ============================================================================

-- ----------------------------
-- Table: payment_methods
-- ----------------------------
-- FUNGSI: Menyimpan metode pembayaran tersimpan untuk auto-billing subscription
-- RELASI:
--   - MANY-TO-ONE ke users (user_id) - pemilik payment method
--   - ONE-TO-MANY ke subscriptions (payment_method_id) - digunakan untuk subscription
-- TYPES:
--   - card: Kartu kredit/debit
--   - bank_account: Rekening bank
--   - ewallet: E-wallet
-- SECURITY:
--   - masked_number: Nomor yang di-mask (**** **** **** 1234)
--   - token: Token dari payment gateway (bukan data kartu asli)
-- ----------------------------
DROP TABLE IF EXISTS `payment_methods`;
CREATE TABLE `payment_methods` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `type` enum('card','bank_account','ewallet') NOT NULL,
  `provider` varchar(50) DEFAULT NULL COMMENT 'visa, mastercard, bca, gopay',
  `masked_number` varchar(50) DEFAULT NULL COMMENT '**** **** **** 1234',
  `holder_name` varchar(100) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL COMMENT 'Token dari payment gateway',
  `is_default` tinyint(1) DEFAULT 0,
  `expires_at` date DEFAULT NULL COMMENT 'Untuk kartu kredit',
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_payment_method_user` (`user_id`),
  CONSTRAINT `payment_methods_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table: subscriptions
-- ----------------------------
-- FUNGSI: Menyimpan data subscription untuk recurring billing (auto-renew)
-- RELASI:
--   - MANY-TO-ONE ke users (user_id) - pemilik subscription
--   - MANY-TO-ONE ke payment_methods (payment_method_id) - metode pembayaran
--   - ONE-TO-MANY ke subscription_invoices - invoice yang dihasilkan
-- ITEM TYPES:
--   - membership: Auto-renew membership
--   - class_pass: Auto-renew class pass
--   - pt_package: Auto-renew PT package
-- BILLING CYCLE:
--   - weekly: Mingguan
--   - monthly: Bulanan
--   - quarterly: 3 bulanan
--   - yearly: Tahunan
-- STATUS:
--   - active: Aktif (akan di-charge sesuai jadwal)
--   - paused: Dijeda sementara
--   - cancelled: Dibatalkan
--   - expired: Expired
--   - failed: Gagal charge berkali-kali
-- RETRY LOGIC:
--   - retry_count: Berapa kali sudah retry
--   - Setting: subscription_retry_days, subscription_retry_count
-- ----------------------------
DROP TABLE IF EXISTS `subscriptions`;
CREATE TABLE `subscriptions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `subscription_code` varchar(50) NOT NULL,
  `user_id` int(11) NOT NULL,
  `item_type` enum('membership','class_pass','pt_package') NOT NULL,
  `item_id` int(11) NOT NULL COMMENT 'FK ke packages',
  `item_name` varchar(100) NOT NULL,
  -- Pricing
  `base_price` decimal(12,2) NOT NULL,
  `discount_type` enum('percentage','fixed') DEFAULT NULL,
  `discount_value` decimal(12,2) DEFAULT 0,
  `discount_amount` decimal(12,2) DEFAULT 0,
  `recurring_price` decimal(12,2) NOT NULL COMMENT 'Harga yang dicharge setiap cycle',
  -- Billing cycle
  `billing_cycle` enum('weekly','monthly','quarterly','yearly') NOT NULL,
  `billing_day` tinyint(2) DEFAULT 1 COMMENT 'Tanggal billing (1-31)',
  `next_billing_date` date NOT NULL,
  -- Payment method
  `payment_method_id` int(11) DEFAULT NULL,
  -- Status
  `status` enum('active','paused','cancelled','expired','failed') NOT NULL DEFAULT 'active',
  `started_at` datetime DEFAULT current_timestamp(),
  `paused_at` datetime DEFAULT NULL,
  `paused_until` date DEFAULT NULL,
  `pause_reason` varchar(255) DEFAULT NULL,
  `cancelled_at` datetime DEFAULT NULL,
  `cancellation_reason` varchar(255) DEFAULT NULL,
  `failed_at` datetime DEFAULT NULL,
  `failure_reason` varchar(255) DEFAULT NULL,
  `retry_count` int(11) DEFAULT 0,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `subscription_code` (`subscription_code`),
  KEY `idx_subscription_user` (`user_id`),
  KEY `idx_subscription_billing` (`next_billing_date`, `status`),
  CONSTRAINT `subscriptions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `subscriptions_ibfk_2` FOREIGN KEY (`payment_method_id`) REFERENCES `payment_methods` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table: subscription_invoices
-- ----------------------------
-- FUNGSI: Menyimpan invoice yang dihasilkan dari subscription (per billing cycle)
-- RELASI:
--   - MANY-TO-ONE ke subscriptions (subscription_id) - subscription induk
--   - MANY-TO-ONE ke transactions (transaction_id) - transaksi jika sudah dibayar
-- STATUS:
--   - pending: Menunggu pembayaran
--   - paid: Sudah dibayar
--   - failed: Gagal charge
--   - cancelled: Dibatalkan
-- USAGE:
--   - Cronjob check next_billing_date dari subscriptions
--   - Generate invoice dan attempt charge ke payment_method
--   - Jika sukses, create transaction dan update subscription.next_billing_date
--   - Jika gagal, increment retry_count dan coba lagi
-- ----------------------------
DROP TABLE IF EXISTS `subscription_invoices`;
CREATE TABLE `subscription_invoices` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `branch_id` int(11) DEFAULT NULL COMMENT 'Cabang yang generate invoice',
  `subscription_id` int(11) NOT NULL,
  `transaction_id` int(11) DEFAULT NULL COMMENT 'FK ke transactions jika sudah bayar',
  `invoice_number` varchar(50) NOT NULL,
  `amount` decimal(12,2) NOT NULL,
  `billing_period_start` date NOT NULL,
  `billing_period_end` date NOT NULL,
  `due_date` date NOT NULL,
  `status` enum('pending','paid','failed','cancelled') NOT NULL DEFAULT 'pending',
  `attempt_count` int(11) DEFAULT 0,
  `last_attempt_at` datetime DEFAULT NULL,
  `paid_at` datetime DEFAULT NULL,
  `failed_reason` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `invoice_number` (`invoice_number`),
  KEY `idx_sub_invoice_branch` (`branch_id`),
  KEY `idx_subscription_invoice` (`subscription_id`),
  KEY `idx_invoice_due_date` (`due_date`, `status`),
  CONSTRAINT `subscription_invoices_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`) ON DELETE SET NULL,
  CONSTRAINT `subscription_invoices_ibfk_1` FOREIGN KEY (`subscription_id`) REFERENCES `subscriptions` (`id`) ON DELETE CASCADE,
  CONSTRAINT `subscription_invoices_ibfk_2` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================================
-- PROMOS & VOUCHERS
-- ============================================================================

-- ----------------------------
-- Table: promos
-- ----------------------------
-- FUNGSI: Menyimpan promo/diskon yang berlaku otomatis
-- RELASI:
--   - Referenced by transactions (promo_id)
-- PROMO TYPES:
--   - percentage: Diskon persentase
--   - fixed: Diskon nominal tetap
--   - free_item: Gratis item tertentu
-- APPLICABLE TO:
--   - all: Berlaku untuk semua item
--   - membership: Hanya untuk membership
--   - class: Hanya untuk class pass
--   - pt: Hanya untuk PT package
--   - product: Hanya untuk produk POS
-- USAGE LIMIT:
--   - usage_limit: Total penggunaan maksimal (NULL = unlimited)
--   - per_user_limit: Maksimal penggunaan per user
--   - new_member_only: Hanya untuk member baru
--   - member_only: Hanya untuk member (bukan walk-in)
-- ----------------------------
DROP TABLE IF EXISTS `promos`;
CREATE TABLE `promos` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `promo_type` enum('percentage','fixed','free_item') NOT NULL,
  `discount_value` decimal(12,2) DEFAULT 0,
  `min_purchase` decimal(12,2) DEFAULT 0 COMMENT 'Minimum pembelian',
  `max_discount` decimal(12,2) DEFAULT NULL COMMENT 'Maksimum potongan (untuk percentage)',
  -- Applicable to
  `applicable_to` enum('all','membership','class','pt','product') NOT NULL DEFAULT 'all',
  `applicable_items` json DEFAULT NULL COMMENT 'Specific item IDs',
  -- Period
  `start_date` datetime NOT NULL,
  `end_date` datetime NOT NULL,
  -- Usage limit
  `usage_limit` int(11) DEFAULT NULL COMMENT 'Total penggunaan maksimal',
  `usage_count` int(11) DEFAULT 0,
  `per_user_limit` int(11) DEFAULT 1 COMMENT 'Penggunaan per user',
  -- Conditions
  `new_member_only` tinyint(1) DEFAULT 0,
  `member_only` tinyint(1) DEFAULT 0,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table: vouchers
-- ----------------------------
-- FUNGSI: Menyimpan voucher code yang bisa diinput manual oleh customer
-- RELASI:
--   - ONE-TO-MANY ke voucher_usages - tracking penggunaan voucher
-- PERBEDAAN DENGAN PROMO:
--   - Voucher harus diinput kode-nya
--   - Promo otomatis ter-apply jika memenuhi syarat
-- VOUCHER TYPES: Sama dengan promo (percentage, fixed, free_item)
-- ----------------------------
DROP TABLE IF EXISTS `vouchers`;
CREATE TABLE `vouchers` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `code` varchar(50) NOT NULL,
  `voucher_type` enum('percentage','fixed','free_item') NOT NULL,
  `discount_value` decimal(12,2) DEFAULT 0,
  `min_purchase` decimal(12,2) DEFAULT 0,
  `max_discount` decimal(12,2) DEFAULT NULL,
  -- Applicable to
  `applicable_to` enum('all','membership','class','pt','product') NOT NULL DEFAULT 'all',
  `applicable_items` json DEFAULT NULL COMMENT 'Specific item IDs',
  -- Period
  `start_date` datetime NOT NULL,
  `end_date` datetime NOT NULL,
  -- Usage
  `usage_limit` int(11) DEFAULT 1,
  `usage_count` int(11) DEFAULT 0,
  `is_single_use` tinyint(1) DEFAULT 1 COMMENT 'Sekali pakai per user',
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table: voucher_usages
-- ----------------------------
-- FUNGSI: Menyimpan log penggunaan voucher
-- RELASI:
--   - MANY-TO-ONE ke vouchers (voucher_id) - voucher yang digunakan
--   - MANY-TO-ONE ke users (user_id) - user yang menggunakan
--   - MANY-TO-ONE ke transactions (transaction_id) - transaksi yang menggunakan voucher
-- USAGE:
--   - Tracking siapa pakai voucher kapan
--   - Validasi is_single_use: cek apakah user sudah pernah pakai
--   - Increment usage_count di vouchers setelah digunakan
-- ----------------------------
DROP TABLE IF EXISTS `voucher_usages`;
CREATE TABLE `voucher_usages` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `voucher_id` int(11) NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  `transaction_id` int(11) DEFAULT NULL,
  `discount_amount` decimal(12,2) NOT NULL,
  `used_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_voucher_usage` (`voucher_id`, `user_id`),
  CONSTRAINT `voucher_usages_ibfk_1` FOREIGN KEY (`voucher_id`) REFERENCES `vouchers` (`id`) ON DELETE CASCADE,
  CONSTRAINT `voucher_usages_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `voucher_usages_ibfk_3` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table: discount_usages
-- ----------------------------
-- FUNGSI: Mencatat penggunaan promo & voucher secara terpadu
-- RELASI:
--   - discount_type + discount_id → referensi ke promos atau vouchers
--   - MANY-TO-ONE ke users (user_id) - user yang menggunakan
--   - MANY-TO-ONE ke transactions (transaction_id) - transaksi terkait
-- USAGE:
--   - Validasi per_user_limit untuk promo
--   - Validasi is_single_use untuk voucher
--   - Reporting penggunaan diskon
-- ----------------------------
DROP TABLE IF EXISTS `discount_usages`;
CREATE TABLE `discount_usages` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `discount_type` enum('promo','voucher') NOT NULL COMMENT 'Jenis diskon',
  `discount_id` int(11) NOT NULL COMMENT 'ID promo atau voucher',
  `user_id` int(11) DEFAULT NULL,
  `transaction_id` int(11) DEFAULT NULL,
  `discount_amount` decimal(12,2) NOT NULL,
  `used_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_discount_usage` (`discount_type`, `discount_id`, `user_id`),
  KEY `idx_discount_transaction` (`transaction_id`),
  CONSTRAINT `discount_usages_user_fk` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `discount_usages_transaction_fk` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================================
-- SETTINGS
-- ============================================================================

-- ----------------------------
-- Table: settings
-- ----------------------------
-- FUNGSI: Menyimpan konfigurasi sistem (key-value store)
-- RELASI: Tidak ada relasi langsung, diakses via key
-- TYPES:
--   - string: Teks biasa
--   - number: Angka
--   - boolean: true/false
--   - json: Data JSON kompleks
-- CATEGORIES:
--   - General: gym_name, gym_address, gym_phone, gym_email
--   - Tax: tax_enabled, tax_name, tax_percentage
--   - Service Charge: service_charge_enabled, service_charge_percentage
--   - Check-in: checkin_cooldown_minutes
--   - Booking: class_booking_advance_days, class_cancel_hours, pt_booking_advance_days, pt_cancel_hours
--   - Subscription: subscription_retry_days, subscription_retry_count
-- ----------------------------
DROP TABLE IF EXISTS `settings`;
CREATE TABLE `settings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `key` varchar(100) NOT NULL,
  `value` text DEFAULT NULL,
  `type` enum('string','number','boolean','json') NOT NULL DEFAULT 'string',
  `description` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `key` (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of settings
-- ----------------------------
INSERT INTO `settings` (`key`, `value`, `type`, `description`) VALUES
-- General
('gym_name', 'Moolai Gym', 'string', 'Nama gym'),
('gym_address', 'Jl. Contoh No. 123, Jakarta', 'string', 'Alamat gym'),
('gym_phone', '021-1234567', 'string', 'Nomor telepon gym'),
('gym_email', 'info@moolaigym.com', 'string', 'Email gym'),
-- Tax
('tax_enabled', 'true', 'boolean', 'Aktifkan pajak'),
('tax_name', 'PPN', 'string', 'Nama pajak'),
('tax_percentage', '11', 'number', 'Persentase pajak'),
-- Service charge
('service_charge_enabled', 'false', 'boolean', 'Aktifkan service charge'),
('service_charge_percentage', '5', 'number', 'Persentase service charge'),
-- Check-in
('checkin_cooldown_minutes', '60', 'number', 'Jeda minimal antar check-in (menit)'),
-- Booking
('class_booking_advance_days', '7', 'number', 'Booking kelas maksimal H-berapa'),
('class_cancel_hours', '2', 'number', 'Minimal jam sebelum kelas untuk cancel'),
('pt_booking_advance_days', '14', 'number', 'Booking PT maksimal H-berapa'),
('pt_cancel_hours', '24', 'number', 'Minimal jam sebelum PT untuk cancel'),
-- Subscription
('subscription_retry_days', '3', 'number', 'Berapa hari retry jika pembayaran gagal'),
('subscription_retry_count', '3', 'number', 'Berapa kali retry pembayaran');

-- ============================================================================
-- NOTIFICATIONS
-- ============================================================================

-- ----------------------------
-- Table: notifications
-- ----------------------------
-- FUNGSI: Menyimpan notifikasi untuk user (in-app notifications)
-- RELASI:
--   - MANY-TO-ONE ke users (user_id) - penerima notifikasi
-- NOTIFICATION TYPES:
--   - info: Informasi umum
--   - success: Konfirmasi sukses
--   - warning: Peringatan
--   - error: Error/masalah
--   - promo: Promo baru
--   - reminder: Pengingat (kelas, PT, membership expiring)
--   - billing: Terkait pembayaran/subscription
-- FITUR:
--   - data: JSON untuk action link, deep link, dll
--   - is_read: Apakah sudah dibaca
--   - Bisa digunakan untuk push notification dengan integrasi FCM/APNS
-- ----------------------------
DROP TABLE IF EXISTS `notifications`;
CREATE TABLE `notifications` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `branch_id` int(11) DEFAULT NULL COMMENT 'Cabang terkait notifikasi',
  `user_id` int(11) NOT NULL,
  `type` enum('info','success','warning','error','promo','reminder','billing') NOT NULL DEFAULT 'info',
  `title` varchar(100) NOT NULL,
  `message` text NOT NULL,
  `data` json DEFAULT NULL COMMENT 'Additional data (link, action, dll)',
  `is_read` tinyint(1) DEFAULT 0,
  `read_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_notification_branch` (`branch_id`),
  KEY `idx_notification_user` (`user_id`, `is_read`),
  CONSTRAINT `notifications_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`) ON DELETE SET NULL,
  CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================================
-- SAMPLE DATA - SKENARIO PENGGUNAAN LENGKAP
-- ============================================================================

/*
================================================================================
                        SKENARIO DATA CONTOH
================================================================================

Berikut adalah data contoh yang menggambarkan penggunaan aplikasi gym secara
lengkap dengan skenario yang saling terkait:

SKENARIO 1: Member Baru (Budi Santoso)
- Registrasi sebagai member baru
- Beli membership Premium Monthly
- Check-in ke gym beberapa kali
- Booking kelas Yoga
- Beli protein shake di kasir

SKENARIO 2: Member VIP dengan PT (Siti Rahayu)
- Member VIP dengan Personal Training
- Beli PT 10 Sessions dengan Trainer Eko
- Booking 3 session PT
- Auto-renew membership via subscription

SKENARIO 3: Member dengan Class Pass (Andi Wijaya)
- Member basic tanpa include_classes
- Beli 10 Class Pass
- Booking multiple classes
- Menggunakan voucher diskon

================================================================================
*/

-- ----------------------------
-- Tambahan Users (Members)
-- ----------------------------
INSERT INTO `users` (`id`, `name`, `email`, `password`, `pin`, `has_pin`, `phone`, `date_of_birth`, `gender`, `address`, `role_id`, `is_active`) VALUES
-- Member Budi - Skenario 1
(6, 'Budi Santoso', 'budi.santoso@email.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567001', '1990-05-15', 'male', 'Jl. Merdeka No. 45, Jakarta Selatan', 3, 1),
-- Member Siti - Skenario 2 (VIP dengan PT)
(7, 'Siti Rahayu', 'siti.rahayu@email.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567002', '1988-08-22', 'female', 'Jl. Sudirman No. 100, Jakarta Pusat', 3, 1),
-- Member Andi - Skenario 3 (Class Pass)
(8, 'Andi Wijaya', 'andi.wijaya@email.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567003', '1995-03-10', 'male', 'Jl. Gatot Subroto No. 50, Jakarta Selatan', 3, 1),
-- Member Expired (untuk testing)
(9, 'Dewi Lestari', 'dewi.lestari@email.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567004', '1992-12-01', 'female', 'Jl. Ahmad Yani No. 75, Jakarta Timur', 3, 1),
-- Member Frozen (untuk testing)
(10, 'Rudi Hermawan', 'rudi.hermawan@email.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567005', '1985-07-20', 'male', 'Jl. Thamrin No. 30, Jakarta Pusat', 3, 1),
-- Trainer tambahan
(11, 'Coach Maya', 'maya.trainer@moolaigym.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567006', '1991-04-18', 'female', 'Jl. Kemang Raya No. 10, Jakarta Selatan', 4, 1);

-- ----------------------------
-- Tambahan Trainer
-- ----------------------------
INSERT INTO `trainers` (`id`, `user_id`, `specialization`, `bio`, `certifications`, `experience_years`, `commission_percentage`) VALUES
(2, 11, 'Yoga & Pilates', 'Certified yoga instructor dengan 4 tahun pengalaman', '["RYT-200 Yoga Alliance", "Pilates Mat Certified"]', 4, 25.00);

-- ----------------------------
-- Update class_schedules dengan trainer_id yang benar
-- ----------------------------
UPDATE `class_schedules` SET `trainer_id` = 1 WHERE `trainer_id` = 1;

-- Tambah jadwal dengan trainer Maya
INSERT INTO `class_schedules` (`branch_id`, `class_type_id`, `trainer_id`, `day_of_week`, `start_time`, `end_time`, `capacity`, `room`) VALUES
(1, 1, 2, 5, '07:00:00', '08:00:00', 20, 'Studio A'),  -- Yoga Friday with Maya @JKT
(1, 4, 2, 2, '09:00:00', '10:00:00', 15, 'Studio A'),  -- Pilates Tuesday with Maya @JKT
(1, 4, 2, 4, '09:00:00', '10:00:00', 15, 'Studio A');  -- Pilates Thursday with Maya @JKT

-- ============================================================================
-- SKENARIO 1: Member Budi Santoso - Premium Monthly
-- ============================================================================

-- Transaksi pembelian membership Premium Monthly
INSERT INTO `transactions` (`id`, `branch_id`, `transaction_code`, `user_id`, `staff_id`, `subtotal`, `subtotal_after_discount`, `tax_percentage`, `tax_amount`, `grand_total`, `payment_method`, `payment_status`, `paid_amount`, `change_amount`, `paid_at`, `created_at`) VALUES
(1, 1, 'TRX-20260115-0001', 6, 3, 500000.00, 500000.00, 11, 55000.00, 555000.00, 'qris', 'paid', 555000.00, 0, '2026-01-15 10:30:00', '2026-01-15 10:30:00');

INSERT INTO `transaction_items` (`transaction_id`, `item_type`, `item_id`, `item_name`, `quantity`, `unit_price`, `subtotal`, `created_at`) VALUES
(1, 'membership', 4, 'Premium Monthly', 1, 500000.00, 500000.00, '2026-01-15 10:30:00');

-- Membership aktif Budi
INSERT INTO `member_memberships` (`id`, `user_id`, `package_id`, `transaction_id`, `membership_code`, `start_date`, `end_date`, `class_remaining`, `status`, `auto_renew`, `created_at`) VALUES
(1, 6, 4, 1, 'MBR-20260115-BUD001', '2026-01-15', '2026-02-14', NULL, 'active', 0, '2026-01-15 10:30:00');

-- Check-in records Budi (beberapa kali dalam seminggu)
-- checkin_type='gym' karena punya Premium Monthly membership (akses penuh)
INSERT INTO `member_checkins` (`branch_id`, `user_id`, `checkin_type`, `membership_id`, `class_pass_id`, `checkin_time`, `checkout_time`, `checkin_method`, `created_at`) VALUES
(1, 6, 'gym', 1, NULL, '2026-01-15 17:00:00', '2026-01-15 18:30:00', 'qr_code', '2026-01-15 17:00:00'),
(1, 6, 'gym', 1, NULL, '2026-01-17 06:30:00', '2026-01-17 08:00:00', 'qr_code', '2026-01-17 06:30:00'),
(1, 6, 'gym', 1, NULL, '2026-01-19 18:00:00', '2026-01-19 19:45:00', 'qr_code', '2026-01-19 18:00:00'),
(1, 6, 'gym', 1, NULL, '2026-01-21 07:00:00', '2026-01-21 08:30:00', 'qr_code', '2026-01-21 07:00:00'),
(1, 6, 'gym', 1, NULL, '2026-01-23 17:30:00', '2026-01-23 19:00:00', 'qr_code', '2026-01-23 17:30:00'),
(1, 6, 'gym', 1, NULL, '2026-01-25 09:00:00', '2026-01-25 10:30:00', 'qr_code', '2026-01-25 09:00:00'),
(1, 6, 'gym', 1, NULL, '2026-01-27 18:00:00', NULL, 'qr_code', '2026-01-27 18:00:00');  -- Masih di gym

-- Booking kelas Budi (Premium Monthly: include_classes=1, membership_id=1)
-- access_type='membership' karena pakai benefit dari membership Premium
INSERT INTO `class_bookings` (`branch_id`, `user_id`, `schedule_id`, `class_date`, `access_type`, `membership_id`, `class_pass_id`, `status`, `booked_at`, `attended_at`, `notes`, `created_at`) VALUES
(1, 6, 1, '2026-01-20', 'membership', 1, NULL, 'attended', '2026-01-18 20:00:00', '2026-01-20 07:00:00', 'Premium Member - FREE class', '2026-01-18 20:00:00'),
(1, 6, 3, '2026-01-22', 'membership', 1, NULL, 'booked', '2026-01-20 19:00:00', NULL, 'Premium Member - FREE class', '2026-01-20 19:00:00'),
(1, 6, 1, '2026-01-27', 'membership', 1, NULL, 'booked', '2026-01-25 21:00:00', NULL, 'Premium Member - FREE class', '2026-01-25 21:00:00');

-- Transaksi beli produk (Protein Shake + Energy Bar)
INSERT INTO `transactions` (`id`, `branch_id`, `transaction_code`, `user_id`, `staff_id`, `subtotal`, `subtotal_after_discount`, `tax_percentage`, `tax_amount`, `grand_total`, `payment_method`, `payment_status`, `paid_amount`, `change_amount`, `paid_at`, `created_at`) VALUES
(2, 1, 'TRX-20260121-0002', 6, 3, 60000.00, 60000.00, 11, 6600.00, 66600.00, 'cash', 'paid', 70000.00, 3400.00, '2026-01-21 08:15:00', '2026-01-21 08:15:00');

INSERT INTO `transaction_items` (`transaction_id`, `item_type`, `item_id`, `item_name`, `quantity`, `unit_price`, `subtotal`, `created_at`) VALUES
(2, 'product', 3, 'Protein Shake', 1, 35000.00, 35000.00, '2026-01-21 08:15:00'),
(2, 'product', 5, 'Energy Bar', 1, 25000.00, 25000.00, '2026-01-21 08:15:00');

-- Update stock produk setelah penjualan (21 Jan 2026 - setelah pembelian Siti 5 Jan)
INSERT INTO `product_stock_logs` (`branch_id`, `product_id`, `type`, `quantity`, `stock_before`, `stock_after`, `reference_type`, `reference_id`, `notes`, `created_by`, `created_at`) VALUES
(1, 3, 'out', 1, 50, 49, 'transaction', 2, 'Penjualan ke Budi Santoso', 3, '2026-01-21 08:15:00'),
(1, 5, 'out', 1, 39, 38, 'transaction', 2, 'Penjualan ke Budi Santoso', 3, '2026-01-21 08:15:00');

UPDATE `products` SET `stock` = 49 WHERE `id` = 3;
UPDATE `products` SET `stock` = 38 WHERE `id` = 5;

-- ============================================================================
-- SKENARIO 2: Member Siti Rahayu - VIP dengan Personal Training
-- ============================================================================

-- ===== SEBELUM JADI MEMBER: Visit sekali dengan Daily Pass (25 Desember 2025) =====
-- Transaksi pembelian Daily Pass (sebelum jadi member VIP)
INSERT INTO `transactions` (`id`, `branch_id`, `transaction_code`, `user_id`, `staff_id`, `subtotal`, `subtotal_after_discount`, `tax_percentage`, `tax_amount`, `grand_total`, `payment_method`, `payment_status`, `paid_amount`, `paid_at`, `created_at`) VALUES
(8, 1, 'TRX-20251225-0008', 7, 3, 50000.00, 50000.00, 11, 5500.00, 55500.00, 'cash', 'paid', 60000.00, '2025-12-25 09:00:00', '2025-12-25 09:00:00');

INSERT INTO `transaction_items` (`transaction_id`, `item_type`, `item_id`, `item_name`, `quantity`, `unit_price`, `subtotal`, `created_at`) VALUES
(8, 'membership', 1, 'Daily Pass', 1, 50000.00, 50000.00, '2025-12-25 09:00:00');

-- Membership Daily Pass Siti (sudah expired)
INSERT INTO `member_memberships` (`id`, `user_id`, `package_id`, `transaction_id`, `membership_code`, `start_date`, `end_date`, `status`, `auto_renew`, `created_at`) VALUES
(6, 7, 1, 8, 'MBR-20251225-SIT000', '2025-12-25', '2025-12-25', 'expired', 0, '2025-12-25 09:00:00');

-- Check-in saat Daily Pass (pertama kali ke gym)
-- checkin_type='gym' karena Daily Pass adalah membership (walaupun 1 hari)
INSERT INTO `member_checkins` (`branch_id`, `user_id`, `checkin_type`, `membership_id`, `class_pass_id`, `checkin_time`, `checkout_time`, `checkin_method`, `notes`, `created_at`) VALUES
(1, 7, 'gym', 6, NULL, '2025-12-25 09:30:00', '2025-12-25 11:00:00', 'manual', 'First visit - trial Daily Pass', '2025-12-25 09:30:00');

-- ===== SEKARANG JADI MEMBER VIP (1 Januari 2026) =====
-- Transaksi pembelian VIP Monthly
INSERT INTO `transactions` (`id`, `branch_id`, `transaction_code`, `user_id`, `staff_id`, `subtotal`, `subtotal_after_discount`, `tax_percentage`, `tax_amount`, `grand_total`, `payment_method`, `payment_status`, `paid_amount`, `paid_at`, `created_at`) VALUES
(3, 1, 'TRX-20260101-0003', 7, 2, 1000000.00, 1000000.00, 11, 110000.00, 1110000.00, 'transfer', 'paid', 1110000.00, '2026-01-01 14:00:00', '2026-01-01 14:00:00');

INSERT INTO `transaction_items` (`transaction_id`, `item_type`, `item_id`, `item_name`, `quantity`, `unit_price`, `subtotal`, `created_at`) VALUES
(3, 'membership', 5, 'VIP Monthly', 1, 1000000.00, 1000000.00, '2026-01-01 14:00:00');

-- Membership VIP Siti
INSERT INTO `member_memberships` (`id`, `user_id`, `package_id`, `transaction_id`, `membership_code`, `start_date`, `end_date`, `class_remaining`, `status`, `auto_renew`, `created_at`) VALUES
(2, 7, 5, 3, 'MBR-20260101-SIT001', '2026-01-01', '2026-01-31', NULL, 'active', 1, '2026-01-01 14:00:00');

-- Transaksi pembelian PT 10 Sessions
INSERT INTO `transactions` (`id`, `branch_id`, `transaction_code`, `user_id`, `staff_id`, `subtotal`, `subtotal_after_discount`, `tax_percentage`, `tax_amount`, `grand_total`, `payment_method`, `payment_status`, `paid_amount`, `paid_at`, `created_at`) VALUES
(4, 1, 'TRX-20260102-0004', 7, 2, 2000000.00, 2000000.00, 11, 220000.00, 2220000.00, 'card', 'paid', 2220000.00, '2026-01-02 15:00:00', '2026-01-02 15:00:00');

INSERT INTO `transaction_items` (`transaction_id`, `item_type`, `item_id`, `item_name`, `quantity`, `unit_price`, `subtotal`, `metadata`, `created_at`) VALUES
(4, 'pt_package', 3, 'PT 10 Sessions', 1, 2000000.00, 2000000.00, '{"trainer_id": 1, "trainer_name": "Coach Eko"}', '2026-01-02 15:00:00');

-- PT Sessions Siti dengan Trainer Eko
INSERT INTO `member_pt_sessions` (`id`, `user_id`, `pt_package_id`, `transaction_id`, `trainer_id`, `total_sessions`, `used_sessions`, `start_date`, `expire_date`, `status`, `created_at`) VALUES
(1, 7, 3, 4, 1, 10, 3, '2026-01-02', '2026-04-02', 'active', '2026-01-02 15:00:00');

-- PT Bookings (3 session sudah selesai)
INSERT INTO `pt_bookings` (`branch_id`, `member_pt_session_id`, `user_id`, `trainer_id`, `booking_date`, `start_time`, `end_time`, `status`, `notes`, `completed_at`, `completed_by`, `created_at`) VALUES
(1, 1, 7, 1, '2026-01-05', '10:00:00', '11:00:00', 'completed', 'Session 1: Fitness assessment & goal setting', '2026-01-05 11:00:00', 5, '2026-01-03 14:00:00'),
(1, 1, 7, 1, '2026-01-12', '10:00:00', '11:00:00', 'completed', 'Session 2: Upper body workout', '2026-01-12 11:00:00', 5, '2026-01-08 10:00:00'),
(1, 1, 7, 1, '2026-01-19', '10:00:00', '11:00:00', 'completed', 'Session 3: Lower body & core workout', '2026-01-19 11:00:00', 5, '2026-01-15 09:00:00'),
(1, 1, 7, 1, '2026-01-26', '10:00:00', '11:00:00', 'booked', 'Session 4: Cardio & HIIT', NULL, NULL, '2026-01-22 16:00:00'),
(1, 1, 7, 1, '2026-02-02', '10:00:00', '11:00:00', 'booked', 'Session 5: Full body workout', NULL, NULL, '2026-01-22 16:00:00');

-- Check-in records Siti (VIP member - akses penuh gym + semua fasilitas)
INSERT INTO `member_checkins` (`branch_id`, `user_id`, `checkin_type`, `membership_id`, `class_pass_id`, `checkin_time`, `checkout_time`, `checkin_method`, `created_at`) VALUES
(1, 7, 'gym', 2, NULL, '2026-01-05 09:30:00', '2026-01-05 11:30:00', 'qr_code', '2026-01-05 09:30:00'),  -- PT Day + beli produk
(1, 7, 'gym', 2, NULL, '2026-01-06 06:30:00', '2026-01-06 08:00:00', 'qr_code', '2026-01-06 06:30:00'),  -- Yoga class
(1, 7, 'gym', 2, NULL, '2026-01-08 07:00:00', '2026-01-08 08:30:00', 'qr_code', '2026-01-08 07:00:00'),  -- Regular gym
(1, 7, 'gym', 2, NULL, '2026-01-12 09:30:00', '2026-01-12 11:30:00', 'qr_code', '2026-01-12 09:30:00'),  -- PT Day
(1, 7, 'gym', 2, NULL, '2026-01-15 18:00:00', '2026-01-15 19:30:00', 'qr_code', '2026-01-15 18:00:00'),  -- Evening workout
(1, 7, 'gym', 2, NULL, '2026-01-19 09:30:00', '2026-01-19 12:00:00', 'qr_code', '2026-01-19 09:30:00'),  -- PT Day + Swim
(1, 7, 'gym', 2, NULL, '2026-01-22 17:00:00', '2026-01-22 19:00:00', 'qr_code', '2026-01-22 17:00:00'),  -- Evening workout
(1, 7, 'gym', 2, NULL, '2026-01-25 08:30:00', '2026-01-25 10:30:00', 'qr_code', '2026-01-25 08:30:00'),  -- Zumba class + teman Diana
(1, 7, 'gym', 2, NULL, '2026-01-26 09:00:00', NULL, 'qr_code', '2026-01-26 09:00:00');  -- Masih di gym (PT Day)

-- Payment method tersimpan untuk subscription
INSERT INTO `payment_methods` (`id`, `user_id`, `type`, `provider`, `masked_number`, `holder_name`, `token`, `is_default`, `expires_at`, `created_at`) VALUES
(1, 7, 'card', 'visa', '**** **** **** 4242', 'SITI RAHAYU', 'tok_visa_siti_001', 1, '2028-12-31', '2026-01-02 15:00:00');

-- Subscription auto-renew membership
INSERT INTO `subscriptions` (`id`, `subscription_code`, `user_id`, `item_type`, `item_id`, `item_name`, `base_price`, `recurring_price`, `billing_cycle`, `billing_day`, `next_billing_date`, `payment_method_id`, `status`, `started_at`, `created_at`) VALUES
(1, 'SUB-20260101-0001', 7, 'membership', 5, 'VIP Monthly', 1000000.00, 1110000.00, 'monthly', 1, '2026-02-01', 1, 'active', '2026-01-01 14:00:00', '2026-01-01 14:00:00');

-- ===== PEMBELIAN PRODUK: Mineral Water + Energy Bar (setelah PT session) =====
INSERT INTO `transactions` (`id`, `branch_id`, `transaction_code`, `user_id`, `staff_id`, `subtotal`, `subtotal_after_discount`, `tax_percentage`, `tax_amount`, `grand_total`, `payment_method`, `payment_status`, `paid_amount`, `change_amount`, `paid_at`, `created_at`) VALUES
(9, 1, 'TRX-20260105-0009', 7, 3, 33000.00, 33000.00, 11, 3630.00, 36630.00, 'cash', 'paid', 40000.00, 3370.00, '2026-01-05 11:15:00', '2026-01-05 11:15:00');

INSERT INTO `transaction_items` (`transaction_id`, `item_type`, `item_id`, `item_name`, `quantity`, `unit_price`, `subtotal`, `created_at`) VALUES
(9, 'product', 4, 'Mineral Water 600ml', 1, 8000.00, 8000.00, '2026-01-05 11:15:00'),
(9, 'product', 5, 'Energy Bar', 1, 25000.00, 25000.00, '2026-01-05 11:15:00');

-- Update stock produk (5 Jan 2026 - sebelum transaksi lain)
INSERT INTO `product_stock_logs` (`branch_id`, `product_id`, `type`, `quantity`, `stock_before`, `stock_after`, `reference_type`, `reference_id`, `notes`, `created_by`, `created_at`) VALUES
(1, 4, 'out', 1, 100, 99, 'transaction', 9, 'Penjualan ke Siti Rahayu', 3, '2026-01-05 11:15:00'),
(1, 5, 'out', 1, 40, 39, 'transaction', 9, 'Penjualan ke Siti Rahayu', 3, '2026-01-05 11:15:00');

-- ===== PEMBELIAN SINGLE CLASS: Zumba (ajak teman yang non-member) =====
-- Siti beli Single Class untuk temannya yang belum member
INSERT INTO `transactions` (`id`, `branch_id`, `transaction_code`, `user_id`, `staff_id`, `subtotal`, `subtotal_after_discount`, `tax_percentage`, `tax_amount`, `grand_total`, `payment_method`, `payment_status`, `paid_amount`, `paid_at`, `notes`, `created_at`) VALUES
(10, 1, 'TRX-20260118-0010', 7, 3, 50000.00, 50000.00, 11, 5500.00, 55500.00, 'qris', 'paid', 55500.00, '2026-01-18 10:00:00', 'Single Class untuk teman (non-member)', '2026-01-18 10:00:00');

INSERT INTO `transaction_items` (`transaction_id`, `item_type`, `item_id`, `item_name`, `quantity`, `unit_price`, `subtotal`, `metadata`, `created_at`) VALUES
(10, 'class_pass', 1, 'Single Class', 1, 50000.00, 50000.00, '{"class_type": "Zumba", "class_date": "2026-01-25", "for_guest": true, "guest_name": "Diana (teman Siti)"}', '2026-01-18 10:00:00');

-- Class Pass Single Class untuk teman Siti
INSERT INTO `member_class_passes` (`id`, `user_id`, `class_package_id`, `transaction_id`, `total_classes`, `used_classes`, `start_date`, `expire_date`, `status`, `created_at`) VALUES
(2, 7, 1, 10, 1, 1, '2026-01-18', '2026-01-25', 'completed', '2026-01-18 10:00:00');

-- ===== SITI IKUT KELAS (benefit VIP: include_classes=1, class_quota=NULL = UNLIMITED) =====
-- Siti adalah VIP Member (membership_id=2) yang punya akses GRATIS ke SEMUA kelas tanpa batas
-- access_type='membership' dengan membership_id=2 (VIP Monthly)
-- Tapi untuk teman Diana yang non-member, Siti belikan Single Class (class_pass_id=2)
INSERT INTO `class_bookings` (`branch_id`, `user_id`, `schedule_id`, `class_date`, `access_type`, `membership_id`, `class_pass_id`, `status`, `booked_at`, `attended_at`, `notes`, `created_at`) VALUES
-- Siti ikut Yoga (6 Jan) - GRATIS karena VIP include_classes=1
(1, 7, 1, '2026-01-06', 'membership', 2, NULL, 'attended', '2026-01-04 20:00:00', '2026-01-06 07:00:00', 'VIP Member - FREE class', '2026-01-04 20:00:00'),
-- Siti ikut Zumba (25 Jan) - GRATIS karena VIP
(1, 7, 5, '2026-01-25', 'membership', 2, NULL, 'attended', '2026-01-18 10:30:00', '2026-01-25 09:00:00', 'VIP Member - FREE class, bareng teman Diana', '2026-01-18 10:30:00'),
-- Siti booking Pilates (upcoming) - GRATIS karena VIP
(1, 7, 7, '2026-01-28', 'membership', 2, NULL, 'booked', '2026-01-26 19:00:00', NULL, 'VIP Member - FREE class', '2026-01-26 19:00:00');

-- Note: Teman Diana (non-member) ikut kelas Zumba pakai Single Class yang DIBELI oleh Siti
-- Booking untuk Diana menggunakan class_pass_id=2 (Single Class)
-- Diana bukan user terdaftar, jadi dicatat di metadata transaction_items saja

-- ============================================================================
-- SKENARIO 3: Member Andi Wijaya - Class Pass
-- ============================================================================

-- Transaksi pembelian Basic Monthly
INSERT INTO `transactions` (`id`, `branch_id`, `transaction_code`, `user_id`, `staff_id`, `subtotal`, `subtotal_after_discount`, `tax_percentage`, `tax_amount`, `grand_total`, `payment_method`, `payment_status`, `paid_amount`, `paid_at`, `created_at`) VALUES
(5, 1, 'TRX-20260110-0005', 8, 3, 300000.00, 300000.00, 11, 33000.00, 333000.00, 'ewallet', 'paid', 333000.00, '2026-01-10 11:00:00', '2026-01-10 11:00:00');

INSERT INTO `transaction_items` (`transaction_id`, `item_type`, `item_id`, `item_name`, `quantity`, `unit_price`, `subtotal`, `created_at`) VALUES
(5, 'membership', 3, 'Basic Monthly', 1, 300000.00, 300000.00, '2026-01-10 11:00:00');

-- Membership Basic Andi (tanpa include_classes)
INSERT INTO `member_memberships` (`id`, `user_id`, `package_id`, `transaction_id`, `membership_code`, `start_date`, `end_date`, `class_remaining`, `status`, `auto_renew`, `created_at`) VALUES
(3, 8, 3, 5, 'MBR-20260110-AND001', '2026-01-10', '2026-02-09', NULL, 'active', 0, '2026-01-10 11:00:00');

-- ═══════════════════════ PROMOS ═══════════════════════

-- 1. Diskon 20% untuk Class Pass (sudah berjalan, Januari)
-- 2. Diskon 15% membership untuk member baru
-- 3. Diskon 10% semua produk (suplemen, minuman, dll)
-- 4. Gratis 1 sesi PT untuk pembelian paket PT 10 sesi
-- 5. Promo Valentine - diskon 25% semua layanan
-- 6. Promo Ramadhan - diskon 30% membership (akan datang)
-- 7. Promo expired (sudah lewat) untuk testing

INSERT INTO `promos` (`id`, `name`, `description`, `promo_type`, `discount_value`, `min_purchase`, `max_discount`, `applicable_to`, `start_date`, `end_date`, `usage_limit`, `usage_count`, `per_user_limit`, `is_active`, `created_at`) VALUES
(1, 'Class Pass Promo', 'Diskon 20% untuk pembelian Class Pass', 'percentage', 20, 100000, 100000, 'class', '2026-01-01 00:00:00', '2026-01-31 23:59:59', 100, 1, 1, 1, '2026-01-01 00:00:00'),
(2, 'Welcome New Member', 'Diskon 15% untuk member baru yang membeli membership pertama', 'percentage', 15, 200000, 150000, 'membership', '2026-01-01 00:00:00', '2026-06-30 23:59:59', 200, 0, 1, 1, '2026-01-01 00:00:00'),
(3, 'Promo Suplemen & Produk', 'Diskon 10% untuk semua produk di shop', 'percentage', 10, 50000, 50000, 'product', '2026-02-01 00:00:00', '2026-02-28 23:59:59', 150, 0, 2, 1, '2026-02-01 00:00:00'),
(4, 'PT Bundling Bonus', 'Potongan Rp 500.000 untuk pembelian paket PT 10 sesi atau lebih', 'fixed', 500000, 2000000, NULL, 'pt', '2026-02-01 00:00:00', '2026-03-31 23:59:59', 50, 0, 1, 1, '2026-02-01 00:00:00'),
(5, 'Valentine Fit Deal', 'Diskon 25% untuk semua layanan di Moolai Gym, spesial Valentine!', 'percentage', 25, 100000, 250000, 'all', '2026-02-10 00:00:00', '2026-02-16 23:59:59', 300, 0, 1, 1, '2026-02-10 00:00:00'),
(6, 'Promo Ramadhan', 'Diskon 30% membership selama bulan Ramadhan', 'percentage', 30, 200000, 300000, 'membership', '2026-03-01 00:00:00', '2026-03-31 23:59:59', 500, 0, 1, 1, '2026-02-01 00:00:00'),
(7, 'Promo Tahun Baru', 'Diskon 20% semua layanan untuk tahun baru', 'percentage', 20, 100000, 200000, 'all', '2025-12-25 00:00:00', '2025-12-31 23:59:59', 100, 45, 1, 0, '2025-12-20 00:00:00');

-- ═══════════════════════ VOUCHERS ═══════════════════════

INSERT INTO `vouchers` (`id`, `code`, `voucher_type`, `discount_value`, `min_purchase`, `max_discount`, `applicable_to`, `start_date`, `end_date`, `usage_limit`, `usage_count`, `is_single_use`, `is_active`, `created_at`) VALUES
(1, 'CLASSFIT20', 'percentage', 20, 100000, 100000, 'class', '2026-01-01 00:00:00', '2026-01-31 23:59:59', 50, 1, 1, 1, '2026-01-01 00:00:00'),
(2, 'NEWMEMBER50K', 'fixed', 50000, 200000, NULL, 'all', '2026-01-01 00:00:00', '2026-12-31 23:59:59', 100, 0, 1, 1, '2026-01-01 00:00:00'),
(3, 'WELCOME15', 'percentage', 15, 200000, 150000, 'membership', '2026-01-01 00:00:00', '2026-06-30 23:59:59', 100, 0, 1, 1, '2026-01-01 00:00:00'),
(4, 'SUPLEMEN10', 'percentage', 10, 50000, 50000, 'product', '2026-02-01 00:00:00', '2026-02-28 23:59:59', 80, 0, 0, 1, '2026-02-01 00:00:00'),
(5, 'PTBONUS500K', 'fixed', 500000, 2000000, NULL, 'pt', '2026-02-01 00:00:00', '2026-03-31 23:59:59', 30, 0, 1, 1, '2026-02-01 00:00:00'),
(6, 'VALENTINE25', 'percentage', 25, 100000, 250000, 'all', '2026-02-10 00:00:00', '2026-02-16 23:59:59', 200, 0, 1, 1, '2026-02-10 00:00:00'),
(7, 'RAMADHAN30', 'percentage', 30, 200000, 300000, 'membership', '2026-03-01 00:00:00', '2026-03-31 23:59:59', 300, 0, 1, 1, '2026-02-01 00:00:00'),
(8, 'REFERRAL25K', 'fixed', 25000, 100000, NULL, 'all', '2026-01-01 00:00:00', '2026-12-31 23:59:59', 500, 0, 1, 1, '2026-01-01 00:00:00'),
(9, 'BIRTHDAY100K', 'fixed', 100000, 300000, NULL, 'all', '2026-01-01 00:00:00', '2026-12-31 23:59:59', 1000, 0, 1, 1, '2026-01-01 00:00:00'),
(10, 'FLASHSALE50', 'percentage', 50, 500000, 500000, 'membership', '2026-02-14 00:00:00', '2026-02-14 23:59:59', 10, 0, 1, 1, '2026-02-10 00:00:00');

-- Transaksi pembelian 10 Class Pass dengan voucher
INSERT INTO `transactions` (`id`, `branch_id`, `transaction_code`, `user_id`, `staff_id`, `subtotal`, `discount_type`, `discount_value`, `discount_amount`, `subtotal_after_discount`, `tax_percentage`, `tax_amount`, `grand_total`, `payment_method`, `payment_status`, `paid_amount`, `voucher_code`, `paid_at`, `created_at`) VALUES
(6, 1, 'TRX-20260112-0006', 8, 3, 350000.00, 'percentage', 20, 70000.00, 280000.00, 11, 30800.00, 310800.00, 'qris', 'paid', 310800.00, 'CLASSFIT20', '2026-01-12 14:00:00', '2026-01-12 14:00:00');

INSERT INTO `transaction_items` (`transaction_id`, `item_type`, `item_id`, `item_name`, `quantity`, `unit_price`, `discount_type`, `discount_value`, `discount_amount`, `subtotal`, `created_at`) VALUES
(6, 'class_pass', 3, '10 Class Pass', 1, 350000.00, 'percentage', 20, 70000.00, 280000.00, '2026-01-12 14:00:00');

-- Voucher usage record
INSERT INTO `voucher_usages` (`voucher_id`, `user_id`, `transaction_id`, `discount_amount`, `used_at`) VALUES
(1, 8, 6, 70000.00, '2026-01-12 14:00:00');

-- Update voucher usage count
UPDATE `vouchers` SET `usage_count` = 1 WHERE `id` = 1;
UPDATE `promos` SET `usage_count` = 1 WHERE `id` = 1;

-- Class Pass Andi
INSERT INTO `member_class_passes` (`id`, `user_id`, `class_package_id`, `transaction_id`, `total_classes`, `used_classes`, `start_date`, `expire_date`, `status`, `created_at`) VALUES
(1, 8, 3, 6, 10, 4, '2026-01-12', '2026-03-13', 'active', '2026-01-12 14:00:00');

-- Class Bookings Andi (4 sudah digunakan dari class_pass_id=1)
-- Andi punya Basic Monthly (include_classes=0), jadi harus pakai Class Pass
-- access_type='class_pass' dengan class_pass_id=1 (10 Class Pass)
INSERT INTO `class_bookings` (`branch_id`, `user_id`, `schedule_id`, `class_date`, `access_type`, `membership_id`, `class_pass_id`, `status`, `booked_at`, `attended_at`, `notes`, `created_at`) VALUES
-- Yoga sudah attend (2 kelas)
(1, 8, 1, '2026-01-13', 'class_pass', NULL, 1, 'attended', '2026-01-12 15:00:00', '2026-01-13 07:00:00', 'Class Pass 1/10', '2026-01-12 15:00:00'),
(1, 8, 2, '2026-01-20', 'class_pass', NULL, 1, 'attended', '2026-01-15 10:00:00', '2026-01-20 07:00:00', 'Class Pass 2/10', '2026-01-15 10:00:00'),
-- Spinning sudah attend (2 kelas)
(1, 8, 3, '2026-01-14', 'class_pass', NULL, 1, 'attended', '2026-01-12 16:00:00', '2026-01-14 18:00:00', 'Class Pass 3/10', '2026-01-12 16:00:00'),
(1, 8, 4, '2026-01-16', 'class_pass', NULL, 1, 'attended', '2026-01-14 19:00:00', '2026-01-16 18:00:00', 'Class Pass 4/10', '2026-01-14 19:00:00'),
-- Upcoming bookings (sisa 6 kelas)
(1, 8, 5, '2026-02-01', 'class_pass', NULL, 1, 'booked', '2026-01-26 20:00:00', NULL, 'Class Pass 5/10 - Zumba', '2026-01-26 20:00:00'),
(1, 8, 7, '2026-01-28', 'class_pass', NULL, 1, 'booked', '2026-01-26 21:00:00', NULL, 'Class Pass 6/10 - Pilates', '2026-01-26 21:00:00');

-- Check-in records Andi (Basic Monthly = akses gym, TAPI kelas pakai class pass)
-- Andi tetap checkin_type='gym' karena punya Basic Monthly membership
INSERT INTO `member_checkins` (`branch_id`, `user_id`, `checkin_type`, `membership_id`, `class_pass_id`, `checkin_time`, `checkout_time`, `checkin_method`, `created_at`) VALUES
(1, 8, 'gym', 3, NULL, '2026-01-13 06:30:00', '2026-01-13 08:30:00', 'qr_code', '2026-01-13 06:30:00'),  -- Yoga class day
(1, 8, 'gym', 3, NULL, '2026-01-14 17:30:00', '2026-01-14 19:30:00', 'qr_code', '2026-01-14 17:30:00'),  -- Spinning class day
(1, 8, 'gym', 3, NULL, '2026-01-16 17:30:00', '2026-01-16 19:30:00', 'qr_code', '2026-01-16 17:30:00'),  -- Spinning class day
(1, 8, 'gym', 3, NULL, '2026-01-18 18:00:00', '2026-01-18 19:30:00', 'qr_code', '2026-01-18 18:00:00'),
(1, 8, 'gym', 3, NULL, '2026-01-20 06:30:00', '2026-01-20 09:00:00', 'qr_code', '2026-01-20 06:30:00'),  -- Yoga class day
(1, 8, 'gym', 3, NULL, '2026-01-24 18:00:00', '2026-01-24 19:30:00', 'qr_code', '2026-01-24 18:00:00');

-- ============================================================================
-- SKENARIO 4: Member Expired (Dewi Lestari)
-- ============================================================================

-- Membership yang sudah expired
INSERT INTO `member_memberships` (`id`, `user_id`, `package_id`, `membership_code`, `start_date`, `end_date`, `status`, `auto_renew`, `created_at`) VALUES
(4, 9, 3, 'MBR-20251201-DEW001', '2025-12-01', '2025-12-31', 'expired', 0, '2025-12-01 10:00:00');

-- Check-in history sebelum expired
INSERT INTO `member_checkins` (`branch_id`, `user_id`, `checkin_type`, `membership_id`, `class_pass_id`, `checkin_time`, `checkout_time`, `checkin_method`, `created_at`) VALUES
(1, 9, 'gym', 4, NULL, '2025-12-05 18:00:00', '2025-12-05 19:30:00', 'qr_code', '2025-12-05 18:00:00'),
(1, 9, 'gym', 4, NULL, '2025-12-10 07:00:00', '2025-12-10 08:30:00', 'qr_code', '2025-12-10 07:00:00'),
(1, 9, 'gym', 4, NULL, '2025-12-15 18:00:00', '2025-12-15 19:30:00', 'qr_code', '2025-12-15 18:00:00'),
(1, 9, 'gym', 4, NULL, '2025-12-20 09:00:00', '2025-12-20 10:30:00', 'qr_code', '2025-12-20 09:00:00'),
(1, 9, 'gym', 4, NULL, '2025-12-28 17:00:00', '2025-12-28 18:30:00', 'qr_code', '2025-12-28 17:00:00');

-- ============================================================================
-- SKENARIO 5: Member Frozen (Rudi Hermawan)
-- ============================================================================

-- Membership yang di-freeze
INSERT INTO `member_memberships` (`id`, `user_id`, `package_id`, `membership_code`, `start_date`, `end_date`, `status`, `frozen_at`, `frozen_until`, `freeze_reason`, `auto_renew`, `created_at`) VALUES
(5, 10, 4, 'MBR-20260101-RUD001', '2026-01-01', '2026-01-31', 'frozen', '2026-01-20 10:00:00', '2026-02-03', 'Sakit / istirahat dokter', 0, '2026-01-01 12:00:00');

-- Check-in history sebelum freeze
INSERT INTO `member_checkins` (`branch_id`, `user_id`, `checkin_type`, `membership_id`, `class_pass_id`, `checkin_time`, `checkout_time`, `checkin_method`, `created_at`) VALUES
(1, 10, 'gym', 5, NULL, '2026-01-02 06:00:00', '2026-01-02 07:30:00', 'qr_code', '2026-01-02 06:00:00'),
(1, 10, 'gym', 5, NULL, '2026-01-05 06:00:00', '2026-01-05 07:30:00', 'qr_code', '2026-01-05 06:00:00'),
(1, 10, 'gym', 5, NULL, '2026-01-08 06:00:00', '2026-01-08 07:30:00', 'qr_code', '2026-01-08 06:00:00'),
(1, 10, 'gym', 5, NULL, '2026-01-12 06:00:00', '2026-01-12 07:30:00', 'qr_code', '2026-01-12 06:00:00'),
(1, 10, 'gym', 5, NULL, '2026-01-15 06:00:00', '2026-01-15 07:30:00', 'qr_code', '2026-01-15 06:00:00'),
(1, 10, 'gym', 5, NULL, '2026-01-18 06:00:00', '2026-01-18 07:00:00', 'qr_code', '2026-01-18 06:00:00');  -- Last before freeze

-- ============================================================================
-- SKENARIO 6: User yang HANYA beli Class Pass (tanpa membership gym)
-- ============================================================================
-- Contoh: Lisa Permata - hanya mau ikut kelas Yoga, tidak butuh akses gym
-- Dia beli 5 Class Pass khusus Yoga

-- Buat user Lisa
INSERT INTO `users` (`id`, `name`, `email`, `password`, `phone`, `role_id`, `is_active`, `token_version`, `created_at`) VALUES
(12, 'Lisa Permata', 'lisa.permata@email.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VQIy8wPQpwJrCi', '081355556666', 3, 1, 1, '2026-01-20 11:00:00');

-- Transaksi beli 5 Class Pass Yoga
INSERT INTO `transactions` (`id`, `branch_id`, `transaction_code`, `user_id`, `staff_id`, `subtotal`, `subtotal_after_discount`, `tax_percentage`, `tax_amount`, `grand_total`, `payment_method`, `payment_status`, `paid_amount`, `paid_at`, `notes`, `created_at`) VALUES
(11, 1, 'TRX-20260120-0011', 12, 3, 200000.00, 200000.00, 11, 22000.00, 222000.00, 'qris', 'paid', 222000.00, '2026-01-20 11:00:00', 'Class Pass only - no gym membership', '2026-01-20 11:00:00');

INSERT INTO `transaction_items` (`transaction_id`, `item_type`, `item_id`, `item_name`, `quantity`, `unit_price`, `subtotal`, `metadata`, `created_at`) VALUES
(11, 'class_pass', 2, '5 Class Pass', 1, 200000.00, 200000.00, '{"class_type": "all"}', '2026-01-20 11:00:00');

-- Class Pass Lisa (5 kelas, sudah pakai 2)
INSERT INTO `member_class_passes` (`id`, `user_id`, `class_package_id`, `transaction_id`, `total_classes`, `used_classes`, `start_date`, `expire_date`, `status`, `created_at`) VALUES
(3, 12, 2, 11, 5, 2, '2026-01-20', '2026-02-20', 'active', '2026-01-20 11:00:00');

-- Class Bookings Lisa (pakai class pass, TANPA membership)
INSERT INTO `class_bookings` (`branch_id`, `user_id`, `schedule_id`, `class_date`, `access_type`, `membership_id`, `class_pass_id`, `status`, `booked_at`, `attended_at`, `notes`, `created_at`) VALUES
-- Yoga sudah attend (2 kelas terpakai)
(1, 12, 1, '2026-01-20', 'class_pass', NULL, 3, 'attended', '2026-01-20 11:30:00', '2026-01-20 07:00:00', 'Class Pass 1/5 - no gym access', '2026-01-20 11:30:00'),
(1, 12, 2, '2026-01-22', 'class_pass', NULL, 3, 'attended', '2026-01-20 12:00:00', '2026-01-22 07:00:00', 'Class Pass 2/5 - no gym access', '2026-01-20 12:00:00'),
-- Upcoming
(1, 12, 1, '2026-01-27', 'class_pass', NULL, 3, 'booked', '2026-01-25 20:00:00', NULL, 'Class Pass 3/5 - Yoga Monday', '2026-01-25 20:00:00');

-- Check-in Lisa: HANYA untuk kelas (checkin_type='class_only')
-- Lisa tidak punya membership, jadi hanya bisa akses area kelas (studio)
INSERT INTO `member_checkins` (`branch_id`, `user_id`, `checkin_type`, `membership_id`, `class_pass_id`, `checkin_time`, `checkout_time`, `checkin_method`, `notes`, `created_at`) VALUES
(1, 12, 'class_only', NULL, 3, '2026-01-20 06:45:00', '2026-01-20 08:15:00', 'manual', 'Class only - Yoga', '2026-01-20 06:45:00'),
(1, 12, 'class_only', NULL, 3, '2026-01-22 06:45:00', '2026-01-22 08:15:00', 'manual', 'Class only - Yoga', '2026-01-22 06:45:00');

-- Notifikasi untuk Lisa
INSERT INTO `notifications` (`branch_id`, `user_id`, `type`, `title`, `message`, `data`, `is_read`, `created_at`) VALUES
(1, 12, 'success', 'Class Pass Dibeli', '5 Class Pass berhasil dibeli. Anda bisa ikut kelas tanpa membership gym!', '{"action": "view_class_pass", "class_pass_id": 3}', 1, '2026-01-20 11:00:00'),
(1, 12, 'info', 'Akses Terbatas', 'Reminder: Class Pass hanya memberikan akses ke area kelas. Upgrade ke membership untuk akses gym penuh!', '{"action": "view_packages"}', 0, '2026-01-21 09:00:00');

-- ============================================================================
-- SKENARIO 7: Walk-in Customer (tanpa membership, beli produk saja)
-- ============================================================================

-- Transaksi walk-in beli produk
INSERT INTO `transactions` (`id`, `branch_id`, `transaction_code`, `user_id`, `staff_id`, `customer_name`, `customer_phone`, `subtotal`, `subtotal_after_discount`, `tax_percentage`, `tax_amount`, `grand_total`, `payment_method`, `payment_status`, `paid_amount`, `change_amount`, `paid_at`, `created_at`) VALUES
(7, 1, 'TRX-20260127-0007', NULL, 3, 'John Doe', '081299998888', 43000.00, 43000.00, 11, 4730.00, 47730.00, 'cash', 'paid', 50000.00, 2270.00, '2026-01-27 15:00:00', '2026-01-27 15:00:00');

INSERT INTO `transaction_items` (`transaction_id`, `item_type`, `item_id`, `item_name`, `quantity`, `unit_price`, `subtotal`, `created_at`) VALUES
(7, 'product', 3, 'Protein Shake', 1, 35000.00, 35000.00, '2026-01-27 15:00:00'),
(7, 'product', 4, 'Mineral Water 600ml', 1, 8000.00, 8000.00, '2026-01-27 15:00:00');

-- Update stock (27 Jan 2026 - setelah pembelian Siti dan Budi)
INSERT INTO `product_stock_logs` (`branch_id`, `product_id`, `type`, `quantity`, `stock_before`, `stock_after`, `reference_type`, `reference_id`, `notes`, `created_by`, `created_at`) VALUES
(1, 3, 'out', 1, 49, 48, 'transaction', 7, 'Penjualan walk-in', 3, '2026-01-27 15:00:00'),
(1, 4, 'out', 1, 99, 98, 'transaction', 7, 'Penjualan walk-in', 3, '2026-01-27 15:00:00');

UPDATE `products` SET `stock` = 48 WHERE `id` = 3;
UPDATE `products` SET `stock` = 98 WHERE `id` = 4;

-- Walk-in customer 2: beli suplemen + air mineral
INSERT INTO `transactions` (`id`, `branch_id`, `transaction_code`, `user_id`, `staff_id`, `customer_name`, `customer_phone`, `subtotal`, `subtotal_after_discount`, `tax_percentage`, `tax_amount`, `grand_total`, `payment_method`, `payment_status`, `paid_amount`, `change_amount`, `paid_at`, `created_at`) VALUES
(12, 1, 'TRX-20260128-0012', NULL, 3, 'Walk-in Customer', NULL, 258000.00, 258000.00, 11, 28380.00, 286380.00, 'cash', 'paid', 300000.00, 13620.00, '2026-01-28 10:30:00', '2026-01-28 10:30:00');

INSERT INTO `transaction_items` (`transaction_id`, `item_type`, `item_id`, `item_name`, `quantity`, `unit_price`, `subtotal`, `created_at`) VALUES
(12, 'product', 1, 'Whey Protein 1kg', 1, 250000.00, 250000.00, '2026-01-28 10:30:00'),
(12, 'product', 4, 'Mineral Water 600ml', 1, 8000.00, 8000.00, '2026-01-28 10:30:00');

INSERT INTO `product_stock_logs` (`branch_id`, `product_id`, `type`, `quantity`, `stock_before`, `stock_after`, `reference_type`, `reference_id`, `notes`, `created_by`, `created_at`) VALUES
(1, 1, 'out', 1, 30, 29, 'transaction', 12, 'Penjualan walk-in', 3, '2026-01-28 10:30:00'),
(1, 4, 'out', 1, 98, 97, 'transaction', 12, 'Penjualan walk-in', 3, '2026-01-28 10:30:00');

-- Walk-in customer 3: beli snack dan minuman (QRIS)
INSERT INTO `transactions` (`id`, `branch_id`, `transaction_code`, `user_id`, `staff_id`, `customer_name`, `customer_phone`, `subtotal`, `subtotal_after_discount`, `tax_percentage`, `tax_amount`, `grand_total`, `payment_method`, `payment_status`, `paid_amount`, `paid_at`, `created_at`) VALUES
(13, 1, 'TRX-20260129-0013', NULL, 3, 'Walk-in Customer', '081377778888', 33000.00, 33000.00, 11, 3630.00, 36630.00, 'qris', 'paid', 36630.00, '2026-01-29 14:00:00', '2026-01-29 14:00:00');

INSERT INTO `transaction_items` (`transaction_id`, `item_type`, `item_id`, `item_name`, `quantity`, `unit_price`, `subtotal`, `created_at`) VALUES
(13, 'product', 5, 'Energy Bar', 1, 25000.00, 25000.00, '2026-01-29 14:00:00'),
(13, 'product', 4, 'Mineral Water 600ml', 1, 8000.00, 8000.00, '2026-01-29 14:00:00');

INSERT INTO `product_stock_logs` (`branch_id`, `product_id`, `type`, `quantity`, `stock_before`, `stock_after`, `reference_type`, `reference_id`, `notes`, `created_by`, `created_at`) VALUES
(1, 5, 'out', 1, 36, 35, 'transaction', 13, 'Penjualan walk-in', 3, '2026-01-29 14:00:00'),
(1, 4, 'out', 1, 97, 96, 'transaction', 13, 'Penjualan walk-in', 3, '2026-01-29 14:00:00');

-- ============================================================================
-- SKENARIO 7: Stock Adjustment & Restock
-- ============================================================================

-- Stock masuk (Purchase Order)
INSERT INTO `product_stock_logs` (`branch_id`, `product_id`, `type`, `quantity`, `stock_before`, `stock_after`, `reference_type`, `reference_id`, `notes`, `created_by`, `created_at`) VALUES
(1, 1, 'in', 10, 20, 30, 'purchase_order', NULL, 'Restock Whey Protein dari supplier', 2, '2026-01-20 09:00:00'),
(1, 2, 'in', 10, 15, 25, 'purchase_order', NULL, 'Restock BCAA dari supplier', 2, '2026-01-20 09:00:00'),
(1, 3, 'in', 50, 48, 98, 'purchase_order', NULL, 'Restock Protein Shake', 2, '2026-01-25 10:00:00');

UPDATE `products` SET `stock` = 30 WHERE `id` = 1;
UPDATE `products` SET `stock` = 25 WHERE `id` = 2;
UPDATE `products` SET `stock` = 98 WHERE `id` = 3;

-- Stock adjustment (expired/rusak) - 26 Jan 2026
-- Stock sebelumnya: 40 (awal) - 1 (Siti) - 1 (Budi) = 38
INSERT INTO `product_stock_logs` (`branch_id`, `product_id`, `type`, `quantity`, `stock_before`, `stock_after`, `reference_type`, `reference_id`, `notes`, `created_by`, `created_at`) VALUES
(1, 5, 'adjustment', -2, 38, 36, 'adjustment', NULL, 'Energy bar expired', 2, '2026-01-26 16:00:00');

UPDATE `products` SET `stock` = 36 WHERE `id` = 5;

-- ============================================================================
-- NOTIFICATIONS
-- ============================================================================

INSERT INTO `notifications` (`branch_id`, `user_id`, `type`, `title`, `message`, `data`, `is_read`, `created_at`) VALUES
-- Notifikasi untuk Budi
(1, 6, 'success', 'Selamat Bergabung!', 'Membership Premium Monthly Anda sudah aktif. Nikmati akses ke gym, pool, dan sauna!', '{"action": "view_membership", "membership_id": 1}', 1, '2026-01-15 10:30:00'),
(1, 6, 'reminder', 'Jangan Lupa Workout!', 'Sudah 2 hari Anda tidak ke gym. Yuk jaga konsistensi!', '{"action": "checkin"}', 0, '2026-01-23 09:00:00'),

-- Notifikasi untuk Siti
(1, 7, 'success', 'Selamat Datang!', 'Terima kasih sudah mencoba Daily Pass! Semoga pengalaman pertama Anda menyenangkan.', '{"action": "view_membership", "membership_id": 6}', 1, '2025-12-25 09:00:00'),
(1, 7, 'promo', 'Promo Khusus Untuk Anda', 'Upgrade ke VIP Membership dan dapatkan akses premium! Hubungi staff kami.', '{"action": "view_packages"}', 1, '2025-12-26 10:00:00'),
(1, 7, 'success', 'VIP Membership Aktif', 'Selamat! Anda sekarang member VIP. Nikmati semua fasilitas premium!', '{"action": "view_membership", "membership_id": 2}', 1, '2026-01-01 14:00:00'),
(1, 7, 'success', 'PT Package Dibeli', 'Paket PT 10 Sessions dengan Coach Eko sudah aktif. Jadwalkan sesi pertama Anda!', '{"action": "view_pt_session", "pt_session_id": 1}', 1, '2026-01-02 15:00:00'),
(1, 7, 'reminder', 'Kelas Yoga Besok', 'Reminder: Anda terdaftar di kelas Yoga besok jam 07:00. Selamat berlatih!', '{"action": "view_class_booking", "class_date": "2026-01-06"}', 1, '2026-01-05 18:00:00'),
(1, 7, 'success', 'Single Class Dibeli', 'Pembelian Single Class Zumba untuk teman berhasil! Ajak teman Anda ke kelas.', '{"action": "view_class_booking", "class_date": "2026-01-25"}', 1, '2026-01-18 10:00:00'),
(1, 7, 'reminder', 'Kelas Zumba Besok', 'Reminder: Kelas Zumba besok jam 09:00. Jangan lupa ajak teman Diana!', '{"action": "view_class_booking", "class_date": "2026-01-25"}', 1, '2026-01-24 18:00:00'),
(1, 7, 'info', 'PT Session Reminder', 'Jangan lupa! Besok Anda ada PT session jam 10:00 dengan Coach Eko', '{"action": "view_pt_booking", "booking_id": 4}', 0, '2026-01-25 18:00:00'),
(1, 7, 'reminder', 'Kelas Pilates', 'Reminder: Anda terdaftar di kelas Pilates tanggal 28 Jan jam 09:00', '{"action": "view_class_booking", "class_date": "2026-01-28"}', 0, '2026-01-27 18:00:00'),
(1, 7, 'billing', 'Tagihan Akan Datang', 'Subscription VIP Monthly Anda akan ditagihkan pada 1 Februari 2026', '{"action": "view_subscription", "subscription_id": 1}', 0, '2026-01-25 10:00:00'),

-- Notifikasi untuk Andi
(1, 8, 'success', 'Class Pass Dibeli', 'Paket 10 Class Pass berhasil dibeli. Selamat berlatih!', '{"action": "view_class_pass", "class_pass_id": 1}', 1, '2026-01-12 14:00:00'),
(1, 8, 'reminder', 'Kelas Besok', 'Reminder: Anda terdaftar di kelas Pilates besok jam 09:00', '{"action": "view_class_booking", "schedule_id": 7}', 0, '2026-01-27 18:00:00'),

-- Notifikasi untuk Dewi (expired member)
(1, 9, 'warning', 'Membership Expired', 'Membership Anda sudah expired pada 31 Desember 2025. Perpanjang sekarang!', '{"action": "renew_membership", "package_id": 3}', 0, '2026-01-01 00:00:00'),
(1, 9, 'promo', 'Promo Khusus Untuk Anda', 'Perpanjang membership sekarang dan dapatkan diskon 10%! Gunakan kode: COMEBACK10', '{"action": "view_promo", "voucher_code": "COMEBACK10"}', 0, '2026-01-15 10:00:00'),

-- Notifikasi untuk Rudi (frozen member)
(1, 10, 'info', 'Membership Dibekukan', 'Membership Anda dibekukan hingga 3 Februari 2026. Semoga lekas sembuh!', '{"action": "view_membership", "membership_id": 5}', 1, '2026-01-20 10:00:00'),
(1, 10, 'reminder', 'Membership Akan Aktif Kembali', 'Membership Anda akan aktif kembali pada 4 Februari 2026. Siap workout lagi?', '{"action": "view_membership", "membership_id": 5}', 0, '2026-01-31 09:00:00');

-- ============================================================================
-- AUDIT LOGS
-- ============================================================================

INSERT INTO `audit_logs` (`branch_id`, `table_name`, `record_id`, `action`, `user_id`, `old_data`, `new_data`, `ip_address`, `created_at`) VALUES
-- User creation
(1, 'users', 6, 'create', 2, NULL, '{"name": "Budi Santoso", "email": "budi.santoso@email.com", "role_id": 3}', '192.168.1.100', '2026-01-15 10:00:00'),
(1, 'users', 7, 'create', 2, NULL, '{"name": "Siti Rahayu", "email": "siti.rahayu@email.com", "role_id": 3}', '192.168.1.100', '2026-01-01 13:30:00'),
(1, 'users', 8, 'create', 2, NULL, '{"name": "Andi Wijaya", "email": "andi.wijaya@email.com", "role_id": 3}', '192.168.1.100', '2026-01-10 10:30:00'),

-- Membership freeze
(1, 'member_memberships', 5, 'update', 2, '{"status": "active"}', '{"status": "frozen", "freeze_reason": "Sakit / istirahat dokter"}', '192.168.1.100', '2026-01-20 10:00:00'),

-- PT Session completion
(1, 'pt_bookings', 1, 'update', 5, '{"status": "booked"}', '{"status": "completed", "completed_at": "2026-01-05 11:00:00"}', '192.168.1.101', '2026-01-05 11:00:00'),
(1, 'pt_bookings', 2, 'update', 5, '{"status": "booked"}', '{"status": "completed", "completed_at": "2026-01-12 11:00:00"}', '192.168.1.101', '2026-01-12 11:00:00'),
(1, 'pt_bookings', 3, 'update', 5, '{"status": "booked"}', '{"status": "completed", "completed_at": "2026-01-19 11:00:00"}', '192.168.1.101', '2026-01-19 11:00:00'),

-- Stock adjustments
(1, 'products', 5, 'update', 2, '{"stock": 38}', '{"stock": 36, "reason": "Energy bar expired"}', '192.168.1.100', '2026-01-26 16:00:00'),

-- Siti Rahayu journey: Daily Pass -> VIP Member
(1, 'member_memberships', 6, 'create', 3, NULL, '{"user_id": 7, "package_id": 1, "status": "active", "type": "Daily Pass trial"}', '192.168.1.102', '2025-12-25 09:00:00'),
(1, 'member_memberships', 2, 'create', 2, NULL, '{"user_id": 7, "package_id": 5, "status": "active", "type": "VIP Monthly"}', '192.168.1.100', '2026-01-01 14:00:00'),

-- Transactions
(1, 'transactions', 8, 'create', 3, NULL, '{"user_id": 7, "type": "Daily Pass", "total": 55500}', '192.168.1.102', '2025-12-25 09:00:00'),
(1, 'transactions', 9, 'create', 3, NULL, '{"user_id": 7, "type": "product_sale", "items": ["Mineral Water", "Energy Bar"], "total": 36630}', '192.168.1.102', '2026-01-05 11:15:00'),
(1, 'transactions', 10, 'create', 3, NULL, '{"user_id": 7, "type": "class_pass", "items": ["Single Class Zumba"], "total": 55500, "note": "untuk teman non-member"}', '192.168.1.102', '2026-01-18 10:00:00');

-- ----------------------------
-- Trainer Branch Assignments
-- ----------------------------
INSERT INTO `trainer_branches` (`trainer_id`, `branch_id`, `is_primary`) VALUES
(1, 1, 1),  -- Coach Eko -> Jakarta (primary)
(1, 2, 0),  -- Coach Eko -> Tangerang
(2, 1, 1),  -- Coach Maya -> Jakarta (primary)
(2, 3, 0);  -- Coach Maya -> Bandung

-- ----------------------------
-- Branch Product Stock (stock per cabang)
-- ----------------------------
INSERT INTO `branch_product_stock` (`branch_id`, `product_id`, `stock`, `min_stock`) VALUES
-- Jakarta (cabang utama, stock terbanyak)
(1, 1, 15, 5), (1, 2, 12, 5), (1, 3, 50, 10), (1, 4, 50, 10),
(1, 5, 20, 5), (1, 6, 15, 3), (1, 7, 12, 3), (1, 8, 999, 0), (1, 9, 999, 0),
-- Tangerang
(2, 1, 8, 3), (2, 2, 8, 3), (2, 3, 25, 5), (2, 4, 25, 5),
(2, 5, 10, 3), (2, 6, 8, 2), (2, 7, 8, 2), (2, 8, 999, 0), (2, 9, 999, 0),
-- Bandung
(3, 1, 7, 3), (3, 2, 5, 3), (3, 3, 23, 5), (3, 4, 23, 5),
(3, 5, 6, 3), (3, 6, 7, 2), (3, 7, 5, 2), (3, 8, 999, 0), (3, 9, 999, 0);

-- ----------------------------
-- Class Schedules - Cabang Tangerang & Bandung
-- ----------------------------
INSERT INTO `class_schedules` (`branch_id`, `class_type_id`, `trainer_id`, `day_of_week`, `start_time`, `end_time`, `capacity`, `room`) VALUES
-- Tangerang (Coach Eko)
(2, 1, 1, 2, '08:00:00', '09:00:00', 15, 'Studio A'),  -- Yoga Tuesday @TNG
(2, 2, 1, 4, '17:00:00', '17:45:00', 12, 'Spinning Room'),  -- Spinning Thursday @TNG
-- Bandung (Coach Maya)
(3, 1, 2, 3, '07:00:00', '08:00:00', 18, 'Studio A'),  -- Yoga Wednesday @BDG
(3, 4, 2, 5, '09:00:00', '10:00:00', 12, 'Studio A');  -- Pilates Friday @BDG

-- ----------------------------
-- MULTI-BRANCH SAMPLE DATA
-- Case: PT sessions & class bookings across different branches
-- Membership berlaku di SEMUA cabang, trainer bisa pindah-pindah
-- ----------------------------

-- ============================
-- 1) Siti (user 7, VIP) - PT di Tangerang dengan Coach Eko
-- Coach Eko assigned di Jakarta (primary) & Tangerang
-- Siti sudah punya member_pt_sessions id=1, 10 sesi, 3 used (all di Jakarta)
-- Sekarang Siti juga latihan PT di cabang Tangerang
-- ============================

-- PT Bookings Siti di Tangerang (branch_id=2, trainer=1=Coach Eko)
-- Session 6 & 7 di Tangerang (karena Siti sedang di Tangerang)
INSERT INTO `pt_bookings` (`branch_id`, `member_pt_session_id`, `user_id`, `trainer_id`, `booking_date`, `start_time`, `end_time`, `status`, `notes`, `completed_at`, `completed_by`, `created_at`) VALUES
(2, 1, 7, 1, '2026-02-07', '09:00:00', '10:00:00', 'completed', 'Session 6: Strength training @Tangerang', '2026-02-07 10:00:00', 5, '2026-02-03 14:00:00'),
(2, 1, 7, 1, '2026-02-14', '09:00:00', '10:00:00', 'booked', 'Session 7: HIIT cardio @Tangerang', NULL, NULL, '2026-02-10 09:00:00');

-- Update Siti's PT sessions: 4 used now (3 JKT + 1 TNG completed)
-- remaining_sessions is auto-calculated (generated column: total - used)
UPDATE `member_pt_sessions` SET used_sessions = 4 WHERE id = 1;

-- Checkin Siti di Tangerang (membership berlaku di semua cabang)
INSERT INTO `member_checkins` (`branch_id`, `user_id`, `checkin_type`, `membership_id`, `class_pass_id`, `checkin_time`, `checkout_time`, `checkin_method`, `notes`, `created_at`) VALUES
(2, 7, 'gym', 2, NULL, '2026-02-07 08:30:00', '2026-02-07 10:30:00', 'qr_code', 'PT session + gym @Tangerang', '2026-02-07 08:30:00'),
(2, 7, 'gym', 2, NULL, '2026-02-08 08:00:00', '2026-02-08 09:30:00', 'qr_code', 'Morning gym @Tangerang', '2026-02-08 08:00:00');

-- ============================
-- 2) Siti (user 7, VIP) - Ikut kelas di cabang Bandung
-- Coach Maya mengajar Yoga Wednesday & Pilates Friday di Bandung
-- Siti punya VIP membership = include classes (unlimited)
-- schedule_id 13 = Yoga Wednesday @BDG, schedule_id 14 = Pilates Friday @BDG
-- ============================

INSERT INTO `class_bookings` (`branch_id`, `user_id`, `schedule_id`, `class_date`, `access_type`, `membership_id`, `class_pass_id`, `status`, `booked_at`, `attended_at`, `notes`, `created_at`) VALUES
-- Siti ikut Yoga di Bandung (Coach Maya)
(3, 7, 13, '2026-02-05', 'membership', 2, NULL, 'attended', '2026-02-03 20:00:00', '2026-02-05 07:00:00', 'VIP Member - Yoga @Bandung', '2026-02-03 20:00:00'),
-- Siti ikut Pilates di Bandung (Coach Maya)
(3, 7, 14, '2026-02-07', 'membership', 2, NULL, 'attended', '2026-02-05 10:00:00', '2026-02-07 09:00:00', 'VIP Member - Pilates @Bandung', '2026-02-05 10:00:00'),
-- Siti book lagi Yoga di Bandung minggu depan
(3, 7, 13, '2026-02-12', 'membership', 2, NULL, 'booked', '2026-02-09 21:00:00', NULL, 'VIP Member - Yoga @Bandung, next week', '2026-02-09 21:00:00');

-- Checkin Siti di Bandung (untuk kelas)
INSERT INTO `member_checkins` (`branch_id`, `user_id`, `checkin_type`, `membership_id`, `class_pass_id`, `checkin_time`, `checkout_time`, `checkin_method`, `notes`, `created_at`) VALUES
(3, 7, 'gym', 2, NULL, '2026-02-05 06:45:00', '2026-02-05 08:15:00', 'qr_code', 'Yoga class @Bandung', '2026-02-05 06:45:00'),
(3, 7, 'gym', 2, NULL, '2026-02-07 08:30:00', '2026-02-07 10:30:00', 'qr_code', 'Pilates class @Bandung', '2026-02-07 08:30:00');

-- ============================
-- 3) Budi (user 6, Premium) - Ikut kelas di Bandung
-- Premium membership include classes
-- schedule_id 13 = Yoga Wednesday @BDG (Coach Maya)
-- ============================

INSERT INTO `class_bookings` (`branch_id`, `user_id`, `schedule_id`, `class_date`, `access_type`, `membership_id`, `class_pass_id`, `status`, `booked_at`, `attended_at`, `notes`, `created_at`) VALUES
-- Budi ikut Yoga di Bandung
(3, 6, 13, '2026-02-05', 'membership', 1, NULL, 'attended', '2026-02-02 19:00:00', '2026-02-05 07:00:00', 'Premium Member - Yoga @Bandung, bareng Siti', '2026-02-02 19:00:00'),
-- Budi book Pilates di Bandung
(3, 6, 14, '2026-02-14', 'membership', 1, NULL, 'booked', '2026-02-10 20:00:00', NULL, 'Premium Member - Pilates @Bandung', '2026-02-10 20:00:00');

-- Checkin Budi di Bandung
INSERT INTO `member_checkins` (`branch_id`, `user_id`, `checkin_type`, `membership_id`, `class_pass_id`, `checkin_time`, `checkout_time`, `checkin_method`, `notes`, `created_at`) VALUES
(3, 6, 'gym', 1, NULL, '2026-02-05 06:30:00', '2026-02-05 08:30:00', 'qr_code', 'Yoga @Bandung - trip bareng Siti', '2026-02-05 06:30:00');

-- ============================
-- 4) Andi (user 8, Basic + Class Pass) - Ikut kelas di Tangerang
-- Basic membership (gym only), kelas pakai class_pass_id=1 (10 classes, 4 used)
-- schedule_id 11 = Yoga Tuesday @TNG (Coach Eko)
-- schedule_id 12 = Spinning Thursday @TNG (Coach Eko)
-- ============================

INSERT INTO `class_bookings` (`branch_id`, `user_id`, `schedule_id`, `class_date`, `access_type`, `membership_id`, `class_pass_id`, `status`, `booked_at`, `attended_at`, `notes`, `created_at`) VALUES
-- Andi ikut Yoga di Tangerang (pakai class pass, setelah 4 kelas di JKT)
(2, 8, 11, '2026-02-04', 'class_pass', NULL, 1, 'attended', '2026-02-02 20:00:00', '2026-02-04 08:00:00', 'Class Pass - Yoga @Tangerang (Coach Eko)', '2026-02-02 20:00:00'),
-- Andi ikut Spinning di Tangerang (pakai class pass)
(2, 8, 12, '2026-02-06', 'class_pass', NULL, 1, 'attended', '2026-02-04 19:00:00', '2026-02-06 17:00:00', 'Class Pass - Spinning @Tangerang (Coach Eko)', '2026-02-04 19:00:00'),
-- Andi book Yoga lagi di Tangerang
(2, 8, 11, '2026-02-11', 'class_pass', NULL, 1, 'booked', '2026-02-09 10:00:00', NULL, 'Class Pass - Yoga @Tangerang next week', '2026-02-09 10:00:00');

-- Update Andi's class pass: 6 used now (4 JKT + 2 TNG attended)
-- remaining_classes is auto-calculated (generated column: total - used)
UPDATE `member_class_passes` SET used_classes = 6 WHERE id = 1;

-- Checkin Andi di Tangerang (gym + kelas)
INSERT INTO `member_checkins` (`branch_id`, `user_id`, `checkin_type`, `membership_id`, `class_pass_id`, `checkin_time`, `checkout_time`, `checkin_method`, `notes`, `created_at`) VALUES
(2, 8, 'gym', 3, NULL, '2026-02-04 07:30:00', '2026-02-04 09:30:00', 'qr_code', 'Yoga class + gym @Tangerang', '2026-02-04 07:30:00'),
(2, 8, 'gym', 3, NULL, '2026-02-06 16:30:00', '2026-02-06 18:30:00', 'qr_code', 'Spinning class + gym @Tangerang', '2026-02-06 16:30:00');

-- ============================
-- 5) Lisa (user 12, Class Pass Only) - Ikut kelas di Bandung
-- Lisa punya class_pass_id=3 (5 classes, 2 used di JKT)
-- schedule_id 14 = Pilates Friday @BDG (Coach Maya)
-- ============================

INSERT INTO `class_bookings` (`branch_id`, `user_id`, `schedule_id`, `class_date`, `access_type`, `membership_id`, `class_pass_id`, `status`, `booked_at`, `attended_at`, `notes`, `created_at`) VALUES
-- Lisa ikut Pilates di Bandung
(3, 12, 14, '2026-02-07', 'class_pass', NULL, 3, 'attended', '2026-02-05 11:00:00', '2026-02-07 09:00:00', 'Class Pass 3/5 - Pilates @Bandung', '2026-02-05 11:00:00'),
-- Lisa book Yoga di Bandung
(3, 12, 13, '2026-02-12', 'class_pass', NULL, 3, 'booked', '2026-02-09 20:00:00', NULL, 'Class Pass 4/5 - Yoga @Bandung', '2026-02-09 20:00:00');

-- Update Lisa's class pass: 3 used now (2 JKT + 1 BDG attended)
-- remaining_classes is auto-calculated (generated column: total - used)
UPDATE `member_class_passes` SET used_classes = 3 WHERE id = 3;

-- Checkin Lisa di Bandung (class only - no membership)
INSERT INTO `member_checkins` (`branch_id`, `user_id`, `checkin_type`, `membership_id`, `class_pass_id`, `checkin_time`, `checkout_time`, `checkin_method`, `notes`, `created_at`) VALUES
(3, 12, 'class_only', NULL, 3, '2026-02-07 08:45:00', '2026-02-07 10:15:00', 'manual', 'Class only - Pilates @Bandung', '2026-02-07 08:45:00');


SET FOREIGN_KEY_CHECKS = 1;

/*
================================================================================
                            TABLE SUMMARY
================================================================================

TOTAL: 31 TABLES (+ 3 junction/stock tables = 34 CREATE TABLEs)

BRANCHES (1 table):
  1. branches              - Daftar cabang/lokasi gym

AUTH & USERS (5 tables + 1 log):
  2. roles                 - Daftar role/jabatan
  3. permissions           - Daftar hak akses
  4. role_permissions      - Pivot role-permission (many-to-many)
  5. users                 - Data semua pengguna
  6. otp_verifications     - Kode OTP untuk verifikasi
  7. audit_logs            - Log perubahan data untuk audit

MEMBERSHIP (2 tables):
  8. membership_packages   - Paket membership yang dijual
  9. member_memberships    - Membership aktif member

CHECK-IN (1 table):
  10. member_checkins      - Record check-in/checkout

TRAINERS & PT (5 tables):
  11. trainers             - Data trainer
  12. trainer_branches     - Assignment trainer ke cabang
  13. pt_packages          - Paket Personal Training
  14. member_pt_sessions   - PT session yang dimiliki member
  15. pt_bookings          - Booking jadwal PT

CLASSES (5 tables):
  16. class_types          - Jenis-jenis kelas
  17. class_schedules      - Jadwal kelas
  18. class_bookings       - Booking kelas member
  19. class_packages       - Paket kelas untuk dijual
  20. member_class_passes  - Class pass yang dimiliki member

PRODUCTS (4 tables):
  21. product_categories   - Kategori produk
  22. products             - Data produk POS
  23. product_stock_logs   - Log perubahan stock
  24. branch_product_stock - Stock produk per cabang

TRANSACTIONS (2 tables):
  25. transactions         - Header transaksi
  26. transaction_items    - Detail item transaksi

SUBSCRIPTIONS (3 tables):
  27. payment_methods      - Metode pembayaran tersimpan
  28. subscriptions        - Data recurring subscription
  29. subscription_invoices - Invoice dari subscription

PROMOS (3 tables):
  30. promos               - Promo otomatis
  31. vouchers             - Voucher code
  32. voucher_usages       - Log penggunaan voucher

SETTINGS & NOTIFICATIONS (2 tables):
  33. settings             - Konfigurasi sistem
  34. notifications        - Notifikasi user

================================================================================
*/
