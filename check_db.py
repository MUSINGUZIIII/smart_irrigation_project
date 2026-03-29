import os
import psycopg2
from django.conf import settings

print("=== Database Configuration ===")
print(f"DB_NAME: {os.getenv('DB_NAME')}")
print(f"DB_USER: {os.getenv('DB_USER')}")
print(f"DB_HOST: {os.getenv('DB_HOST')}")

try:
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT', '5432')
    )
    print("✅ Database connection successful!")
    conn.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
