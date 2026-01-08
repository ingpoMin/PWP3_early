from flask import Blueprint, request, redirect, url_for, session, flash
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from flask import Blueprint, request, redirect, url_for, session, flash, jsonify, render_template, current_app as app
import os
import re
import MySQLdb.cursors
from .. import mysql, allowed_file

post_bp = Blueprint('post', __name__)


def handle_mentions(content, post_id, sender_id):
    if not content:
        return
    mentions = re.findall(r'@(\w+)', content)
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    for username in mentions:
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        target_user = cursor.fetchone()
        
        if target_user and target_user['id'] != sender_id:
            cursor.execute("""
                INSERT INTO notifications (recipient_id, sender_id, post_id, category, timestamp)
                VALUES (%s, %s, %s, 'mention', NOW())
            """, (target_user['id'], sender_id, post_id))

@post_bp.route('/create_post', methods=['POST'])
def create_post():
    if 'loggedin' not in session:
        return redirect(url_for('auth.login'))

    caption = request.form['caption']
    user_id = session['id']
    media_url = None
    media_type = 'text' 

    if 'media_file' in request.files:
        file = request.files['media_file']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            media_url = filename
            ext = filename.rsplit('.', 1)[1].lower()
            media_type = 'video' if ext in ['mp4', 'avi', 'mov'] else 'image'

    if not caption.strip() and media_type == 'text':
        flash('Isi caption atau upload sesuatu!', 'danger')
        return redirect(url_for('feed.feed'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute('INSERT INTO posts (user_id, caption, media_url, media_type) VALUES (%s, %s, %s, %s)', 
                       (user_id, caption, media_url, media_type))
        post_id = cursor.lastrowid
        caption = request.form.get('caption')
        handle_mentions(caption, post_id, session['id'])
        mysql.connection.commit()
        flash('Status berhasil diposting!', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Gagal posting: {str(e)}', 'danger')

    return redirect(url_for('feed.feed'))


    mysql.connection.commit()

@post_bp.route('/post/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    if 'loggedin' not in session:
        return redirect(url_for('auth.login'))

    content = request.form.get('content') or request.form.get('comment_text')
    
    parent_id = request.form.get('parent_id') 
    if parent_id == '' or parent_id == 'None':
        parent_id = None

    user_id = session['id']

    if content and content.strip():
        cursor = mysql.connection.cursor()
        cursor.execute('INSERT INTO comments (user_id, post_id, content, parent_id) VALUES (%s, %s, %s, %s)',
                       (user_id, post_id, content, parent_id))
        
        handle_mentions(content, post_id, session['id'])
        mysql.connection.commit()
    else:
        flash('Komentar kosong!', 'danger')

    return redirect(url_for('post.post_detail', post_id=post_id))

@post_bp.route('/post/<int:post_id>')
def post_detail(post_id):
    if 'loggedin' not in session:
        return redirect(url_for('auth.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    query_post = """
        SELECT posts.*, users.username, users.full_name, users.profile_pic,
        (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS like_count,
        (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id AND likes.user_id = %s) AS user_has_liked
        FROM posts 
        JOIN users ON posts.user_id = users.id 
        WHERE posts.id = %s
    """
    cursor.execute(query_post, (session['id'], post_id))
    post = cursor.fetchone()

    query_comments = """
        SELECT comments.*, users.username, users.full_name, users.profile_pic,
        (SELECT COUNT(*) FROM comment_likes WHERE comment_id = comments.id) AS like_count,
        (SELECT COUNT(*) FROM comment_likes WHERE comment_id = comments.id AND user_id = %s) AS user_has_liked
        FROM comments 
        JOIN users ON comments.user_id = users.id 
        WHERE comments.post_id = %s 
        ORDER BY comments.created_at ASC
    """
    cursor.execute(query_comments, (session['id'], post_id))
    all_comments = cursor.fetchall()
    
    parents = []
    replies = {}

    for c in all_comments:
        if c['parent_id'] is None:
            parents.append(c)
        else:
            p_id = c['parent_id']
            if p_id not in replies:
                replies[p_id] = []
            replies[p_id].append(c)

    cursor.execute('SELECT * FROM users WHERE id = %s', (session['id'],))
    current_user = cursor.fetchone()

    return render_template('post_detail.html', post=post, parents=parents, replies=replies, 
                           comment_count=len(all_comments), user=current_user)

@post_bp.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if 'loggedin' not in session:
        return redirect(url_for('auth.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM posts WHERE id = %s', (post_id,))
    post = cursor.fetchone()
    current_username = session.get('username') 

    if not post or post['user_id'] != session['id']:
        flash('Aksi tidak diizinkan', 'danger')
        return redirect(url_for('feed.profile', username=current_username))

    if post['media_url']:
        try:
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], post['media_url'])
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass

    cursor.execute('DELETE FROM posts WHERE id = %s', (post_id,))
    mysql.connection.commit()
    cursor.close()
    
    flash('Postingan berhasil dihapus', 'success')
    return redirect(url_for('feed.profile', username=current_username))

@post_bp.route('/delete_comment/<int:comment_id>')
def delete_comment(comment_id):
    if 'loggedin' not in session:
        return redirect(url_for('auth.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM comments WHERE id = %s', (comment_id,))
    comment = cursor.fetchone()
    
    if comment and comment['user_id'] == session['id']:
        post_id = comment['post_id']
        cursor.execute('DELETE FROM comments WHERE id = %s', (comment_id,))
        mysql.connection.commit()
        flash('Komentar dihapus', 'success')
        return redirect(url_for('post.post_detail', post_id=post_id))

    return redirect(url_for('feed.feed'))

@post_bp.route('/api/like_post/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': 'Login required'}), 401

    user_id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT * FROM likes WHERE user_id = %s AND post_id = %s", (user_id, post_id))
    existing_like = cursor.fetchone()

    liked = False
    if existing_like:
        cursor.execute("DELETE FROM likes WHERE user_id = %s AND post_id = %s", (user_id, post_id))
    else:
        cursor.execute("INSERT INTO likes (user_id, post_id) VALUES (%s, %s)", (user_id, post_id))
        liked = True

        cursor.execute("SELECT user_id FROM posts WHERE id = %s", (post_id,))
        post_data = cursor.fetchone()
        
        if post_data and post_data['user_id'] != user_id:
            cursor.execute("""
                INSERT INTO notifications (recipient_id, sender_id, post_id, category, timestamp)
                VALUES (%s, %s, %s, 'like', NOW())
            """, (post_data['user_id'], user_id, post_id))

    mysql.connection.commit()

    cursor.execute("SELECT COUNT(*) as count FROM likes WHERE post_id = %s", (post_id,))
    new_count = cursor.fetchone()['count']
    cursor.close()

    return jsonify({'status': 'success', 'liked': liked, 'new_count': new_count})

@post_bp.route('/api/like_comment/<int:comment_id>', methods=['POST'])
def api_like_comment(comment_id):
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': 'Belum login'})

    user_id = session['id']
    cursor = mysql.connection.cursor()
    
    cursor.execute('SELECT * FROM comment_likes WHERE user_id = %s AND comment_id = %s', (user_id, comment_id))
    existing_like = cursor.fetchone()

    liked = False
    if existing_like:
        cursor.execute('DELETE FROM comment_likes WHERE user_id = %s AND comment_id = %s', (user_id, comment_id))
    else:
        cursor.execute('INSERT INTO comment_likes (user_id, comment_id) VALUES (%s, %s)', (user_id, comment_id))
        liked = True
    
    mysql.connection.commit()
    
    cursor.execute('SELECT COUNT(*) as count FROM comment_likes WHERE comment_id = %s', (comment_id,))
    new_count = cursor.fetchone()[0]

    return jsonify({'status': 'success', 'liked': liked, 'new_count': new_count})

@post_bp.app_template_filter('linkify_mentions')
def linkify_mentions(text):
    return re.sub(r'@(\w+)', r'<a href="/profile/\1" class="text-blue-500 hover:underline">@\1</a>', text)