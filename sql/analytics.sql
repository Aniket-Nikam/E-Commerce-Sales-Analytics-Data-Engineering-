-- Top categories by realized revenue.
SELECT category,
       round(SUM(net_revenue), 2) AS revenue,
       COUNT(DISTINCT order_id) AS orders
FROM warehouse.vw_sales_enriched
WHERE order_status IN ('Delivered', 'Shipped')
GROUP BY category
ORDER BY revenue DESC;

-- Customer dense rank within region.
WITH customer_revenue AS (
    SELECT region, customer_id, SUM(net_revenue) AS revenue
    FROM warehouse.vw_sales_enriched
    WHERE order_status IN ('Delivered', 'Shipped')
    GROUP BY region, customer_id
)
SELECT region, customer_id, round(revenue, 2) AS revenue,
       DENSE_RANK() OVER (PARTITION BY region ORDER BY revenue DESC) AS regional_rank
FROM customer_revenue
QUALIFY regional_rank <= 5
ORDER BY region, regional_rank;

-- Month-over-month growth with LAG.
SELECT * FROM warehouse.vw_monthly_growth ORDER BY sales_month;

-- Daily change with LAG and next-day comparison with LEAD.
SELECT sales_date, revenue,
       revenue - LAG(revenue) OVER (ORDER BY sales_date) AS change_from_previous_day,
       LEAD(revenue) OVER (ORDER BY sales_date) - revenue AS change_to_next_day
FROM warehouse.vw_daily_revenue
ORDER BY sales_date;

