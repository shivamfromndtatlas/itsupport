CREATE DATABASE IF NOT EXISTS it_support_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS test_it_support_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'it_support_user'@'localhost' IDENTIFIED BY 'ITSupport@2024';
GRANT ALL PRIVILEGES ON it_support_db.* TO 'it_support_user'@'localhost';
GRANT ALL PRIVILEGES ON test_it_support_db.* TO 'it_support_user'@'localhost';
FLUSH PRIVILEGES;