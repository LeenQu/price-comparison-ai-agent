CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    product_name VARCHAR(255),
    brand VARCHAR(255),
    category VARCHAR(100)
);

CREATE TABLE prices (
    id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(id),
    website VARCHAR(50),
    price DECIMAL(10,2),
    product_url TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);