import sqlite3

conn = sqlite3.connect('instance/database.db')
cursor = conn.cursor()

# Jalankan query SELECT pada tabel yang ingin Anda ketahui nama kolomnya
cursor.execute("SELECT * FROM detector_log;")

# Ambil nama-nama kolom dari cursor.description
# cursor.description akan mengembalikan list of tuples,
# di mana elemen pertama dari setiap tuple adalah nama kolom
column_names = [description[0] for description in cursor.description]

print("Nama Kolom:", column_names)

#Optional: Untuk melihat data juga
print("Data:", cursor.fetchall())

cursor.close()
conn.close() # Penting: Selalu tutup koneksi