-- Migration: Add class_checkin_before_minutes setting
-- Value 0 = check-in boleh sepanjang hari (H-0)
-- Value > 0 = check-in boleh N menit sebelum kelas mulai

INSERT IGNORE INTO `settings` (`key`, `value`, `type`, `description`) VALUES
('class_checkin_before_minutes', '0', 'number', 'Boleh check-in kelas berapa menit sebelum mulai (0 = sepanjang hari)');
