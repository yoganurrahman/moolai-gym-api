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

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- AUTH & USERS
-- ============================================================================

-- ----------------------------
-- Table structure for roles
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
-- Table structure for permissions
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
(45, 'settings.update', 'Update pengaturan');

-- ----------------------------
-- Table structure for role_permissions
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
-- Table structure for users
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
  CONSTRAINT `users_ibfk_1` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of users (default users, password: password123, pin: 123456)
-- ----------------------------
INSERT INTO `users` (`id`, `name`, `email`, `password`, `pin`, `has_pin`, `phone`, `role_id`, `is_active`) VALUES
(1, 'Super Admin', 'superadmin@moolaigym.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567890', 1, 1),
(2, 'Admin Gym', 'admin@moolaigym.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567891', 2, 1),
(3, 'Staff Kasir', 'staff@moolaigym.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567892', 5, 1),
(4, 'Member User', 'member@moolaigym.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567893', 3, 1),
(5, 'Coach Eko', 'trainer@moolaigym.com', '$2b$12$L.5z5PVoOyHKr2muErPwDeIaXVafAMp73Dq2aLtR67TXUgUODTd9u', '$2b$12$8y8T.vBbtUIM0jfiJQpZB.22q735D7xR.iDFjvAp2cVWT9oTq0tSO', 1, '081234567894', 4, 1);

-- ----------------------------
-- Table structure for otp_verifications
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
-- Table structure for audit_logs
-- ----------------------------
DROP TABLE IF EXISTS `audit_logs`;
CREATE TABLE `audit_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
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
  KEY `idx_audit_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================================
-- MEMBERSHIP PACKAGES
-- ============================================================================

-- ----------------------------
-- Table structure for membership_packages
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
INSERT INTO `membership_packages` (`name`, `description`, `package_type`, `duration_days`, `visit_quota`, `price`, `include_classes`, `class_quota`, `facilities`, `sort_order`) VALUES
('Daily Pass', 'Akses gym 1 hari', 'daily', 1, NULL, 50000.00, 0, NULL, '["gym"]', 1),
('Weekly Pass', 'Akses gym 7 hari', 'weekly', 7, NULL, 150000.00, 0, NULL, '["gym"]', 2),
('Basic Monthly', 'Akses gym 1 bulan', 'monthly', 30, NULL, 300000.00, 0, NULL, '["gym"]', 3),
('Premium Monthly', 'Akses gym + pool + sauna 1 bulan', 'monthly', 30, NULL, 500000.00, 1, NULL, '["gym", "pool", "sauna"]', 4),
('VIP Monthly', 'All access + 4x PT session', 'monthly', 30, NULL, 1000000.00, 1, NULL, '["gym", "pool", "sauna", "locker"]', 5),
('Quarterly Basic', 'Akses gym 3 bulan', 'quarterly', 90, NULL, 800000.00, 0, NULL, '["gym"]', 6),
('Yearly Basic', 'Akses gym 1 tahun', 'yearly', 365, NULL, 2500000.00, 1, 48, '["gym"]', 7),
('10 Visit Pass', 'Akses gym 10 kali kunjungan', 'visit', NULL, 10, 400000.00, 0, NULL, '["gym"]', 8);

