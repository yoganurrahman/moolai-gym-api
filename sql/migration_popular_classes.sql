-- ================================================================
-- Migration Script: Popular Classes Feature
-- Description: Add support for popular classes ranking by bookings
-- Date: 2026-02-06
-- ================================================================

USE moolai_gym;

-- ================================================================
-- 1. Add 'image' column to class_types if not exists
-- ================================================================

-- Check and add image column
SET @column_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'moolai_gym'
      AND TABLE_NAME = 'class_types'
      AND COLUMN_NAME = 'image'
);

SET @sql = IF(@column_exists = 0,
    'ALTER TABLE class_types ADD COLUMN image VARCHAR(255) DEFAULT NULL AFTER color',
    'SELECT "Column image already exists in class_types" AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ================================================================
-- 2. Create performance index for booking queries
-- ================================================================

-- Check and create index
SET @index_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = 'moolai_gym'
      AND TABLE_NAME = 'class_bookings'
      AND INDEX_NAME = 'idx_booking_schedule_status'
);

SET @sql = IF(@index_exists = 0,
    'CREATE INDEX idx_booking_schedule_status ON class_bookings(schedule_id, status)',
    'SELECT "Index idx_booking_schedule_status already exists" AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ================================================================
-- 3. Verify the schema changes
-- ================================================================

-- Show class_types structure
SELECT 'class_types table structure:' AS '';
DESCRIBE class_types;

-- Show indexes on class_bookings
SELECT 'class_bookings indexes:' AS '';
SHOW INDEXES FROM class_bookings;

-- ================================================================
-- 4. Test query for popular classes (optional verification)
-- ================================================================

SELECT '
-- Test Query: Top 5 Popular Classes
' AS '';

SELECT
    ct.id,
    ct.name,
    ct.description,
    ct.default_duration,
    ct.color,
    ct.image,
    COUNT(cb.id) as total_bookings
FROM class_types ct
LEFT JOIN class_schedules cs ON ct.id = cs.class_type_id
LEFT JOIN class_bookings cb ON cs.id = cb.schedule_id
    AND cb.status IN ('booked', 'attended')
WHERE ct.is_active = 1
GROUP BY ct.id, ct.name, ct.description, ct.default_duration,
         ct.color, ct.image
ORDER BY total_bookings DESC, ct.name ASC
LIMIT 5;

-- ================================================================
-- 5. Show summary
-- ================================================================

SELECT '
================================================================
Migration Complete!
================================================================

Changes Applied:
1. Added "image" column to class_types table (if not exists)
2. Created performance index idx_booking_schedule_status (if not exists)

Next Steps:
1. Backend API endpoint is ready with include_stats parameter
2. Frontend dashboard will consume popular classes data
3. Test the app to verify popular classes display correctly

Verification:
- Check that class_types.image column exists above
- Check that idx_booking_schedule_status index exists above
- Review test query results for popular classes ranking

================================================================
' AS 'Migration Summary';
