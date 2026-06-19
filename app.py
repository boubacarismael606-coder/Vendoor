from flask import Flask, render_template, request, redirect, url_for, session, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
from datetime import datetime, timedelta
import cloudinary
import cloudinary.uploader
import os
import json
import secrets
import re

# ---------------- APP INIT ----------------
app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'CHANGE_ME_SECRET')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///vendoor.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ---------------- MAIL ----------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
mail = Mail(app)

# ---------------- CLOUDINARY ----------------
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'jfif'}

# ---------------- HELPERS ----------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def upload_to_cloudinary(file):
    try:
        result = cloudinary.uploader.upload(file, folder="vendoor")
        return result.get('secure_url')
    except Exception as e:
        print("Cloudinary error:", e)
        return None


@app.context_processor
def utility_processor():
    def image_url(image_path):
        if not image_path:
            return 'https://placehold.co/300x200'
        if image_path.startswith('http'):
            return image_path
        return url_for('static', filename=image_path)
    return dict(image_url=image_url)


# =====================================================
# MODELS
# =====================================================

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    role = db.Column(db.String(10), default='user')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime)
    reset_token = db.Column(db.String(100))


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(20), nullable=False)

    image = db.Column(db.String(500), nullable=False)
    promo = db.Column(db.Float, default=0)

    delivery_method = db.Column(db.String(20))
    pickup_location = db.Column(db.String(200))
    location = db.Column(db.String(120))
    whatsapp = db.Column(db.String(30))

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='posts')


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))
    buyer_id = db.Column(db.Integer)
    seller_id = db.Column(db.Integer)
    amount = db.Column(db.Float)
    commission = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =====================================================
# BEFORE REQUEST (ONLINE STATUS)
# =====================================================

@app.before_request
def update_last_seen():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            user.last_seen = datetime.utcnow()
            db.session.commit()


# =====================================================
# HOME
# =====================================================

@app.route('/')
def home():
    username = session.get('username')
    search_query = request.args.get('q', '').strip()
    category_filter = request.args.get('category', '').strip()

    posts_query = Post.query

    if search_query:
        pattern = f"%{search_query.lower()}%"
        posts_query = posts_query.filter(
            func.lower(Post.title).like(pattern) |
            func.lower(Post.description).like(pattern) |
            func.lower(Post.category).like(pattern)
        )

    if category_filter:
        posts_query = posts_query.filter(Post.category == category_filter)

    posts = posts_query.order_by(Post.created_at.desc()).all()

    categories = [
        'Electronics', 'Clothing', 'Accessories',
        'Furniture', 'Food & Drinks', 'Service',
        'Delivery', 'Other'
    ]

    return render_template('home.html',
        username=username,
        posts=posts,
        search_query=search_query,
        category_filter=category_filter,
        categories=categories
    )


# =====================================================
# REGISTER
# =====================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        confirm = request.form['confirm_password']
        phone = request.form.get('phone', '').strip()

        EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if not re.match(EMAIL_REGEX, email):
            return render_template('register.html', error="Invalid email format")

        if password != confirm:
            return render_template('register.html', error="Passwords do not match")

        if len(password) < 6:
            return render_template('register.html', error="Password too short")

        if User.query.filter_by(email=email).first():
            return render_template('register.html', error="Email already used")

        if User.query.filter_by(username=username).first():
            return render_template('register.html', error="Username already taken")

        hashed = bcrypt.generate_password_hash(password).decode('utf-8')

        user = User(username=username, email=email, password=hashed, phone=phone)
        db.session.add(user)
        db.session.commit()

        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role

        return redirect(url_for('home'))

    return render_template('register.html')


