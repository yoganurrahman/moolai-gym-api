-- Step 1: Tambah kolom baru untuk multiple promo & voucher
-- promo_ids (varchar) menyimpan JSON array semua promo ID yang dipakai
-- voucher_codes (varchar) menyimpan JSON array semua voucher code yang dipakai

ALTER TABLE transactions
  ADD COLUMN IF NOT EXISTS promo_ids VARCHAR(500) DEFAULT NULL COMMENT 'JSON array of promo IDs, e.g. [1,5,8]' AFTER promo_id,
  ADD COLUMN IF NOT EXISTS voucher_codes VARCHAR(500) DEFAULT NULL COMMENT 'JSON array of voucher codes, e.g. ["HEMAT5","EXTRA25K"]' AFTER voucher_code;

-- Step 2: Migrate data dari kolom lama ke kolom baru (jalankan sebelum drop)
UPDATE transactions
SET promo_ids = CONCAT('[', promo_id, ']')
WHERE promo_id IS NOT NULL AND (promo_ids IS NULL OR promo_ids = '');

UPDATE transactions
SET voucher_codes = CONCAT('["', voucher_code, '"]')
WHERE voucher_code IS NOT NULL AND voucher_code != '' AND (voucher_codes IS NULL OR voucher_codes = '');

-- Step 3: Drop kolom lama (jalankan setelah yakin migrasi data berhasil)
ALTER TABLE transactions
  DROP COLUMN promo_id,
  DROP COLUMN voucher_code;
