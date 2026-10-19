PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price_coins INTEGER NOT NULL CHECK (price_coins >= 0),
    user_limit INTEGER NOT NULL CHECK (user_limit >= 1)
);

CREATE TABLE IF NOT EXISTS stock (
    product_id TEXT NOT NULL REFERENCES products(id),
    size TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    PRIMARY KEY (product_id, size)
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    coins INTEGER NOT NULL CHECK (coins >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    size TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 1),
    total_price INTEGER NOT NULL CHECK (total_price >= 0),
    status TEXT NOT NULL CHECK (status IN ('created', 'cancelled', 'picked_up'))
);

INSERT OR IGNORE INTO products (id, name, price_coins, user_limit) VALUES
    ('hoodie', 'Худи', 500, 1),
    ('tshirt', 'Футболка', 250, 2),
    ('stickers', 'Стикеры', 50, 5),
    ('bottle', 'Бутылка', 150, 2),
    ('tote', 'Шоппер', 100, 3);

INSERT OR IGNORE INTO stock (product_id, size, quantity) VALUES
    ('hoodie', 'S', 3),
    ('hoodie', 'M', 5),
    ('hoodie', 'L', 2),
    ('hoodie', 'XL', 1),
    ('tshirt', 'S', 10),
    ('tshirt', 'M', 8),
    ('tshirt', 'L', 6),
    ('tshirt', 'XL', 4),
    ('stickers', 'one_size', 50),
    ('bottle', 'one_size', 12),
    ('tote', 'one_size', 20);

INSERT OR IGNORE INTO users (id, coins) VALUES
    ('student_01', 1000),
    ('student_02', 300),
    ('student_poor', 20);
