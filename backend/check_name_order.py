import sqlite3
import os

# Get database path
db_path = os.path.join(os.path.dirname(os.getcwd()), 'contacts.db')
print(f"Database path: {db_path}")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Check for Anar Axundov entries
print("\n=== Searching for Anar/Axundov ===")
cur.execute("SELECT Ad, Soyad, Vəzifə FROM contacts WHERE Ad LIKE '%Anar%' OR Soyad LIKE '%Axundov%' OR Ad LIKE '%Axundov%' OR Soyad LIKE '%Anar%'")
rows = cur.fetchall()

print(f'Found {len(rows)} entries:')
for row in rows:
    print(f'  Ad: {row[0]} | Soyad: {row[1]} | Vəzifə: {row[2]}')

# Check first 10 entries to see the structure
print("\n=== First 10 database entries ===")
cur.execute("SELECT Ad, Soyad, Vəzifə FROM contacts LIMIT 10")
sample_rows = cur.fetchall()

for i, row in enumerate(sample_rows, 1):
    print(f'{i:2d}. Ad: "{row[0]}" | Soyad: "{row[1]}" | Vəzifə: "{row[2]}"')

conn.close()