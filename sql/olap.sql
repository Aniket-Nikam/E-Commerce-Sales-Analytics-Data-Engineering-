-- ROLLUP: category subtotals by region plus a grand total.
SELECT region, category, round(SUM(net_revenue), 2) AS revenue
FROM warehouse.vw_sales_enriched
WHERE order_status IN ('Delivered', 'Shipped')
GROUP BY ROLLUP (region, category)
ORDER BY region NULLS LAST, category NULLS LAST;

-- CUBE: all combinations of region and channel.
SELECT region, sales_channel, round(SUM(net_revenue), 2) AS revenue,
       GROUPING(region) AS all_regions,
       GROUPING(sales_channel) AS all_channels
FROM warehouse.vw_sales_enriched
WHERE order_status IN ('Delivered', 'Shipped')
GROUP BY CUBE (region, sales_channel)
ORDER BY all_regions, all_channels, revenue DESC;

-- GROUPING SETS: detail, both one-dimensional totals, and grand total.
SELECT region, category, round(SUM(net_revenue), 2) AS revenue
FROM warehouse.vw_sales_enriched
WHERE order_status IN ('Delivered', 'Shipped')
GROUP BY GROUPING SETS ((region, category), (region), (category), ());

