CREATE OR REPLACE VIEW warehouse.vw_sales_enriched AS
SELECT
    f.order_date, f.order_id, f.line_id,
    c.customer_id, c.customer_segment, c.region,
    f.sales_channel,
    p.product_id, p.product_name, p.category,
    f.quantity, f.unit_price, f.discount_pct,
    f.gross_amount, f.net_revenue,
    f.payment_method, f.order_status, f.shipping_days
FROM warehouse.fact_sales f
JOIN warehouse.dim_customer c USING (customer_key)
JOIN warehouse.dim_product p USING (product_key);

CREATE OR REPLACE VIEW warehouse.vw_daily_revenue AS
SELECT order_date::DATE AS sales_date,
       round(SUM(CASE WHEN order_status IN ('Delivered', 'Shipped') THEN net_revenue ELSE 0 END), 2) AS revenue,
       COUNT(DISTINCT order_id) AS orders,
       COUNT(DISTINCT customer_id) AS customers
FROM warehouse.vw_sales_enriched
GROUP BY sales_date;

CREATE OR REPLACE VIEW warehouse.vw_monthly_growth AS
WITH monthly AS (
    SELECT date_trunc('month', order_date)::DATE AS sales_month,
           SUM(CASE WHEN order_status IN ('Delivered', 'Shipped') THEN net_revenue ELSE 0 END) AS revenue,
           COUNT(DISTINCT order_id) AS orders
    FROM warehouse.vw_sales_enriched
    GROUP BY sales_month
), compared AS (
    SELECT *, LAG(revenue) OVER (ORDER BY sales_month) AS previous_month_revenue
    FROM monthly
)
SELECT sales_month, round(revenue, 2) AS revenue, orders,
       round(previous_month_revenue, 2) AS previous_month_revenue,
       round(100.0 * (revenue - previous_month_revenue) / NULLIF(previous_month_revenue, 0), 2) AS growth_pct
FROM compared;

CREATE OR REPLACE VIEW warehouse.vw_repeat_customer_pct AS
WITH customer_orders AS (
    SELECT customer_id, COUNT(DISTINCT order_id) AS order_count
    FROM warehouse.vw_sales_enriched
    WHERE order_status IN ('Delivered', 'Shipped')
    GROUP BY customer_id
)
SELECT COUNT(*) AS purchasing_customers,
       COUNT_IF(order_count > 1) AS repeat_customers,
       round(100.0 * COUNT_IF(order_count > 1) / NULLIF(COUNT(*), 0), 2) AS repeat_customer_pct
FROM customer_orders;

