from flask import Flask, render_template, request, redirect, url_for, session, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from flask_bcrypt import Bcrypt
from datetime import datetime
import os
import json
import cloudinary
import cloudinary.uploader
from sqlalchemy import func, text
from datetime import datetime, timedelta
from flask_mail import Mail, Message
import secrets

app = Flask(__name__)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
mail = Mail(app)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'vendoor-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///vendoor.db')
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'jfif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_cloudinary(file):
    try:
        result = cloudinary.uploader.upload(file, folder='vendoor')
        return result.get('secure_url')
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None

@app.context_processor
def utility_processor():
    def image_url(image_path):
        if not image_path:
            return 'https://placehold.co/300x200'
        if image_path.startswith('http://') or image_path.startswith('https://'):
            return image_path
        return url_for('static', filename=image_path)
    return dict(image_url=image_url)

# --- TABLES ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    role = db.Column(db.String(10), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, nullable=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    image = db.Column(db.String(500), nullable=False)
    promo = db.Column(db.Float, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    delivery_method = db.Column(db.String(20), nullable=True)
    pickup_location = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('posts', lazy=True))
    location = db.Column(db.String(120), nullable=True)
    whatsapp = db.Column(db.String(30), nullable=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    commission = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reset_token = db.Column(db.String(100), nullable=True)
# --- ROUTES ---
@app.before_request
def update_last_seen():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            user.last_seen = datetime.utcnow()
            db.session.commit()
@app.route('/')
def home():
    username = session.get('username')
    search_query = request.args.get('q', '').strip()
    category_filter = request.args.get('category', '').strip()

    posts_query = Post.query

    if search_query:
        search_pattern = f"%{search_query.lower()}%"
        posts_query = posts_query.filter(
            func.lower(Post.title).like(search_pattern) |
            func.lower(Post.description).like(search_pattern) |
            func.lower(Post.category).like(search_pattern)
        )

    if category_filter:
        posts_query = posts_query.filter(Post.category == category_filter)

    posts = posts_query.order_by(Post.created_at.desc()).all()
    categories = ['Electronics', 'Clothing', 'Accessories', 'Furniture', 'Food & Drinks', 'Service', 'Delivery', 'Other']

    return render_template('home.html',
        username=username,
        posts=posts,
        search_query=search_query,
        category_filter=category_filter,
        categories=categories
    )

@app.route('/publish', methods=['GET', 'POST'])
def publish():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    error = None

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']
        post_type = request.form['type']
        delivery_method = request.form.get('delivery_method', 'delivery')
        pickup_location = request.form.get('pickup_location', '').strip()
        location = request.form.get('location', '').strip()
        whatsapp = request.form.get('whatsapp', '').strip()
        image = request.form.get('image', '').strip()
        promo = float(request.form.get('promo', 0) or 0)

        image_file = request.files.get('image_file')
        if image_file and image_file.filename:
            if allowed_file(image_file.filename):
                cloudinary_url = upload_to_cloudinary(image_file)
                if cloudinary_url:
                    image = cloudinary_url
                else:
                    error = "Image upload failed. Please try again."
                    return render_template('publish.html', error=error)
            else:
                error = "Unsupported format. Please use png, jpg, jpeg, gif, webp or jfif."
                return render_template('publish.html', error=error)

        if not image:
            image = 'https://placehold.co/300x200'

        new_post = Post(
            title=title,
            description=description,
            price=price,
            category=category,
            type=post_type,
            image=image,
            promo=promo,
            delivery_method=delivery_method,
            pickup_location=pickup_location,
            location=location,
            whatsapp=whatsapp,
            user_id=session['user_id']
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('home'))

    return render_template('publish.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        user = User.query.filter(func.lower(User.email) == email).first()

        if not user or not bcrypt.check_password_hash(user.password, password):
            return render_template('login.html', error="Email or password is incorrect.")

        if user.role == 'banned':
            return render_template('login.html', error="Your account has been banned. Contact admin.")

        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        return redirect(url_for('home'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(EMAIL_REGEX, email):
            return render_template('register.html', error="Please enter a valid email address (e.g. name@gmail.com).")
        password = request.form['password']
        confirm = request.form['confirm_password']
        phone = request.form.get('phone', '').strip()

        if 'terms' not in request.form:
            return render_template('register.html', error="You must accept the 5% commission terms.")

        if len(password) < 6:
            return render_template('register.html', error="Password must be at least 6 characters.")

        if password != confirm:
            return render_template('register.html', error="Passwords do not match.")

        if User.query.filter_by(email=email).first():
            return render_template('register.html', error="This email is already used.")

        if User.query.filter_by(username=username).first():
            return render_template('register.html', error="This username is already taken.")

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, email=email, password=hashed_pw, phone=phone)
        db.session.add(new_user)
        db.session.commit()

        session['user_id'] = new_user.id
        session['username'] = new_user.username
        session['role'] = new_user.role
        return redirect(url_for('home'))

    return render_template('register.html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        user.phone = phone
        db.session.commit()
        return render_template('profile.html', user=user, success="Profile updated ✅")

    return render_template('profile.html', user=user)

@app.route('/posts')
def posts_list():
    username = session.get('username')
    user_id = session.get('user_id')
    search_query = request.args.get('q', '').strip()
    posts_query = Post.query
    if search_query:
        search_pattern = f"%{search_query.lower()}%"
        posts_query = posts_query.filter(
            func.lower(Post.title).like(search_pattern) |
            func.lower(Post.description).like(search_pattern) |
            func.lower(Post.category).like(search_pattern)
        )
    posts = posts_query.order_by(Post.created_at.desc()).all()
    return render_template('posts.html', username=username, user_id=user_id, posts=posts, search_query=search_query)

@app.route('/my_listings')
def my_listings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    username = session.get('username')
    search_query = request.args.get('q', '').strip()
    posts_query = Post.query.filter_by(user_id=session['user_id'])
    if search_query:
        search_pattern = f"%{search_query.lower()}%"
        posts_query = posts_query.filter(
            func.lower(Post.title).like(search_pattern) |
            func.lower(Post.description).like(search_pattern) |
            func.lower(Post.category).like(search_pattern)
        )
    posts = posts_query.order_by(Post.created_at.desc()).all()
    return render_template('my_listings.html', username=username, posts=posts, search_query=search_query)

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    seller = User.query.get(post.user_id)
    username = session.get('username')
    session_user_id = session.get('user_id')
    return render_template('post_detail.html', post=post, seller=seller, username=username, session_user_id=session_user_id)

@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
def edit_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    post = Post.query.get_or_404(post_id)

    if post.user_id != session['user_id'] and session.get('role') != 'admin':
        return redirect(url_for('posts_list'))

    if request.method == 'POST':
        post.title = request.form['title']
        post.description = request.form['description']
        post.price = float(request.form['price'])
        post.category = request.form['category']
        post.type = request.form['type']
        post.delivery_method = request.form.get('delivery_method', post.delivery_method)
        post.pickup_location = request.form.get('pickup_location', post.pickup_location)
        post.promo = float(request.form.get('promo', 0) or 0)

        image_file = request.files.get('image_file')
        if image_file and image_file.filename:
            if allowed_file(image_file.filename):
                cloudinary_url = upload_to_cloudinary(image_file)
                if cloudinary_url:
                    post.image = cloudinary_url

        db.session.commit()
        return redirect(url_for('posts_list'))

    return render_template('edit_post.html', post=post)

@app.route('/post/<int:post_id>/delete', methods=['POST'])
def delete_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    post = Post.query.get_or_404(post_id)

    if post.user_id != session['user_id'] and session.get('role') != 'admin':
        return redirect(url_for('posts_list'))

    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('posts_list'))
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        user = User.query.filter(func.lower(User.email) == email).first()

        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            db.session.commit()

            reset_link = url_for('reset_password', token=token, _external=True)
            try:
                msg = Message('Reset your Vendoor password',
                               sender=os.environ.get('MAIL_USERNAME'),
                               recipients=[email])
                msg.body = f"Click this link to reset your password: {reset_link}\n\nIf you didn't request this, ignore this email."
                mail.send(msg)
            except Exception as e:
                print(f"Mail error: {e}")

        return render_template('forgot_password.html', success="If this email exists, a reset link has been sent.")

    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user:
        return render_template('login.html', error="Invalid or expired reset link.")

    if request.method == 'POST':
        password = request.form['password']
        confirm = request.form['confirm_password']

        if len(password) < 6:
            return render_template('reset_password.html', token=token, error="Password must be at least 6 characters.")
        if password != confirm:
            return render_template('reset_password.html', token=token, error="Passwords do not match.")

        user.password = bcrypt.generate_password_hash(password).decode('utf-8')
        user.reset_token = None
        db.session.commit()
        return render_template('login.html', error="Password updated! You can log in now.")

    return render_template('reset_password.html', token=token)
# --- ADMIN ---

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or user.role != 'admin':
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated

@app.route('/admin')
@admin_required
@app.route('/admin')
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    total_posts = Post.query.count()
    recent_posts = Post.query.order_by(Post.created_at.desc()).limit(10).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()

    online_threshold = datetime.utcnow() - timedelta(minutes=5)
    for user in recent_users:
        user.is_online = user.last_seen and user.last_seen >= online_threshold

    return render_template('admin.html',
        total_users=total_users,
        total_posts=total_posts,
        recent_posts=recent_posts,
        recent_users=recent_users,
        username=session.get('username')
    )

@app.route('/admin/delete_post/<int:post_id>', methods=['POST'])
@admin_required
def admin_delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/ban_user/<int:user_id>', methods=['POST'])
@admin_required
def admin_ban_user(user_id):
    user = User.query.get_or_404(user_id)
    user.role = 'banned'
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/unban_user/<int:user_id>', methods=['POST'])
@admin_required
def admin_unban_user(user_id):
    user = User.query.get_or_404(user_id)
    user.role = 'user'
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/export')
@admin_required
def admin_export():
    users = User.query.all()
    posts = Post.query.all()

    data = {
        'exported_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'users': [
            {
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'phone': u.phone or '',
                'role': u.role,
                'created_at': u.created_at.strftime('%Y-%m-%d %H:%M:%S') if u.created_at else ''
            }
            for u in users
        ],
        'posts': [
            {
                'id': p.id,
                'title': p.title,
                'description': p.description,
                'price': p.price,
                'category': p.category,
                'type': p.type,
                'image': p.image,
                'promo': p.promo,
                'delivery_method': p.delivery_method or '',
                'pickup_location': p.pickup_location or '',
                'user_id': p.user_id,
                'created_at': p.created_at.strftime('%Y-%m-%d %H:%M:%S') if p.created_at else ''
            }
            for p in posts
        ]
    }

    filename = f"vendoor_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    return Response(
        json.dumps(data, indent=2, ensure_ascii=False),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

# --- LANCEMENT ---

def init_db():
    with app.app_context():
        db.create_all()

        # Ajouter les colonnes manquantes si elles n'existent pas
        with db.engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE post ADD COLUMN location VARCHAR(120)"))
                conn.commit()
                print("Colonne location ajoutée ✅")
            except Exception:
                conn.rollback()

            try:
                conn.execute(text("ALTER TABLE post ADD COLUMN whatsapp VARCHAR(30)"))
                conn.commit()
                print("Colonne whatsapp ajoutée ✅")
            except Exception:
                conn.rollback()

        admin = User.query.filter_by(email='admin@vendoor.com').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@vendoor.com',
                password=bcrypt.generate_password_hash('admin123').decode('utf-8'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin créé ✅")

        print("Base de données prête ✅")
        try:
            conn.execute(text("ALTER TABLE \"user\" ADD COLUMN last_seen TIMESTAMP"))
            conn.commit()
            print("Colonne last_seen ajoutée ✅")
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE \"user\" ADD COLUMN reset_token VARCHAR(100)"))
            conn.commit()
        except Exception:
            conn.rollback()
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)