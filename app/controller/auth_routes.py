from flask import Blueprint, request, redirect, url_for, session, flash
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
import bcrypt
from .. import mysql, bcrypt

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def home():
    if 'loggedin' in session:
        return redirect(url_for('feed.feed'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Form tidak lengkap', 'danger')
            return render_template('login.html')

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        account = cursor.fetchone()

        if account and bcrypt.check_password_hash(account['password_hash'], password):
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            return redirect(url_for('feed.feed'))

        flash('Username atau password salah', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        username = request.form['username']
        email = request.form.get('email', f"{username}@example.com") 
        password = request.form['password']
        bio = request.form['bio']
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        cursor = mysql.connection.cursor()
        try:
            cursor.execute('INSERT INTO users (full_name, username, email, password_hash, bio) VALUES (%s, %s, %s, %s, %s)', 
                           (full_name, username, email, hashed_password, bio))
            mysql.connection.commit()
            flash('Akun berhasil dibuat! Silakan login.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Gagal daftar: {str(e)}', 'danger')
            
    return render_template('register.html')