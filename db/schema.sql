-- Session-Based E-Commerce Recommender: MySQL events store
-- Source of truth for raw events. Bulk-loaded via load_data.sql,
-- append target for any future incremental data.

CREATE DATABASE IF NOT EXISTS product_recommender
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE product_recommender;

CREATE TABLE IF NOT EXISTS events (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_time    DATETIME     NOT NULL,
    event_type    VARCHAR(16)  NOT NULL,
    product_id    BIGINT       NOT NULL,
    category_id   BIGINT       NULL,
    category_code VARCHAR(255) NULL,
    brand         VARCHAR(100) NULL,
    price         DECIMAL(10, 2) NULL,
    user_id       BIGINT       NOT NULL,
    user_session  CHAR(36)     NOT NULL
) ENGINE = InnoDB;

-- Indexes are added AFTER the bulk load (see load_data.sql), not here —
-- building them during a 42M-row LOAD DATA INFILE is far slower than
-- loading first and indexing after.
