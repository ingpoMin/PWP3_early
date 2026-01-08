from flask import Blueprint, request, redirect, url_for, session, flash
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from flask_mysqldb import MySQL
import os
import time
import MySQLdb.cursors
from app import mysql, allowed_file
from flask_bcrypt import Bcrypt
from .. import mysql


feed_bp = Blueprint('feed', __name__)

app = Flask(__name__)

@feed_bp.route('/feed')
def feed():
    if 'loggedin' not in session:
        return redirect(url_for('auth.login'))
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    cursor.execute('SELECT * FROM users WHERE id = %s', (session['id'],))
    user = cursor.fetchone()
    
    query_posts = """
        SELECT 
            posts.*, 
            users.username, 
            users.full_name, 
            users.profile_pic,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS like_count,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id AND likes.user_id = %s) AS user_has_liked
        FROM posts 
        JOIN users ON posts.user_id = users.id 
        ORDER BY posts.created_at DESC
    """
    cursor.execute(query_posts, (session['id'],))
    posts = cursor.fetchall()

    query_notif = """
        SELECT 
            notifications.*, 
            users.username AS sender_name, 
            users.profile_pic AS sender_pic 
        FROM notifications 
        JOIN users ON notifications.sender_id = users.id
        WHERE notifications.recipient_id = %s 
        ORDER BY notifications.timestamp DESC 
        LIMIT 10
    """
    cursor.execute(query_notif, (session['id'],))
    notifications = cursor.fetchall()

    query_suggestions = """
        SELECT * FROM users 
        WHERE id != %s 
        AND id NOT IN (
            SELECT followed_id FROM follows WHERE follower_id = %s
        ) 
        ORDER BY RAND() 
        LIMIT 3
    """
    cursor.execute(query_suggestions, (session['id'], session['id']))
    suggestions = cursor.fetchall()
    
    cursor.close()
    return render_template('feed.html', user=user, posts=posts, notifications=notifications, suggestions=suggestions)

@feed_bp.route('/my_profile')
def my_profile():
    if 'loggedin' in session:
        return redirect(url_for('feed.profile', username=session['username']))
    return redirect(url_for('auth.login'))

@feed_bp.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'loggedin' not in session:
        return redirect(url_for('authlogin'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        full_name = request.form['full_name']
        username = request.form['username']
        bio = request.form['bio']
        
        cursor.execute('SELECT * FROM users WHERE username = %s AND id != %s', (username, session['id']))
        if cursor.fetchone():
            flash('Username sudah dipakai orang lain!', 'danger')
            return redirect(url_for('feed.edit_profile'))

        cursor.execute('SELECT profile_pic FROM users WHERE id = %s', (session['id'],))
        current_data = cursor.fetchone()
        filename = current_data['profile_pic']

        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '' and allowed_file(file.filename):
                if filename != 'default.jpg' and filename:
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    except:
                        pass
                
                filename = secure_filename(file.filename)
                filename = f"{int(time.time())}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cursor.execute('''
            UPDATE users SET full_name = %s, username = %s, bio = %s, profile_pic = %s
            WHERE id = %s
        ''', (full_name, username, bio, filename, session['id']))
        
        mysql.connection.commit()
        session['username'] = username
        
        flash('Profil berhasil diperbarui!', 'success')
        return redirect(url_for('feed.profile', username=username))

    cursor.execute('SELECT * FROM users WHERE id = %s', (session['id'],))
    user = cursor.fetchone()
    return render_template('edit_profile.html', user=user)

@feed_bp.route('/follow/<int:user_id>')
def follow(user_id):
    if 'loggedin' not in session:
        return redirect(url_for('auth.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    target_user = cursor.fetchone()
    
    if target_user:
        follower_id = session['id']
        followed_id = target_user['id']
        
        if follower_id != followed_id:
            try:
                cursor.execute('INSERT INTO follows (follower_id, followed_id) VALUES (%s, %s)', (follower_id, followed_id))
                cursor.execute("""
                    INSERT INTO notifications (recipient_id, sender_id, category, timestamp) 
                    VALUES (%s, %s, 'follow', NOW())
                """, (followed_id, follower_id))
                mysql.connection.commit()
                flash(f'Berhasil mengikuti {target_user["username"]}', 'success')
            except:
                pass
    
    return redirect(url_for('feed.feed'))

@feed_bp.route('/unfollow/<string:username>')
def unfollow(username):
    if 'loggedin' not in session:
        return redirect(url_for('auth.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT id FROM users WHERE username = %s', (username,))
    target_user = cursor.fetchone()
    
    if target_user:
        cursor.execute('DELETE FROM follows WHERE follower_id = %s AND followed_id = %s', (session['id'], target_user['id']))
        mysql.connection.commit()
        flash(f'Berhenti mengikuti {username}', 'warning')
        
    return redirect(url_for('feed.profile', username=username))

@feed_bp.route('/api/search_users')
def search_users():
    query = request.args.get('q', '')
    if len(query) < 1:
        return jsonify([])

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT username, profile_pic FROM users WHERE username LIKE %s LIMIT 5", (f'%{query}%',))
    users = cursor.fetchall()
    cursor.close()
    return jsonify(users)

@feed_bp.route('/profile/<username>')
def profile(username):
    if 'loggedin' not in session:
        return redirect(url_for('auth.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
    profile_user = cursor.fetchone()

    if not profile_user:
        return "User tidak ditemukan", 404

    query_posts = """
        SELECT 
            posts.*, 
            users.username, 
            users.full_name, 
            users.profile_pic,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS like_count,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id AND likes.user_id = %s) AS user_has_liked
        FROM posts 
        JOIN users ON posts.user_id = users.id 
        WHERE posts.user_id = %s
        ORDER BY posts.created_at DESC
    """
    cursor.execute(query_posts, (session['id'], profile_user['id']))
    posts = cursor.fetchall()
    
    cursor.execute('SELECT COUNT(*) as cnt FROM posts WHERE user_id = %s', (profile_user['id'],))
    post_count = cursor.fetchone()['cnt']

    cursor.execute('SELECT COUNT(*) as cnt FROM follows WHERE followed_id = %s', (profile_user['id'],))
    follower_count = cursor.fetchone()['cnt']

    cursor.execute('SELECT COUNT(*) as cnt FROM follows WHERE follower_id = %s', (profile_user['id'],))
    following_count = cursor.fetchone()['cnt']

    cursor.execute('SELECT * FROM follows WHERE follower_id = %s AND followed_id = %s', (session['id'], profile_user['id']))
    is_following = cursor.fetchone()

    is_own_profile = (session['id'] == profile_user['id'])

    cursor.close()

    return render_template('profile.html', 
                           user=profile_user,               # Data pemilik profil
                           posts=posts,                     # Daftar postingan
                           post_count=post_count,           # Statistik
                           follower_count=follower_count,   # Statistik
                           following_count=following_count, # Statistik
                           is_following=is_following,       # True/False (buat tombol Follow)
                           is_own_profile=is_own_profile)   # True/False (buat tombol Edit/Hapus)