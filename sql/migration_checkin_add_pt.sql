-- Migration: Add 'pt' to checkin_type enum on both tables
-- Also add pt_checkin_before_minutes setting

-- 1. Update checkin_qr_tokens enum
ALTER TABLE `checkin_qr_tokens`
  MODIFY COLUMN `checkin_type` enum('gym','class_only','pt') NOT NULL,
  MODIFY COLUMN `booking_id` int(11) DEFAULT NULL COMMENT 'FK ke class_bookings/pt_bookings tergantung checkin_type';

-- 2. Update member_checkins enum (PENTING: tanpa ini INSERT pt akan error)
ALTER TABLE `member_checkins`
  MODIFY COLUMN `checkin_type` enum('gym','class_only','pt') NOT NULL DEFAULT 'gym' COMMENT 'gym=akses penuh, class_only=hanya area kelas, pt=personal training';

-- 3. Add PT checkin setting
INSERT IGNORE INTO `settings` (`key`, `value`, `type`, `description`) VALUES
('pt_checkin_before_minutes', '0', 'number', 'Boleh check-in PT berapa menit sebelum mulai (0 = sepanjang hari)');
