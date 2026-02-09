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

 Date: 04/02/2026 14:27:10
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for audit_logs
-- ----------------------------
DROP TABLE IF EXISTS `audit_logs`;
CREATE TABLE `audit_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `branch_id` int(11) DEFAULT NULL COMMENT 'Cabang tempat aksi dilakukan',
  `table_name` varchar(100) DEFAULT NULL,
  `record_id` int(11) DEFAULT NULL,
  `action` enum('create','update','delete') DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `old_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`old_data`)),
  `new_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`new_data`)),
  `ip_address` varchar(45) DEFAULT NULL,
  `user_agent` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_audit_table` (`table_name`,`record_id`),
  KEY `idx_audit_user` (`user_id`),
  KEY `idx_audit_branch` (`branch_id`),
  CONSTRAINT `audit_logs_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for branch_product_stock
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
  UNIQUE KEY `unique_branch_product` (`branch_id`,`product_id`),
  KEY `idx_product_stock` (`product_id`),
  CONSTRAINT `branch_product_stock_ibfk_1` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`) ON DELETE CASCADE,
  CONSTRAINT `branch_product_stock_ibfk_2` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=28 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for branches
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
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for class_bookings
-- ----------------------------
DROP TABLE IF EXISTS `class_bookings`;
CREATE TABLE `class_bookings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `branch_id` int(11) NOT NULL COMMENT 'Cabang tempat kelas',
  `user_id` int(11) NOT NULL,
  `schedule_id` int(11) NOT NULL,
  `class_date` date NOT NULL COMMENT 'Tanggal kelas yang di-booking',
  `access_type` enum('membership','class_pass') NOT NULL COMMENT 'Sumber akses: membership benefit atau class pass',
  `membership_id` int(11) DEFAULT NULL COMMENT 'FK ke member_memberships jika pakai benefit membership',
  `class_pass_id` int(11) DEFAULT NULL COMMENT 'FK ke member_class_passes jika pakai class pass',
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
  UNIQUE KEY `unique_booking` (`user_id`,`schedule_id`,`class_date`),
  KEY `idx_class_booking_branch` (`branch_id`),
  KEY `idx_class_booking_date` (`class_date`),
  KEY `idx_class_booking_membership` (`membership_id`),
  KEY `idx_class_booking_class_pass` (`class_pass_id`),
  KEY `class_bookings_ibfk_2` (`schedule_id`),
  CONSTRAINT `class_bookings_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`),
  CONSTRAINT `class_bookings_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `class_bookings_ibfk_2` FOREIGN KEY (`schedule_id`) REFERENCES `class_schedules` (`id`),
  CONSTRAINT `class_bookings_ibfk_3` FOREIGN KEY (`membership_id`) REFERENCES `member_memberships` (`id`) ON DELETE SET NULL,
  CONSTRAINT `class_bookings_ibfk_4` FOREIGN KEY (`class_pass_id`) REFERENCES `member_class_passes` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=37 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for class_packages
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
  KEY `class_packages_ibfk_1` (`class_type_id`),
  CONSTRAINT `class_packages_ibfk_1` FOREIGN KEY (`class_type_id`) REFERENCES `class_types` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for class_schedules
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
  UNIQUE KEY `idx_unique_schedule` (`branch_id`,`class_type_id`,`trainer_id`,`day_of_week`,`start_time`,`room`),
  KEY `idx_schedule_branch` (`branch_id`),
  KEY `idx_schedule_day` (`day_of_week`,`start_time`),
  KEY `class_schedules_ibfk_1` (`class_type_id`),
  KEY `class_schedules_ibfk_2` (`trainer_id`),
  CONSTRAINT `class_schedules_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`),
  CONSTRAINT `class_schedules_ibfk_1` FOREIGN KEY (`class_type_id`) REFERENCES `class_types` (`id`),
  CONSTRAINT `class_schedules_ibfk_2` FOREIGN KEY (`trainer_id`) REFERENCES `trainers` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for class_types
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
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for member_checkins
-- ----------------------------
DROP TABLE IF EXISTS `member_checkins`;
CREATE TABLE `member_checkins` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `branch_id` int(11) NOT NULL COMMENT 'Cabang tempat check-in',
  `user_id` int(11) NOT NULL,
  `checkin_type` enum('gym','class_only') NOT NULL DEFAULT 'gym' COMMENT 'gym=akses penuh, class_only=hanya area kelas',
  `membership_id` int(11) DEFAULT NULL COMMENT 'Jika pakai membership',
  `class_pass_id` int(11) DEFAULT NULL COMMENT 'Jika HANYA ikut kelas tanpa membership',
  `checkin_time` datetime NOT NULL DEFAULT current_timestamp(),
  `checkout_time` datetime DEFAULT NULL,
  `checkin_method` enum('qr_code','manual','card') NOT NULL DEFAULT 'qr_code',
  `checked_in_by` int(11) DEFAULT NULL COMMENT 'Staff yang check-in manual',
  `notes` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_checkin_branch` (`branch_id`),
  KEY `idx_checkin_user` (`user_id`),
  KEY `idx_checkin_date` (`checkin_time`),
  KEY `idx_checkin_type` (`checkin_type`),
  KEY `member_checkins_ibfk_2` (`membership_id`),
  KEY `member_checkins_ibfk_3` (`checked_in_by`),
  KEY `member_checkins_ibfk_4` (`class_pass_id`),
  CONSTRAINT `member_checkins_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`),
  CONSTRAINT `member_checkins_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `member_checkins_ibfk_2` FOREIGN KEY (`membership_id`) REFERENCES `member_memberships` (`id`) ON DELETE SET NULL,
  CONSTRAINT `member_checkins_ibfk_3` FOREIGN KEY (`checked_in_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `member_checkins_ibfk_4` FOREIGN KEY (`class_pass_id`) REFERENCES `member_class_passes` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=51 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for member_class_passes
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
  KEY `member_class_passes_ibfk_2` (`class_package_id`),
  CONSTRAINT `member_class_passes_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `member_class_passes_ibfk_2` FOREIGN KEY (`class_package_id`) REFERENCES `class_packages` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for member_memberships
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
  KEY `member_memberships_ibfk_2` (`package_id`),
  CONSTRAINT `member_memberships_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `member_memberships_ibfk_2` FOREIGN KEY (`package_id`) REFERENCES `membership_packages` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for member_pt_sessions
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
  KEY `member_pt_sessions_ibfk_2` (`pt_package_id`),
  KEY `member_pt_sessions_ibfk_3` (`trainer_id`),
  CONSTRAINT `member_pt_sessions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `member_pt_sessions_ibfk_2` FOREIGN KEY (`pt_package_id`) REFERENCES `pt_packages` (`id`),
  CONSTRAINT `member_pt_sessions_ibfk_3` FOREIGN KEY (`trainer_id`) REFERENCES `trainers` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

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
  `include_classes` tinyint(1) DEFAULT 0 COMMENT 'Apakah include akses kelas gratis',
  `class_quota` int(11) DEFAULT NULL COMMENT 'Jumlah kelas gratis per periode (NULL = unlimited)',
  `facilities` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT '["gym", "pool", "sauna", "locker"]' CHECK (json_valid(`facilities`)),
  `is_active` tinyint(1) DEFAULT 1,
  `sort_order` int(11) DEFAULT 0,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for notifications
-- ----------------------------
DROP TABLE IF EXISTS `notifications`;
CREATE TABLE `notifications` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `branch_id` int(11) DEFAULT NULL COMMENT 'Cabang terkait notifikasi',
  `user_id` int(11) NOT NULL,
  `type` enum('info','success','warning','error','promo','reminder','billing') NOT NULL DEFAULT 'info',
  `title` varchar(100) NOT NULL,
  `message` text NOT NULL,
  `data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'Additional data (link, action, dll)' CHECK (json_valid(`data`)),
  `is_read` tinyint(1) DEFAULT 0,
  `read_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_notification_branch` (`branch_id`),
  KEY `idx_notification_user` (`user_id`,`is_read`),
  CONSTRAINT `notifications_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`) ON DELETE SET NULL,
  CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

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
  KEY `idx_otp_contact` (`contact_value`,`otp_type`),
  KEY `otp_verifications_ibfk_1` (`user_id`),
  CONSTRAINT `otp_verifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for payment_methods
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
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=50 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for product_stock_logs
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
  KEY `product_stock_logs_ibfk_2` (`created_by`),
  CONSTRAINT `product_stock_logs_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`),
  CONSTRAINT `product_stock_logs_ibfk_1` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE,
  CONSTRAINT `product_stock_logs_ibfk_2` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for promos
