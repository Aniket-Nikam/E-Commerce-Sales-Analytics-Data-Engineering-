CREATE OR REPLACE TABLE warehouse.stg_orders AS
SELECT
    trim(line_id) AS line_id,
    trim(order_id) AS order_id,
    TRY_CAST(order_date AS TIMESTAMP) AS order_date,
    NULLIF(trim(customer_id), '') AS customer_id,
    CASE lower(trim(customer_segment))
        WHEN 'consumer' THEN 'Consumer'
        WHEN 'corporate' THEN 'Corporate'
        WHEN 'small business' THEN 'Small Business'
        ELSE 'Unknown'
    END AS customer_segment,
    CASE lower(trim(region))
        WHEN 'north' THEN 'North'
        WHEN 'south' THEN 'South'
        WHEN 'east' THEN 'East'
        WHEN 'west' THEN 'West'
        WHEN 'central' THEN 'Central'
        ELSE 'Unknown'
    END AS region,
    CASE lower(trim(sales_channel))
        WHEN 'web' THEN 'Web'
        WHEN 'mobile app' THEN 'Mobile App'
        WHEN 'marketplace' THEN 'Marketplace'
        ELSE 'Unknown'
    END AS sales_channel,
    trim(product_id) AS product_id,
    trim(product_name) AS product_name,
    upper(substr(trim(category), 1, 1)) || lower(substr(trim(category), 2)) AS category,
    TRY_CAST(quantity AS INTEGER) AS quantity,
    TRY_CAST(unit_price AS DOUBLE) AS unit_price,
    TRY_CAST(discount_pct AS DOUBLE) AS discount_pct,
    trim(payment_method) AS payment_method,
    upper(substr(trim(order_status), 1, 1)) || lower(substr(trim(order_status), 2)) AS order_status,
    TRY_CAST(shipping_days AS INTEGER) AS shipping_days
FROM warehouse.raw_orders
QUALIFY ROW_NUMBER() OVER (PARTITION BY trim(line_id) ORDER BY trim(line_id)) = 1;

CREATE OR REPLACE TABLE warehouse.rejected_orders AS
SELECT *,
    concat_ws('; ',
        CASE WHEN line_id IS NULL OR line_id = '' THEN 'missing line_id' END,
        CASE WHEN order_id IS NULL OR order_id = '' THEN 'missing order_id' END,
        CASE WHEN order_date IS NULL THEN 'invalid order_date' END,
        CASE WHEN customer_id IS NULL THEN 'missing customer_id' END,
        CASE WHEN product_id IS NULL OR product_id = '' THEN 'missing product_id' END,
        CASE WHEN quantity NOT BETWEEN 1 AND 20 OR quantity IS NULL THEN 'invalid quantity' END,
        CASE WHEN unit_price <= 0 OR unit_price IS NULL THEN 'invalid unit_price' END,
        CASE WHEN discount_pct NOT BETWEEN 0 AND 80 OR discount_pct IS NULL THEN 'invalid discount' END
    ) AS rejection_reason
FROM warehouse.stg_orders
WHERE line_id IS NULL OR line_id = ''
   OR order_id IS NULL OR order_id = ''
   OR order_date IS NULL
   OR customer_id IS NULL
   OR product_id IS NULL OR product_id = ''
   OR quantity NOT BETWEEN 1 AND 20 OR quantity IS NULL
   OR unit_price <= 0 OR unit_price IS NULL
   OR discount_pct NOT BETWEEN 0 AND 80 OR discount_pct IS NULL;

CREATE OR REPLACE TABLE warehouse.dim_product AS
SELECT ROW_NUMBER() OVER (ORDER BY product_id)::INTEGER AS product_key,
       product_id, any_value(product_name) AS product_name,
       any_value(category) AS category
FROM warehouse.stg_orders
WHERE product_id IS NOT NULL AND product_id <> ''
GROUP BY product_id;

CREATE OR REPLACE TABLE warehouse.dim_customer AS
SELECT ROW_NUMBER() OVER (ORDER BY customer_id)::INTEGER AS customer_key,
       customer_id, any_value(customer_segment) AS customer_segment,
       any_value(region) AS region
FROM warehouse.stg_orders
WHERE customer_id IS NOT NULL
GROUP BY customer_id;

CREATE OR REPLACE TABLE warehouse.dim_date AS
SELECT CAST(strftime(d, '%Y%m%d') AS INTEGER) AS date_key,
       d::DATE AS full_date,
       year(d)::INTEGER AS year,
       quarter(d)::INTEGER AS quarter,
       month(d)::INTEGER AS month,
       monthname(d) AS month_name,
       week(d)::INTEGER AS week_of_year,
       dayofweek(d)::INTEGER AS day_of_week
FROM range(
    (SELECT min(order_date)::DATE FROM warehouse.stg_orders WHERE order_date IS NOT NULL),
    (SELECT max(order_date)::DATE + INTERVAL 1 DAY FROM warehouse.stg_orders WHERE order_date IS NOT NULL),
    INTERVAL 1 DAY
) dates(d);

CREATE OR REPLACE TABLE warehouse.fact_sales AS
SELECT
    s.line_id,
    s.order_id,
    CAST(strftime(s.order_date, '%Y%m%d') AS INTEGER) AS date_key,
    s.order_date,
    c.customer_key,
    p.product_key,
    s.sales_channel,
    s.quantity,
    round(s.unit_price, 2) AS unit_price,
    round(s.discount_pct, 2) AS discount_pct,
    round(s.quantity * s.unit_price, 2) AS gross_amount,
    round(s.quantity * s.unit_price * (1 - s.discount_pct / 100.0), 2) AS net_revenue,
    s.payment_method,
    s.order_status,
    s.shipping_days
FROM warehouse.stg_orders s
JOIN warehouse.dim_customer c USING (customer_id)
JOIN warehouse.dim_product p USING (product_id)
WHERE s.line_id IS NOT NULL AND s.line_id <> ''
  AND s.order_id IS NOT NULL AND s.order_id <> ''
  AND s.order_date IS NOT NULL
  AND s.customer_id IS NOT NULL
  AND s.quantity BETWEEN 1 AND 20
  AND s.unit_price > 0
  AND s.discount_pct BETWEEN 0 AND 80;

CREATE INDEX IF NOT EXISTS idx_fact_date ON warehouse.fact_sales(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_customer ON warehouse.fact_sales(customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_product ON warehouse.fact_sales(product_key);
