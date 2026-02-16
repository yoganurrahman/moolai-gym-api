-- Migration: Create checkin_qr_tokens table for OTP-style QR check-in
-- Run this migration on the moolai_gym database

CREATE TABLE IF NOT EXISTS `checkin_qr_tokens` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `token` varchar(64) NOT NULL,
  `checkin_type` enum('gym','class_only','pt') NOT NULL,
  `booking_id` int(11) DEFAULT NULL COMMENT 'FK ke class_bookings/pt_bookings tergantung checkin_type',
  `branch_id` int(11) DEFAULT NULL,
  `expires_at` datetime NOT NULL,
  `is_used` tinyint(1) NOT NULL DEFAULT 0,
  `used_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_token` (`token`),
  KEY `idx_user_expires` (`user_id`, `expires_at`),
  CONSTRAINT `checkin_qr_tokens_user_fk` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
