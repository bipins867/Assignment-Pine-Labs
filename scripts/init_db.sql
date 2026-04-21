-- Initialize databases for app and tests
-- This runs automatically on first MySQL container startup

CREATE DATABASE IF NOT EXISTS payment_db;
CREATE DATABASE IF NOT EXISTS payment_test_db;

-- Grant privileges on both databases to the app user
GRANT ALL PRIVILEGES ON payment_db.* TO 'payment_user'@'%';
GRANT ALL PRIVILEGES ON payment_test_db.* TO 'payment_user'@'%';
FLUSH PRIVILEGES;
