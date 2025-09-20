import sqlite3
import os

# Get database path
db_path = os.path.join(os.path.dirname(os.getcwd()), 'contacts.db')
print(f"Database path: {db_path}")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Check entries with "oğlu" in Soyad column
print("\n=== Entries with 'oğlu' in Soyad column ===")
cur.execute("SELECT Ad, Soyad, Vəzifə FROM contacts WHERE Soyad LIKE '%oğlu%' ORDER BY Soyad")
rows = cur.fetchall()

print(f'Found {len(rows)} entries with "oğlu" in surname:')
for i, row in enumerate(rows, 1):
    print(f'{i:2d}. {row[0]} {row[1]} - {row[2]}')

# Also check entries with "qızı" (daughter of)
print("\n=== Entries with 'qızı' in Soyad column ===")
cur.execute("SELECT Ad, Soyad, Vəzifə FROM contacts WHERE Soyad LIKE '%qızı%' ORDER BY Soyad")
rows2 = cur.fetchall()

print(f'Found {len(rows2)} entries with "qızı" in surname:')
for i, row in enumerate(rows2, 1):
    print(f'{i:2d}. {row[0]} {row[1]} - {row[2]}')

# Check some sample surnames to see the pattern
print("\n=== Sample surnames (first 20) ===")
cur.execute("SELECT DISTINCT Soyad FROM contacts WHERE Soyad IS NOT NULL ORDER BY Soyad LIMIT 20")
sample_rows = cur.fetchall()

for i, row in enumerate(sample_rows, 1):
    print(f'{i:2d}. {row[0]}')

conn.close()