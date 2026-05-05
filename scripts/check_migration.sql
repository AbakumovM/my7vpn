-- =============================================================
-- Проверка статуса миграции: старая модель → user_subscriptions
-- =============================================================

-- 1. Сводка: сколько юзеров на старой, новой, обеих моделях
SELECT
    COUNT(*) FILTER (WHERE has_old AND NOT has_new)     AS only_old,
    COUNT(*) FILTER (WHERE has_new AND NOT has_old)     AS only_new,
    COUNT(*) FILTER (WHERE has_old AND has_new)         AS both_migrated,
    COUNT(*)                                            AS total
FROM (
    SELECT
        u.id,
        EXISTS (
            SELECT 1 FROM devices d
            JOIN subscriptions s ON s.device_id = d.id
            WHERE d.user_id = u.id
        ) AS has_old,
        EXISTS (
            SELECT 1 FROM user_subscriptions us
            WHERE us.user_id = u.id
        ) AS has_new
    FROM users u
) t;


-- 2. Юзеры, которые ещё на старой модели (активная старая, нет новой)
--    Это те, кто ещё не продлял подписку после миграции
SELECT
    u.telegram_id,
    u.username,
    d.device_name,
    s.plan        AS plan_months,
    s.start_date,
    s.end_date,
    s.is_active,
    s.end_date > NOW() AS sub_still_active
FROM users u
JOIN devices d ON d.user_id = u.id
JOIN subscriptions s ON s.device_id = d.id
WHERE s.is_active = true
  AND NOT EXISTS (
      SELECT 1 FROM user_subscriptions us WHERE us.user_id = u.id
  )
ORDER BY s.end_date DESC;


-- 3. Юзеры, у которых есть обе записи — проверяем расхождение дат
--    В норме: end_date в user_subscriptions >= end_date в subscriptions
SELECT
    u.telegram_id,
    u.username,
    s.end_date      AS old_end_date,
    us.end_date     AS new_end_date,
    us.device_limit AS new_device_limit,
    CASE
        WHEN us.end_date >= s.end_date THEN 'OK'
        ELSE 'РАСХОЖДЕНИЕ — новая < старой'
    END AS status
FROM users u
JOIN devices d ON d.user_id = u.id
JOIN subscriptions s ON s.device_id = d.id
JOIN user_subscriptions us ON us.user_id = u.id
WHERE s.is_active = true
  AND us.is_active = true
ORDER BY status DESC, u.telegram_id;


-- 4. Юзеры с подозрительно далёкой end_date (больше 13 месяцев от сегодня)
SELECT
    u.telegram_id,
    u.username,
    us.plan,
    us.start_date,
    us.end_date,
    ROUND(EXTRACT(EPOCH FROM (us.end_date - NOW())) / 2592000) AS months_left
FROM user_subscriptions us
JOIN users u ON u.id = us.user_id
WHERE us.is_active = true
  AND us.end_date > NOW() + INTERVAL '13 months'
ORDER BY us.end_date DESC;


-- 5. То же самое для старой модели
SELECT
    u.telegram_id,
    u.username,
    d.device_name,
    s.plan,
    s.end_date,
    ROUND(EXTRACT(EPOCH FROM (s.end_date - NOW())) / 2592000) AS months_left
FROM subscriptions s
JOIN devices d ON d.id = s.device_id
JOIN users u ON u.id = d.user_id
WHERE s.is_active = true
  AND s.end_date > NOW() + INTERVAL '13 months'
ORDER BY s.end_date DESC;