# =====================================================
# LOGIN / LOGOUT
# =====================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']

        user = User.query.filter(func.lower(User.email) == email).first()

        if not user or not bcrypt.check_password_hash(user.password, password):
            return render_template('login.html', error="Invalid credentials")

        if user.role == 'banned':
            return render_template('login.html', error="Account banned")

        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role

        return redirect(url_for('home'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# =====================================================
# PUBLISH POST
# =====================================================

@app.route('/publish', methods=['GET', 'POST'])
def publish():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']
        post_type = request.form['type']

        image = request.form.get('image', '')
        image_file = request.files.get('image_file')

        if image_file and image_file.filename:
            if allowed_file(image_file.filename):
                image = upload_to_cloudinary(image_file)
            else:
                return render_template('publish.html', error="Invalid image format")

        if not image:
            image = "https://placehold.co/300x200"

        post = Post(
            title=title,
            description=description,
            price=price,
            category=category,
            type=post_type,
            image=image,
            promo=float(request.form.get('promo', 0) or 0),
            delivery_method=request.form.get('delivery_method'),
            pickup_location=request.form.get('pickup_location'),
            location=request.form.get('location'),
            whatsapp=request.form.get('whatsapp'),
            user_id=session['user_id']
        )

        db.session.add(post)
        db.session.commit()

        return redirect(url_for('home'))

    return render_template('publish.html')


# =====================================================
# POST DETAIL
# =====================================================

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    seller = User.query.get(post.user_id)

    return render_template('post_detail.html',
        post=post,
        seller=seller,
        username=session.get('username'),
        session_user_id=session.get('user_id')
    )


# =====================================================
# DELETE POST
# =====================================================

@app.route('/post/<int:post_id>/delete', methods=['POST'])
def delete_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    post = Post.query.get_or_404(post_id)

    if post.user_id != session['user_id'] and session.get('role') != 'admin':
        return redirect(url_for('home'))

    db.session.delete(post)
    db.session.commit()

    return redirect(url_for('home'))


# =====================================================
# FORGOT PASSWORD
# =====================================================

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        user = User.query.filter(func.lower(User.email) == email).first()

        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            db.session.commit()

            link = url_for('reset_password', token=token, _external=True)

            try:
                msg = Message(
                    "Reset Password",
                    sender=os.environ.get('MAIL_USERNAME'),
                    recipients=[email]
                )
                msg.body = f"Reset link: {link}"
                mail.send(msg)
            except Exception as e:
                print("Mail error:", e)

        return render_template('forgot_password.html', success="If email exists, link sent")

    return render_template('forgot_password.html')


# =====================================================
# RESET PASSWORD
# =====================================================

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()

    if not user:
        return render_template('login.html', error="Invalid token")

    if request.method == 'POST':
        password = request.form['password']
        confirm = request.form['confirm_password']

        if password != confirm:
            return render_template('reset_password.html', token=token, error="Mismatch")

        user.password = bcrypt.generate_password_hash(password).decode('utf-8')
        user.reset_token = None

        db.session.commit()

        return render_template('login.html', error="Password updated")

    return render_template('reset_password.html', token=token)


# =====================================================
# ADMIN
# =====================================================

def admin_required(f):
    from functools import wraps
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))

        user = User.query.get(session['user_id'])
        if not user or user.role != 'admin':
            return redirect(url_for('home'))

        return f(*args, **kwargs)
    return wrapper


@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin.html',
        total_users=User.query.count(),
        total_posts=Post.query.count(),
        recent_users=User.query.order_by(User.created_at.desc()).limit(10).all(),
        recent_posts=Post.query.order_by(Post.created_at.desc()).limit(10).all(),
        username=session.get('username')
    )


# =====================================================
# INIT DB
# =====================================================

def init_db():
    with app.app_context():
        db.create_all()

        with db.engine.connect() as conn:
            for query in [
                "ALTER TABLE post ADD COLUMN location VARCHAR(120)",
                "ALTER TABLE post ADD COLUMN whatsapp VARCHAR(30)",
                "ALTER TABLE users ADD COLUMN last_seen TIMESTAMP",
                "ALTER TABLE users ADD COLUMN reset_token VARCHAR(100)"
            ]:
                try:
                    conn.execute(text(query))
                    conn.commit()
                except:
                    pass

        print("Database ready ✅")


init_db()


# =====================================================
# RUN
# =====================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)