-- ----------------------------
DROP TABLE IF EXISTS `promos`;
CREATE TABLE `promos` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `promo_type` enum('percentage','fixed','free_item') NOT NULL,
  `discount_value` decimal(12,2) DEFAULT 0.00,
  `min_purchase` decimal(12,2) DEFAULT 0.00 COMMENT 'Minimum pembelian',
  `max_discount` decimal(12,2) DEFAULT NULL COMMENT 'Maksimum potongan (untuk percentage)',
  `applicable_to` enum('all','membership','class','pt','product') NOT NULL DEFAULT 'all',
  `applicable_items` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'Specific item IDs' CHECK (json_valid(`applicable_items`)),
  `start_date` datetime NOT NULL,
  `end_date` datetime NOT NULL,
  `usage_limit` int(11) DEFAULT NULL COMMENT 'Total penggunaan maksimal',
  `usage_count` int(11) DEFAULT 0,
  `per_user_limit` int(11) DEFAULT 1 COMMENT 'Penggunaan per user',
  `new_member_only` tinyint(1) DEFAULT 0,
  `member_only` tinyint(1) DEFAULT 0,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for pt_bookings
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
  KEY `idx_pt_booking_trainer` (`trainer_id`,`booking_date`),
  KEY `pt_bookings_ibfk_1` (`member_pt_session_id`),
  KEY `pt_bookings_ibfk_2` (`user_id`),
  CONSTRAINT `pt_bookings_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`),
  CONSTRAINT `pt_bookings_ibfk_1` FOREIGN KEY (`member_pt_session_id`) REFERENCES `member_pt_sessions` (`id`),
  CONSTRAINT `pt_bookings_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `pt_bookings_ibfk_3` FOREIGN KEY (`trainer_id`) REFERENCES `trainers` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for pt_packages
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
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=114 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for subscription_invoices
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
  KEY `idx_invoice_due_date` (`due_date`,`status`),
  KEY `subscription_invoices_ibfk_2` (`transaction_id`),
  CONSTRAINT `subscription_invoices_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`) ON DELETE SET NULL,
  CONSTRAINT `subscription_invoices_ibfk_1` FOREIGN KEY (`subscription_id`) REFERENCES `subscriptions` (`id`) ON DELETE CASCADE,
  CONSTRAINT `subscription_invoices_ibfk_2` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE SET NULL
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
  `base_price` decimal(12,2) NOT NULL,
  `discount_type` enum('percentage','fixed') DEFAULT NULL,
  `discount_value` decimal(12,2) DEFAULT 0.00,
  `discount_amount` decimal(12,2) DEFAULT 0.00,
  `recurring_price` decimal(12,2) NOT NULL COMMENT 'Harga yang dicharge setiap cycle',
  `billing_cycle` enum('weekly','monthly','quarterly','yearly') NOT NULL,
  `billing_day` tinyint(2) DEFAULT 1 COMMENT 'Tanggal billing (1-31)',
  `next_billing_date` date NOT NULL,
  `payment_method_id` int(11) DEFAULT NULL,
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
  KEY `idx_subscription_billing` (`next_billing_date`,`status`),
  KEY `subscriptions_ibfk_2` (`payment_method_id`),
  CONSTRAINT `subscriptions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `subscriptions_ibfk_2` FOREIGN KEY (`payment_method_id`) REFERENCES `payment_methods` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for trainer_branches
