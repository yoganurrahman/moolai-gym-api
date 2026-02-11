-- ============================================================
-- DROP kolom lama promo_id & voucher_code dari tabel transactions
-- ============================================================
-- PENTING: Jalankan SETELAH:
--   1. alter_transactions_multi_promo.sql (Step 1 & 2) sudah dijalankan
--   2. Data sudah termigrasi ke promo_ids & voucher_codes
--   3. Backend sudah di-deploy dengan kode baru (tanpa promo_id/voucher_code)
-- ============================================================

-- Verifikasi dulu: cek apakah ada data yang belum termigrasi
-- SELECT COUNT(*) as belum_migrasi_promo
-- FROM transactions
-- WHERE promo_id IS NOT NULL AND (promo_ids IS NULL OR promo_ids = '');

-- SELECT COUNT(*) as belum_migrasi_voucher
-- FROM transactions
-- WHERE voucher_code IS NOT NULL AND voucher_code != '' AND (voucher_codes IS NULL OR voucher_codes = '');

-- Kalau hasilnya 0 semua, aman untuk DROP:

ALTER TABLE transactions
  DROP COLUMN promo_id,
  DROP COLUMN voucher_code;