-- ----------------------------
-- Table structure for member_memberships (membership aktif member)
-- ----------------------------
DROP TABLE IF EXISTS `member_memberships`;
CREATE TABLE `member_memberships` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `package_id` int(11) NOT NULL,
  `transaction_id` int(11) DEFAULT NULL COMMENT 'FK ke transaksi pembelian',
  `membership_code` varchar(50) NOT NULL COMMENT 'Kode unik membership',
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
-- Table structure for member_checkins
-- ----------------------------
DROP TABLE IF EXISTS `member_checkins`;
CREATE TABLE `member_checkins` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `membership_id` int(11) DEFAULT NULL,
  `checkin_time` datetime NOT NULL DEFAULT current_timestamp(),
  `checkout_time` datetime DEFAULT NULL,
  `checkin_method` enum('qr_code','manual','card') NOT NULL DEFAULT 'qr_code',
  `checked_in_by` int(11) DEFAULT NULL COMMENT 'Staff yang check-in manual',
  `notes` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_checkin_user` (`user_id`),
  KEY `idx_checkin_date` (`checkin_time`),
  CONSTRAINT `member_checkins_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `member_checkins_ibfk_2` FOREIGN KEY (`membership_id`) REFERENCES `member_memberships` (`id`) ON DELETE SET NULL,
  CONSTRAINT `member_checkins_ibfk_3` FOREIGN KEY (`checked_in_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================================
-- TRAINERS & PERSONAL TRAINING
-- ============================================================================

-- ----------------------------
-- Table structure for trainers
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
INSERT INTO `trainers` (`user_id`, `specialization`, `bio`, `experience_years`, `commission_percentage`) VALUES
(5, 'Strength & Conditioning', 'Certified personal trainer dengan pengalaman 5 tahun', 5, 30.00);

-- ----------------------------
-- Table structure for pt_packages (Personal Training Packages)
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
-- Table structure for member_pt_sessions (PT session yang dimiliki member)
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
-- Table structure for pt_bookings (Booking jadwal PT)
-- ----------------------------
DROP TABLE IF EXISTS `pt_bookings`;
CREATE TABLE `pt_bookings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
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
  KEY `idx_pt_booking_date` (`booking_date`),
  KEY `idx_pt_booking_trainer` (`trainer_id`, `booking_date`),
  CONSTRAINT `pt_bookings_ibfk_1` FOREIGN KEY (`member_pt_session_id`) REFERENCES `member_pt_sessions` (`id`),
  CONSTRAINT `pt_bookings_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `pt_bookings_ibfk_3` FOREIGN KEY (`trainer_id`) REFERENCES `trainers` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================================
-- CLASS MANAGEMENT
-- ============================================================================

-- ----------------------------
-- Table structure for class_types (Jenis kelas)
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
-- Table structure for class_schedules (Jadwal kelas)
-- ----------------------------
DROP TABLE IF EXISTS `class_schedules`;
CREATE TABLE `class_schedules` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
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
  KEY `idx_schedule_day` (`day_of_week`, `start_time`),
  CONSTRAINT `class_schedules_ibfk_1` FOREIGN KEY (`class_type_id`) REFERENCES `class_types` (`id`),
  CONSTRAINT `class_schedules_ibfk_2` FOREIGN KEY (`trainer_id`) REFERENCES `trainers` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Records of class_schedules
-- ----------------------------
INSERT INTO `class_schedules` (`class_type_id`, `trainer_id`, `day_of_week`, `start_time`, `end_time`, `capacity`, `room`) VALUES
(1, 1, 1, '07:00:00', '08:00:00', 20, 'Studio A'),  -- Yoga Monday
(1, 1, 3, '07:00:00', '08:00:00', 20, 'Studio A'),  -- Yoga Wednesday
(2, 1, 2, '18:00:00', '18:45:00', 15, 'Spinning Room'),  -- Spinning Tuesday
(2, 1, 4, '18:00:00', '18:45:00', 15, 'Spinning Room'),  -- Spinning Thursday
(3, 1, 6, '09:00:00', '10:00:00', 25, 'Studio B');  -- Zumba Saturday

-- ----------------------------
-- Table structure for class_bookings (Booking kelas member)
-- ----------------------------
DROP TABLE IF EXISTS `class_bookings`;
CREATE TABLE `class_bookings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `schedule_id` int(11) NOT NULL,
  `class_date` date NOT NULL COMMENT 'Tanggal kelas yang di-booking',
  `status` enum('booked','attended','cancelled','no_show') NOT NULL DEFAULT 'booked',
  `booked_at` datetime DEFAULT current_timestamp(),
  `cancelled_at` datetime DEFAULT NULL,
  `cancellation_reason` varchar(255) DEFAULT NULL,
  `attended_at` datetime DEFAULT NULL,
  `waitlist_position` int(11) DEFAULT NULL COMMENT 'Posisi di waitlist jika penuh',
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_booking` (`user_id`, `schedule_id`, `class_date`),
  KEY `idx_class_booking_date` (`class_date`),
  CONSTRAINT `class_bookings_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `class_bookings_ibfk_2` FOREIGN KEY (`schedule_id`) REFERENCES `class_schedules` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for class_packages (Paket kelas untuk non-member)
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
-- Table structure for member_class_passes (Class pass yang dimiliki member)
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
-- PRODUCTS & INVENTORY
-- ============================================================================

-- ----------------------------
-- Table structure for product_categories
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
-- Table structure for products
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
INSERT INTO `products` (`category_id`, `sku`, `name`, `description`, `price`, `cost_price`, `stock`) VALUES
(1, 'SUP-WHEY-001', 'Whey Protein 1kg', 'Whey protein isolate', 350000.00, 280000.00, 20),
(1, 'SUP-BCAA-001', 'BCAA 300g', 'Branched-chain amino acids', 250000.00, 180000.00, 15),
(2, 'BEV-SHAKE-001', 'Protein Shake', 'Ready to drink protein shake', 35000.00, 20000.00, 50),
(2, 'BEV-WATER-001', 'Mineral Water 600ml', 'Air mineral', 8000.00, 4000.00, 100),
(3, 'SNK-BAR-001', 'Energy Bar', 'High protein energy bar', 25000.00, 15000.00, 40),
(4, 'APP-SHIRT-001', 'Gym T-Shirt', 'Kaos olahraga', 150000.00, 80000.00, 30),
(5, 'ACC-GLOVE-001', 'Gym Gloves', 'Sarung tangan gym', 120000.00, 60000.00, 25),
(6, 'RNT-TOWEL-001', 'Towel Rental', 'Sewa handuk', 10000.00, 2000.00, 999),
(6, 'RNT-LOCKER-001', 'Locker Rental', 'Sewa locker harian', 15000.00, 0.00, 999);

-- ----------------------------
-- Table structure for product_stock_logs
-- ----------------------------
DROP TABLE IF EXISTS `product_stock_logs`;
CREATE TABLE `product_stock_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
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
  KEY `idx_stock_log_product` (`product_id`),
  CONSTRAINT `product_stock_logs_ibfk_1` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE,
  CONSTRAINT `product_stock_logs_ibfk_2` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================================
-- TRANSACTIONS
-- ============================================================================

-- ----------------------------
-- Table structure for transactions (Header transaksi)
-- ----------------------------
DROP TABLE IF EXISTS `transactions`;
CREATE TABLE `transactions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
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
  `voucher_code` varchar(50) DEFAULT NULL,
  `notes` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `transaction_code` (`transaction_code`),
  KEY `idx_transaction_user` (`user_id`),
  KEY `idx_transaction_date` (`created_at`),
  KEY `idx_transaction_status` (`payment_status`),
  CONSTRAINT `transactions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `transactions_ibfk_2` FOREIGN KEY (`staff_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for transaction_items (Detail item transaksi)
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
-- Table structure for payment_methods (Saved payment methods)
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
-- Table structure for subscriptions
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
-- Table structure for subscription_invoices
-- ----------------------------
DROP TABLE IF EXISTS `subscription_invoices`;
CREATE TABLE `subscription_invoices` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
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
  KEY `idx_subscription_invoice` (`subscription_id`),
  KEY `idx_invoice_due_date` (`due_date`, `status`),
  CONSTRAINT `subscription_invoices_ibfk_1` FOREIGN KEY (`subscription_id`) REFERENCES `subscriptions` (`id`) ON DELETE CASCADE,
  CONSTRAINT `subscription_invoices_ibfk_2` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================================
-- PROMOS & VOUCHERS
-- ============================================================================

-- ----------------------------
-- Table structure for promos
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
-- Table structure for vouchers
-- ----------------------------
DROP TABLE IF EXISTS `vouchers`;
CREATE TABLE `vouchers` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `code` varchar(50) NOT NULL,
  `promo_id` int(11) DEFAULT NULL COMMENT 'Link ke promo jika ada',
  `voucher_type` enum('percentage','fixed','free_item') NOT NULL,
  `discount_value` decimal(12,2) DEFAULT 0,
  `min_purchase` decimal(12,2) DEFAULT 0,
  `max_discount` decimal(12,2) DEFAULT NULL,
  -- Applicable to
  `applicable_to` enum('all','membership','class','pt','product') NOT NULL DEFAULT 'all',
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
  UNIQUE KEY `code` (`code`),
  CONSTRAINT `vouchers_ibfk_1` FOREIGN KEY (`promo_id`) REFERENCES `promos` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for voucher_usages
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

-- ============================================================================
-- SETTINGS
-- ============================================================================

-- ----------------------------
-- Table structure for settings
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
-- Table structure for notifications
-- ----------------------------
DROP TABLE IF EXISTS `notifications`;
CREATE TABLE `notifications` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `type` enum('info','success','warning','error','promo','reminder','billing') NOT NULL DEFAULT 'info',
  `title` varchar(100) NOT NULL,
  `message` text NOT NULL,
  `data` json DEFAULT NULL COMMENT 'Additional data (link, action, dll)',
  `is_read` tinyint(1) DEFAULT 0,
  `read_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_notification_user` (`user_id`, `is_read`),
  CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

SET FOREIGN_KEY_CHECKS = 1;
