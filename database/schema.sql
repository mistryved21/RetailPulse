-- RetailPulse PostgreSQL Schema & Seed Data
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS suppliers;

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category_id INTEGER REFERENCES categories(id) NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    cost NUMERIC(10, 2) NOT NULL,
    sku VARCHAR(100) UNIQUE NOT NULL,
    brand VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    city VARCHAR(100),
    state VARCHAR(100),
    registration_date DATE,
    segment VARCHAR(50)
);

CREATE TABLE sales (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) NOT NULL,
    customer_id INTEGER REFERENCES customers(id) NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,
    sale_date TIMESTAMP NOT NULL,
    payment_method VARCHAR(50),
    region VARCHAR(100)
);

CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) NOT NULL UNIQUE,
    current_stock INTEGER NOT NULL DEFAULT 0,
    reorder_level INTEGER NOT NULL DEFAULT 10,
    max_stock INTEGER NOT NULL DEFAULT 100,
    warehouse_location VARCHAR(100),
    last_restocked TIMESTAMP
);

CREATE TABLE suppliers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    contact_email VARCHAR(255),
    phone VARCHAR(20),
    city VARCHAR(100),
    country VARCHAR(100),
    rating FLOAT
);

-- Categories
INSERT INTO categories (name, description) VALUES
('Electronics', 'Gadgets, appliances and accessories'),
('Clothing', 'Men and women apparel'),
('Food & Beverages', 'Groceries and drinks'),
('Home & Kitchen', 'Furniture and kitchen appliances'),
('Sports', 'Sports equipment and apparel'),
('Books', 'Fiction and Non-fiction'),
('Beauty', 'Cosmetics and skincare'),
('Toys', 'Kids toys and games');

-- Products (50 items)
WITH cat AS (SELECT id, name FROM categories)
INSERT INTO products (name, category_id, price, cost, sku, brand)
SELECT 
    'Product ' || i,
    (SELECT id FROM categories ORDER BY random() LIMIT 1),
    random() * 1995 + 5,
    (random() * 1995 + 5) * 0.7,
    'SKU-' || lpad(i::text, 4, '0'),
    'Brand ' || chr(65 + (i % 5))
FROM generate_series(1, 50) i;

-- Customers (100 customers)
INSERT INTO customers (name, email, city, state, registration_date, segment)
SELECT 
    'Customer ' || i,
    'customer' || i || '@example.com',
    (ARRAY['Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Hyderabad'])[floor(random() * 5 + 1)],
    (ARRAY['Maharashtra', 'Delhi', 'Karnataka', 'Tamil Nadu', 'Telangana'])[floor(random() * 5 + 1)],
    DATE '2022-01-01' + (random() * 1000)::integer,
    (ARRAY['Premium', 'Regular', 'Budget'])[floor(random() * 3 + 1)]
FROM generate_series(1, 100) i;

-- Sales (500 records)
INSERT INTO sales (product_id, customer_id, quantity, unit_price, total_amount, sale_date, payment_method, region)
SELECT 
    p.id,
    c.id,
    floor(random() * 5 + 1)::integer as quantity,
    p.price as unit_price,
    (floor(random() * 5 + 1) * p.price) as total_amount,
    TIMESTAMP '2023-01-01 00:00:00' + random() * (TIMESTAMP '2025-06-30 23:59:59' - TIMESTAMP '2023-01-01 00:00:00') as sale_date,
    (ARRAY['Cash', 'Credit Card', 'Debit Card', 'UPI', 'Net Banking'])[floor(random() * 5 + 1)],
    (ARRAY['North', 'South', 'East', 'West'])[floor(random() * 4 + 1)]
FROM generate_series(1, 500) i
CROSS JOIN LATERAL (SELECT id, price FROM products ORDER BY random() LIMIT 1) p
CROSS JOIN LATERAL (SELECT id FROM customers ORDER BY random() LIMIT 1) c;

-- Inventory (50 records matching products)
INSERT INTO inventory (product_id, current_stock, reorder_level, max_stock, warehouse_location, last_restocked)
SELECT 
    id,
    floor(random() * 100)::integer,
    floor(random() * 20 + 5)::integer,
    150,
    (ARRAY['Zone A', 'Zone B', 'Zone C'])[floor(random() * 3 + 1)],
    TIMESTAMP '2024-01-01 00:00:00' + random() * (TIMESTAMP '2025-06-30 23:59:59' - TIMESTAMP '2024-01-01 00:00:00')
FROM products;

-- Suppliers (20 records)
INSERT INTO suppliers (name, contact_email, phone, city, country, rating)
SELECT 
    'Supplier ' || i,
    'contact@supplier' || i || '.com',
    '+91-9' || lpad((floor(random() * 1000000000))::text, 9, '0'),
    (ARRAY['Mumbai', 'Shenzhen', 'Bangalore', 'Hanoi', 'Taipei'])[floor(random() * 5 + 1)],
    (ARRAY['India', 'China', 'India', 'Vietnam', 'Taiwan'])[floor(random() * 5 + 1)],
    (random() * 2 + 3)::numeric(2,1)
FROM generate_series(1, 20) i;
