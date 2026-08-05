-- Bulk-load 2019-Oct.csv into the events table via LOAD DATA INFILE.
-- Row-by-row INSERT would take hours at ~42M rows; this takes minutes.
--
-- Prerequisites:
--   1. Run schema.sql first.
--   2. secure_file_priv must permit reading from the CSV's directory, OR
--      run this via `mysql --local-infile=1` and use LOAD DATA LOCAL INFILE
--      instead (uncomment the LOCAL variant below if your server restricts
--      secure_file_priv).
--   3. Adjust the file path to match where 2019-Oct.csv actually lives.

USE product_recommender;

SET GLOBAL local_infile = 1;

LOAD DATA LOCAL INFILE 'D:/Product Recommendation project/2019-Oct.csv'
INTO TABLE events
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(@event_time, event_type, product_id, category_id, @category_code, @brand, price, user_id, user_session)
SET
    -- event_time in the CSV looks like "2019-10-01 00:00:00 UTC" —
    -- strip the trailing " UTC" before parsing as DATETIME.
    event_time = STR_TO_DATE(SUBSTRING_INDEX(@event_time, ' UTC', 1), '%Y-%m-%d %H:%i:%s'),
    category_code = NULLIF(@category_code, ''),
    brand = NULLIF(@brand, '');

-- Indexes added post-load for faster bulk insert.
CREATE INDEX idx_events_user_session ON events (user_session);
CREATE INDEX idx_events_event_time   ON events (event_time);
CREATE INDEX idx_events_product_id   ON events (product_id);

-- Sanity checks after load.
SELECT COUNT(*) AS total_rows FROM events;
SELECT event_type, COUNT(*) FROM events GROUP BY event_type;
SELECT MIN(event_time), MAX(event_time) FROM events;
