-- Audience definitions. Each is a view so the rules live in one reviewable place.

-- Regulars who have gone quiet: worth a "we miss you" offer before they churn.
CREATE OR REPLACE VIEW seg_lapsed_regulars AS
SELECT guest_id FROM guest_profiles
WHERE visits >= 4 AND days_since_last BETWEEN 21 AND 60;

-- Top 10% by spend.
CREATE OR REPLACE VIEW seg_high_value AS
SELECT guest_id FROM guest_profiles
WHERE spend >= (SELECT QUANTILE_CONT(spend, 0.9) FROM guest_profiles);

-- The audience loyalty programs can't see: frequent guests who never joined loyalty.
-- Only identity resolution (a receipt email linked to their card) makes them reachable.
CREATE OR REPLACE VIEW seg_non_loyalty_regulars AS
SELECT guest_id FROM guest_profiles
WHERE NOT is_member AND visits >= 3;

-- First visit in the last 14 days: the moment to win a second visit.
CREATE OR REPLACE VIEW seg_new_guests AS
SELECT guest_id FROM guest_profiles
WHERE DATE_DIFF('day', first_visit, (SELECT MAX(txn_date) FROM transactions)) <= 14;
