from flask import Blueprint, request, redirect, url_for, session, flash
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
from .. import mysql
from app import mysql

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/chat')
def chat_list():
    if 'loggedin' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    query = """
        SELECT DISTINCT users.id, users.username, users.full_name, users.profile_pic
        FROM users
        LEFT JOIN follows ON users.id = follows.followed_id AND follows.follower_id = %s
        LEFT JOIN chats ON (users.id = chats.sender_id AND chats.receiver_id = %s) 
                        OR (users.id = chats.receiver_id AND chats.sender_id = %s)
        WHERE (follows.follower_id IS NOT NULL OR chats.id IS NOT NULL)
        AND users.id != %s
    """
    cursor.execute(query, (user_id, user_id, user_id, user_id))
    users_list = cursor.fetchall()
    
    return render_template('chat_list.html', users=users_list)

@chat_bp.route('/chat/<string:username>')
def chat_room(username):
    if 'loggedin' not in session:
        return redirect(url_for('auth.login'))
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
    partner = cursor.fetchone()
    
    if not partner:
        flash('User tidak ditemukan', 'danger')
        return redirect(url_for('chat.chat_list'))
    
    query_chats = """
        SELECT * FROM chats 
        WHERE (sender_id = %s AND receiver_id = %s) 
           OR (sender_id = %s AND receiver_id = %s)
        ORDER BY created_at ASC
    """
    cursor.execute(query_chats, (session['id'], partner['id'], partner['id'], session['id']))
    messages = cursor.fetchall()
    
    return render_template('chat_room.html', partner=partner, messages=messages)

@chat_bp.route('/api/get_chat/<string:partner_username>')
def api_get_chat(partner_username):
    if 'loggedin' not in session:
        return jsonify([])

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT id FROM users WHERE username = %s', (partner_username,))
    partner = cursor.fetchone()
    if not partner: return jsonify([])

    query = """
        SELECT * FROM chats 
        WHERE (sender_id = %s AND receiver_id = %s) 
           OR (sender_id = %s AND receiver_id = %s)
        ORDER BY created_at ASC
    """
    cursor.execute(query, (session['id'], partner['id'], partner['id'], session['id']))
    messages = cursor.fetchall()
    
    for msg in messages:
        msg['created_at'] = msg['created_at'].strftime('%Y-%m-%d %H:%M')

    return jsonify({'messages': messages, 'my_id': session['id']})

@chat_bp.route('/api/send_message', methods=['POST'])
def api_send_message():
    if 'loggedin' not in session:
        return jsonify({'status': 'error'})
        
    data = request.json
    receiver_username = data['receiver_username']
    message = data['message']
    
    if message and message.strip():
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT id FROM users WHERE username = %s', (receiver_username,))
        receiver_data = cursor.fetchone() 
        
        if receiver_data:
            cursor.execute('INSERT INTO chats (sender_id, receiver_id, message) VALUES (%s, %s, %s)', 
                           (session['id'], receiver_data[0], message))
            mysql.connection.commit()
            return jsonify({'status': 'success'})
            
    return jsonify({'status': 'fail'})