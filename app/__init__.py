import os
from flask import Flask
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv

mysql = MySQL()
bcrypt = Bcrypt()

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'mov'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_app():
    load_dotenv()
    app = Flask(__name__)

    app.config['MYSQL_HOST'] = os.getenv('DB_HOST')
    app.config['MYSQL_USER'] = os.getenv('DB_USER')
    app.config['MYSQL_PASSWORD'] = os.getenv('DB_PASSWORD')
    app.config['MYSQL_DB'] = os.getenv('DB_NAME')
    app.secret_key = os.getenv('SECRET_KEY')
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    mysql.init_app(app)
    bcrypt.init_app(app)

    from .controller.auth_routes import auth_bp
    from .controller.post_routes import post_bp
    from .controller.feed_routes import feed_bp
    from .controller.chat_routes import chat_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(post_bp)
    app.register_blueprint(feed_bp)
    app.register_blueprint(chat_bp)

    return app