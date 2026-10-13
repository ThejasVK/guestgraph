-- One row per resolved guest. Written in plain ANSI-style SQL so it ports to Snowflake
-- with minimal changes (DATE_DIFF -> DATEDIFF, MODE() -> MODE()).
CREATE OR REPLACE TABLE guest_profiles AS
WITH tx AS (
    SELECT t.*, g.guest_id
    FROM transactions t
    JOIN txn_guest g USING (txn_id)
    WHERE g.guest_id IS NOT NULL
),
agg AS (
    SELECT
        guest_id,
        COUNT(*)                                AS visits,
        ROUND(SUM(amount), 2)                   AS spend,
        ROUND(AVG(amount), 2)                   AS avg_ticket,
        MIN(txn_date)                           AS first_visit,
        MAX(txn_date)                           AS last_visit,
        MODE(store_id)                          AS top_store,
        COUNT(DISTINCT store_id)                AS stores_visited,
        SUM(CASE WHEN member_id IS NOT NULL THEN 1 ELSE 0 END) AS loyalty_scans
    FROM tx
    GROUP BY guest_id
)
SELECT
    a.*,
    DATE_DIFF('day', a.last_visit, (SELECT MAX(txn_date) FROM transactions)) AS days_since_last,
    i.is_member,
    i.has_email,
    i.has_phone,
    (i.has_email OR i.has_phone)            AS reachable
FROM agg a
JOIN guest_identity i USING (guest_id);
