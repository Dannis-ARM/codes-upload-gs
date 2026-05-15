SELECT
  database_name,
  ROUND(disk_used / 1024 / 1024 / 1024, 3) AS disk_gb,
  ROUND(disk_used * 100 / (SELECT SUM(disk_used) FROM information_schema.mv_database_storage_usage), 2) AS disk_pct
FROM information_schema.mv_database_storage_usage
ORDER BY disk_gb DESC;