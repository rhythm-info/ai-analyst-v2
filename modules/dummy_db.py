import psycopg2
import random
import datetime
from faker import Faker

# DB connection config (change if needed)
DB_CONFIG = {
    "dbname": "test_db",
    "user": "postgres",
    "password": "test",
    "host": "localhost",
    "port": 5433
}

fake = Faker()

def create_tables(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            dept_id SERIAL PRIMARY KEY,
            dept_name VARCHAR(100),
            location VARCHAR(100)
        );
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            emp_id SERIAL PRIMARY KEY,
            first_name VARCHAR(50),
            last_name VARCHAR(50),
            email VARCHAR(100),
            hire_date DATE,
            salary NUMERIC(10, 2),
            dept_id INT REFERENCES departments(dept_id)
        );
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            project_id SERIAL PRIMARY KEY,
            project_name VARCHAR(100),
            start_date DATE,
            end_date DATE,
            budget NUMERIC(12, 2),
            dept_id INT REFERENCES departments(dept_id)
        );
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            sale_id SERIAL PRIMARY KEY,
            emp_id INT REFERENCES employees(emp_id),
            sale_date DATE,
            amount NUMERIC(10, 2),
            product VARCHAR(100)
        );
    """)

def populate_departments(cur, n=5):
    locations = ["New York", "London", "Berlin", "Tokyo", "Bangalore"]
    for _ in range(n):
        cur.execute(
            "INSERT INTO departments (dept_name, location) VALUES (%s, %s)",
            (fake.company(), random.choice(locations))
        )

def populate_employees(cur, n=50):
    for _ in range(n):
        cur.execute(
            """INSERT INTO employees (first_name, last_name, email, hire_date, salary, dept_id)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                fake.first_name(),
                fake.last_name(),
                fake.email(),
                fake.date_between(start_date="-5y", end_date="today"),
                round(random.uniform(30000, 120000), 2),
                random.randint(1, 5)
            )
        )

def populate_projects(cur, n=10):
    for _ in range(n):
        start = fake.date_between(start_date="-3y", end_date="today")
        end = start + datetime.timedelta(days=random.randint(30, 365))
        cur.execute(
            """INSERT INTO projects (project_name, start_date, end_date, budget, dept_id)
               VALUES (%s, %s, %s, %s, %s)""",
            (
                fake.catch_phrase(),
                start,
                end,
                round(random.uniform(10000, 500000), 2),
                random.randint(1, 5)
            )
        )

def populate_sales(cur, n=200):
    products = ["Laptop", "Phone", "Tablet", "Monitor", "Keyboard", "Headphones"]
    for _ in range(n):
        cur.execute(
            """INSERT INTO sales (emp_id, sale_date, amount, product)
               VALUES (%s, %s, %s, %s)""",
            (
                random.randint(1, 50),
                fake.date_between(start_date="-2y", end_date="today"),
                round(random.uniform(100, 2000), 2),
                random.choice(products)
            )
        )

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    create_tables(cur)
    populate_departments(cur)
    populate_employees(cur)
    populate_projects(cur)
    populate_sales(cur)
    
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database populated successfully!")

if __name__ == "__main__":
    main()
