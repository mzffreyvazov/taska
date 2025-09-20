import sqlite3
import os

# Get database path
db_path = os.path.join(os.path.dirname(os.getcwd()), 'contacts.db')
print(f"Database path: {db_path}")
print(f"Database exists: {os.path.exists(db_path)}")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Check if there are any deputy ministers
print("\n=== Checking for 'nazir' positions ===")
cur.execute("SELECT Ad, Soyad, Vəzifə FROM contacts WHERE lower(Vəzifə) LIKE '%nazir%' ORDER BY Vəzifə")
rows = cur.fetchall()

print(f'Found {len(rows)} positions containing "nazir":')
for row in rows:
    print(f'  {row[0]} {row[1]} - {row[2]}')

# Check for 'müavin' positions  
print("\n=== Checking for 'müavin' positions ===")
cur.execute("SELECT Ad, Soyad, Vəzifə FROM contacts WHERE lower(Vəzifə) LIKE '%müavin%' LIMIT 10")
rows2 = cur.fetchall()

print(f'First 10 positions containing "müavin":')
for row in rows2:
    print(f'  {row[0]} {row[1]} - {row[2]}')

conn.close()