-- ----------------------------
DROP TABLE IF EXISTS `trainer_branches`;
CREATE TABLE `trainer_branches` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `trainer_id` int(11) NOT NULL,
  `branch_id` int(11) NOT NULL,
  `is_primary` tinyint(1) DEFAULT 0 COMMENT 'Cabang utama trainer',
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_trainer_branch` (`trainer_id`,`branch_id`),
  KEY `idx_branch_trainers` (`branch_id`),
  CONSTRAINT `trainer_branches_ibfk_1` FOREIGN KEY (`trainer_id`) REFERENCES `trainers` (`id`) ON DELETE CASCADE,
  CONSTRAINT `trainer_branches_ibfk_2` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for trainers
-- ----------------------------
DROP TABLE IF EXISTS `trainers`;
CREATE TABLE `trainers` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `specialization` varchar(255) DEFAULT NULL COMMENT 'Strength, Cardio, Yoga, dll',
  `bio` text DEFAULT NULL,
  `certifications` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT '["ACE Certified", "NASM CPT"]' CHECK (json_valid(`certifications`)),
  `experience_years` int(11) DEFAULT 0,
  `rate_per_session` decimal(12,2) DEFAULT NULL COMMENT 'Harga per session jika freelance',
  `commission_percentage` decimal(5,2) DEFAULT 0.00 COMMENT 'Komisi dari PT session',
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `trainers_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for transaction_items
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
  `discount_type` enum('percentage','fixed') DEFAULT NULL,
  `discount_value` decimal(12,2) DEFAULT 0.00,
  `discount_amount` decimal(12,2) DEFAULT 0.00,
  `subtotal` decimal(12,2) NOT NULL,
  `metadata` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`metadata`)),
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_transaction_item` (`transaction_id`),
  CONSTRAINT `transaction_items_ibfk_1` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=37 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for transactions
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
  `subtotal` decimal(12,2) NOT NULL DEFAULT 0.00,
  `discount_type` enum('percentage','fixed') DEFAULT NULL,
  `discount_value` decimal(12,2) DEFAULT 0.00,
  `discount_amount` decimal(12,2) DEFAULT 0.00,
  `subtotal_after_discount` decimal(12,2) NOT NULL DEFAULT 0.00,
  `tax_percentage` decimal(5,2) DEFAULT 0.00,
  `tax_amount` decimal(12,2) DEFAULT 0.00,
  `service_charge_percentage` decimal(5,2) DEFAULT 0.00,
  `service_charge_amount` decimal(12,2) DEFAULT 0.00,
  `grand_total` decimal(12,2) NOT NULL DEFAULT 0.00,
  `payment_method` enum('cash','transfer','qris','card','ewallet','other') DEFAULT NULL,
  `payment_status` enum('pending','paid','failed','refunded','partial') NOT NULL DEFAULT 'pending',
  `paid_amount` decimal(12,2) DEFAULT 0.00,
  `change_amount` decimal(12,2) DEFAULT 0.00,
  `paid_at` datetime DEFAULT NULL,
  `promo_id` int(11) DEFAULT NULL,
  `promo_discount` decimal(12,2) DEFAULT 0.00 COMMENT 'Jumlah diskon dari promo',
  `voucher_code` varchar(50) DEFAULT NULL,
  `voucher_discount` decimal(12,2) DEFAULT 0.00 COMMENT 'Jumlah diskon dari voucher',
  `notes` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `transaction_code` (`transaction_code`),
  KEY `idx_transaction_branch` (`branch_id`),
  KEY `idx_transaction_user` (`user_id`),
  KEY `idx_transaction_date` (`created_at`),
  KEY `idx_transaction_status` (`payment_status`),
  KEY `transactions_ibfk_2` (`staff_id`),
  CONSTRAINT `transactions_branch_fk` FOREIGN KEY (`branch_id`) REFERENCES `branches` (`id`),
  CONSTRAINT `transactions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `transactions_ibfk_2` FOREIGN KEY (`staff_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=29 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

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
  `default_branch_id` int(11) DEFAULT NULL COMMENT 'Default cabang user (staff/admin untuk CMS, member untuk preferensi)',
  `is_active` tinyint(1) DEFAULT 1,
  `pin` varchar(255) DEFAULT NULL,
  `has_pin` tinyint(1) DEFAULT 0,
  `pin_version` int(11) DEFAULT 1,
  `failed_pin_attempts` int(11) DEFAULT 0,
  `pin_locked_until` datetime DEFAULT NULL,
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
  CONSTRAINT `users_branch_fk` FOREIGN KEY (`default_branch_id`) REFERENCES `branches` (`id`) ON DELETE SET NULL,
  CONSTRAINT `users_ibfk_1` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

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
  KEY `idx_voucher_usage` (`voucher_id`,`user_id`),
  KEY `voucher_usages_ibfk_2` (`user_id`),
  KEY `voucher_usages_ibfk_3` (`transaction_id`),
  CONSTRAINT `voucher_usages_ibfk_1` FOREIGN KEY (`voucher_id`) REFERENCES `vouchers` (`id`) ON DELETE CASCADE,
  CONSTRAINT `voucher_usages_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `voucher_usages_ibfk_3` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for discount_usages
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

-- ----------------------------
-- Table structure for vouchers
-- ----------------------------
DROP TABLE IF EXISTS `vouchers`;
CREATE TABLE `vouchers` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `code` varchar(50) NOT NULL,
  `voucher_type` enum('percentage','fixed','free_item') NOT NULL,
  `discount_value` decimal(12,2) DEFAULT 0.00,
  `min_purchase` decimal(12,2) DEFAULT 0.00,
  `max_discount` decimal(12,2) DEFAULT NULL,
  `applicable_to` enum('all','membership','class','pt','product') NOT NULL DEFAULT 'all',
  `applicable_items` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'Specific item IDs' CHECK (json_valid(`applicable_items`)),
  `start_date` datetime NOT NULL,
  `end_date` datetime NOT NULL,
  `usage_limit` int(11) DEFAULT 1,
  `usage_count` int(11) DEFAULT 0,
  `is_single_use` tinyint(1) DEFAULT 1 COMMENT 'Sekali pakai per user',
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Table structure for images
-- ----------------------------
DROP TABLE IF EXISTS `images`;
CREATE TABLE `images` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `category` enum('splash_screen','onboarding','banner','banner_member','banner_class','banner_pt','banner_product','pop_promo','product','class','pt','content','other') NOT NULL COMMENT 'Kategori penggunaan gambar',
  `reference_id` int(11) DEFAULT NULL COMMENT 'FK ke record terkait (product_id, class_type_id, dll). NULL untuk gambar umum',
  `title` varchar(150) DEFAULT NULL COMMENT 'Judul/alt text gambar',
  `description` text DEFAULT NULL,
  `file_path` varchar(500) NOT NULL COMMENT 'Path file gambar di storage',
  `file_name` varchar(255) NOT NULL COMMENT 'Nama file asli',
  `file_size` int(11) DEFAULT NULL COMMENT 'Ukuran file dalam bytes',
  `mime_type` varchar(50) DEFAULT NULL COMMENT 'image/jpeg, image/png, image/webp',
  `width` int(11) DEFAULT NULL COMMENT 'Lebar gambar dalam pixel',
  `height` int(11) DEFAULT NULL COMMENT 'Tinggi gambar dalam pixel',
  `sort_order` int(11) DEFAULT 0 COMMENT 'Urutan tampilan',
  `is_active` tinyint(1) DEFAULT 1,
  `start_date` datetime DEFAULT NULL COMMENT 'Tanggal mulai tampil (untuk banner/pop_promo)',
  `end_date` datetime DEFAULT NULL COMMENT 'Tanggal selesai tampil (untuk banner/pop_promo)',
  `deep_link` varchar(500) DEFAULT NULL COMMENT 'URL/deep link saat gambar diklik (untuk banner/pop_promo)',
  `platform` enum('all','mobile','web','cms') DEFAULT 'all' COMMENT 'Platform target tampil',
  `created_by` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_images_category` (`category`),
  KEY `idx_images_reference` (`category`,`reference_id`),
  KEY `idx_images_active` (`is_active`,`category`),
  KEY `idx_images_schedule` (`start_date`,`end_date`),
  KEY `idx_images_created_by` (`created_by`),
  CONSTRAINT `images_created_by_fk` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ----------------------------
-- Insert image permissions
-- ----------------------------
INSERT INTO `permissions` (`name`, `description`) VALUES
('image.view', 'Melihat daftar gambar'),
('image.create', 'Upload gambar baru'),
('image.update', 'Edit metadata/file gambar'),
('image.delete', 'Hapus gambar')
ON DUPLICATE KEY UPDATE `description` = VALUES(`description`);

-- Grant image permissions to superadmin role (role_id = 1)
INSERT INTO `role_permissions` (`role_id`, `permission_id`)
SELECT 1, id FROM `permissions` WHERE `name` IN ('image.view', 'image.create', 'image.update', 'image.delete')
ON DUPLICATE KEY UPDATE `role_id` = `role_id`;

-- Grant image permissions to admin role (role_id = 2)
INSERT INTO `role_permissions` (`role_id`, `permission_id`)
SELECT 2, id FROM `permissions` WHERE `name` IN ('image.view', 'image.create', 'image.update', 'image.delete')
ON DUPLICATE KEY UPDATE `role_id` = `role_id`;

SET FOREIGN_KEY_CHECKS = 1;
