from app import create_app

# Panggil fungsi create_app untuk inisialisasi aplikasi
app = create_app()

if __name__ == '__main__':
    # Jalankan aplikasi dengan mode debug aktif
    app.run(debug=True)