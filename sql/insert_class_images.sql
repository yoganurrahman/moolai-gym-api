-- ================================================================
-- Insert Sample Images for Class Types
-- Description: Add sample images for popular classes feature
-- Date: 2026-02-06
-- ================================================================

USE moolai_gym;

-- Insert sample images for class types
-- Note: Ganti file_path dengan path image yang sebenarnya di server Anda

INSERT INTO images
    (category, reference_id, file_path, title, description, sort_order, platform, deep_link, created_at)
VALUES
    -- Yoga (class_type_id = 1)
    ('class', 1, 'uploads/images/class/yoga.jpg', 'Yoga Class', 'Yoga class image', 1, 'all', NULL, NOW()),

    -- Spinning (class_type_id = 2)
    ('class', 2, 'uploads/images/class/spinning.jpg', 'Spinning Class', 'Spinning class image', 1, 'all', NULL, NOW()),

    -- Zumba (class_type_id = 3)
    ('class', 3, 'uploads/images/class/zumba.jpg', 'Zumba Class', 'Zumba class image', 1, 'all', NULL, NOW()),

    -- Pilates (class_type_id = 4)
    ('class', 4, 'uploads/images/class/pilates.jpg', 'Pilates Class', 'Pilates class image', 1, 'all', NULL, NOW()),

    -- HIIT (class_type_id = 5)
    ('class', 5, 'uploads/images/class/hiit.jpg', 'HIIT Class', 'HIIT class image', 1, 'all', NULL, NOW()),

    -- Boxing (class_type_id = 6)
    ('class', 6, 'uploads/images/class/boxing.jpg', 'Boxing Class', 'Boxing class image', 1, 'all', NULL, NOW()),

    -- Body Combat (class_type_id = 7)
    ('class', 7, 'uploads/images/class/combat.jpg', 'Body Combat Class', 'Body Combat class image', 1, 'all', NULL, NOW())
ON DUPLICATE KEY UPDATE
    file_path = VALUES(file_path),
    title = VALUES(title),
    description = VALUES(description),
    sort_order = VALUES(sort_order);

-- Verify the inserts
SELECT
    i.id,
    i.category,
    i.reference_id,
    ct.name as class_name,
    i.file_path,
    i.sort_order
FROM images i
LEFT JOIN class_types ct ON i.reference_id = ct.id
WHERE i.category = 'class'
ORDER BY i.reference_id, i.sort_order;
