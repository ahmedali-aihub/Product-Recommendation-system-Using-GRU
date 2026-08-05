-- Storefront v1: product catalog + session-based cart.
-- Product data is DERIVED, not sourced -- the `events` table has no product
-- names or images, only product_id/category_code/brand/price. `products`
-- is populated by src/data/build_product_catalog.py, not by hand, and is
-- safe to re-run (idempotent upsert) after any fresh `events` load.

USE product_recommender;

CREATE TABLE IF NOT EXISTS products (
    product_id     BIGINT        PRIMARY KEY,
    category_code  VARCHAR(255)  NULL,       -- raw dot-hierarchy from events, may be NULL
    category_top   VARCHAR(100)  NULL,       -- first dot segment, e.g. 'electronics'
    category_leaf  VARCHAR(100)  NULL,       -- last dot segment, e.g. 'smartphone'
    brand          VARCHAR(100)  NULL,
    price          DECIMAL(10,2) NULL,
    display_name   VARCHAR(255)  NOT NULL,   -- generated from category/brand, see build_product_catalog.py
    image_ref      VARCHAR(100)  NOT NULL,   -- icon key for the frontend; 'generic' fallback
    event_count    BIGINT        NOT NULL DEFAULT 0,  -- popularity signal, used as default sort
    updated_at     TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_products_category_top (category_top),
    KEY idx_products_brand (brand)
) ENGINE = InnoDB;

-- No accounts/login in v1 -- a cart is identified by a client-generated
-- UUID (stored in the browser's localStorage), not a logged-in user.
CREATE TABLE IF NOT EXISTS carts (
    cart_id    CHAR(36)  PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS cart_items (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    cart_id     CHAR(36) NOT NULL,
    product_id  BIGINT   NOT NULL,
    quantity    INT      NOT NULL DEFAULT 1,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_cart_product (cart_id, product_id),
    CONSTRAINT fk_cart_items_cart    FOREIGN KEY (cart_id)    REFERENCES carts(cart_id) ON DELETE CASCADE,
    CONSTRAINT fk_cart_items_product FOREIGN KEY (product_id) REFERENCES products(product_id)
) ENGINE = InnoDB;
-- quantity is never stored as 0 -- the API deletes the row instead.
