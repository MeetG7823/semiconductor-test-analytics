-- QUERY: overall
SELECT COUNT(*) AS devices_tested,
       SUM(test_result = 'PASS') AS devices_passed,
       SUM(test_result = 'FAIL') AS devices_failed,
       ROUND(100.0 * SUM(test_result = 'PASS') / COUNT(*), 2) AS yield_percent
FROM tests;

-- QUERY: lot_yield
SELECT lot_id, COUNT(*) AS devices_tested, SUM(test_result = 'PASS') AS devices_passed,
       ROUND(100.0 * SUM(test_result = 'PASS') / COUNT(*), 2) AS yield_percent,
       ROUND(AVG(leakage_ua), 3) AS mean_leakage_ua
FROM tests GROUP BY lot_id ORDER BY lot_id;

-- QUERY: wafer_yield
SELECT wafer_id, lot_id, COUNT(*) AS devices_tested,
       ROUND(100.0 * SUM(test_result = 'PASS') / COUNT(*), 2) AS yield_percent
FROM tests GROUP BY wafer_id, lot_id ORDER BY yield_percent;

-- QUERY: condition_yield
SELECT lot_id, temperature_c, voltage_v, COUNT(*) AS devices_tested,
       ROUND(100.0 * SUM(test_result = 'PASS') / COUNT(*), 2) AS yield_percent
FROM tests GROUP BY lot_id, temperature_c, voltage_v ORDER BY lot_id, temperature_c, voltage_v;

-- QUERY: failure_counts
SELECT 'HIGH_LEAKAGE' AS failure_mode, COUNT(*) AS devices FROM tests WHERE failure_modes LIKE '%HIGH_LEAKAGE%'
UNION ALL
SELECT 'OVER_CURRENT', COUNT(*) FROM tests WHERE failure_modes LIKE '%OVER_CURRENT%'
UNION ALL
SELECT 'LOW_GAIN', COUNT(*) FROM tests WHERE failure_modes LIKE '%LOW_GAIN%';
