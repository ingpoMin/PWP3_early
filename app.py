from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
import os
import MySQLdb.cursors

# Load config dari .env
load_dotenv()

app = Flask(__name__)

# Config Database
app.config['MYSQL_HOST'] = os.getenv('DB_HOST')
app.config['MYSQL_USER'] = os.getenv('DB_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('DB_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('DB_NAME')
app.secret_key = os.getenv('SECRET_KEY')

mysql = MySQL(app)
bcrypt = Bcrypt(app)

# --- ROUTES ---

@app.route('/')
def home():
    if 'loggedin' in session:
        return redirect(url_for('feed'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Form tidak lengkap', 'danger')
            return render_template('login.html')

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(
            'SELECT * FROM users WHERE username = %s',
            (username,)
        )
        account = cursor.fetchone()

        if account and bcrypt.check_password_hash(account['password_hash'], password):
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            return redirect(url_for('feed'))

        flash('Username atau password salah', 'danger')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        username = request.form['username']
        # Nanti tambahkan input email di HTML ya
        email = request.form.get('email', f"{username}@example.com") 
        password = request.form['password']
        bio = request.form['bio']
        
        # Hash password biar aman
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        cursor = mysql.connection.cursor()
        try:
            cursor.execute('INSERT INTO users (full_name, username, email, password_hash, bio) VALUES (%s, %s, %s, %s, %s)', 
                           (full_name, username, email, hashed_password, bio))
            mysql.connection.commit()
            flash('Akun berhasil dibuat! Silakan login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Gagal daftar: {str(e)}', 'danger')
            
    return render_template('register.html')

@app.route('/feed')
def feed():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Ambil data user yang lagi login
    cursor.execute('SELECT * FROM users WHERE id = %s', (session['id'],))
    user = cursor.fetchone()
    
    # Ambil semua postingan (JOIN dengan tabel users biar ada nama & foto pengirim)
    # Kita urutkan dari yang terbaru (DESC)
    query_posts = """
        SELECT posts.*, users.username, users.full_name, users.profile_pic 
        FROM posts 
        JOIN users ON posts.user_id = users.id 
        ORDER BY posts.created_at DESC
    """
    cursor.execute(query_posts)
    posts = cursor.fetchall()
    
    return render_template('feed.html', user=user, posts=posts)

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)