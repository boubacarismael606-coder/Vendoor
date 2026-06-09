from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text
from flask_bcrypt import Bcrypt
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'vendoor-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vendoor.db'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'images')
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'jfif'}

def ensure_db_schema():
    with db.engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info('user')"))
        existing_cols = [row['name'] for row in result.mappings()]
        if not existing_cols:
            return
        if 'phone' not in existing_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN phone VARCHAR(20) DEFAULT ''"))
        if 'role' not in existing_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN role VARCHAR(10) DEFAULT 'user'"))
        if 'created_at' not in existing_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN created_at DATETIME"))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    image = db.Column(db.String(200), nullable=False)
    promo = db.Column(db.Float, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    delivery_method = db.Column(db.String(20), nullable=True)
    pickup_location = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('posts', lazy=True))

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    commission = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- ROUTES ---

@app.route('/')
def home():
    username = session.get('username')
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('home.html', username=username, posts=posts)

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
        image = request.form.get('image', '').strip()
        promo = float(request.form.get('promo', 0) or 0)

        image_file = request.files.get('image_file')
        if image_file and image_file.filename:
            if allowed_file(image_file.filename):
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                ext = image_file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(filepath)
                image = f'images/{filename}'
            else:
                error = "Format d'image non supporté. Utilise png, jpg, jpeg, gif, webp ou jfif."
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
            return render_template('login.html', error="Email ou mot de passe invalide.")

        if user.role == 'banned':
            return render_template('login.html', error="Votre compte a été bloqué. Contactez l'administrateur.")

        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        return redirect(url_for('home'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        confirm = request.form['confirm_password']
        phone = request.form.get('phone', '').strip()

        if 'terms' not in request.form:
            return render_template('register.html', error="Vous devez accepter les conditions et la commission de 5%.")

        if len(password) < 6:
            return render_template('register.html', error="Le mot de passe doit contenir au moins 6 caractères.")

        if password != confirm:
            return render_template('register.html', error="Les mots de passe ne correspondent pas.")

        if User.query.filter_by(email=email).first():
            return render_template('register.html', error="Cet email est déjà utilisé.")

        if User.query.filter_by(username=username).first():
            return render_template('register.html', error="Ce nom d'utilisateur est déjà pris.")

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
        return render_template('profile.html', user=user, success="Profil mis à jour ✅")

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

    if post.user_id != session['user_id']:
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
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                ext = image_file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(filepath)
                post.image = f'images/{filename}'

        db.session.commit()
        return redirect(url_for('posts_list'))

    return render_template('edit_post.html', post=post)

@app.route('/post/<int:post_id>/delete', methods=['POST'])
def delete_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    post = Post.query.get_or_404(post_id)

    if post.user_id != session['user_id']:
        return redirect(url_for('posts_list'))

    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('posts_list'))

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
def admin_dashboard():
    total_users = User.query.count()
    total_posts = Post.query.count()
    recent_posts = Post.query.order_by(Post.created_at.desc()).limit(10).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
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

# --- LANCEMENT ---

def init_db():
    with app.app_context():
        db.create_all()
        ensure_db_schema()

        admin_user = User.query.filter_by(email='admin@vendoor.com').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@vendoor.com',
                password=bcrypt.generate_password_hash('admin123').decode('utf-8'),
                role='admin'
            )
            db.session.add(admin_user)
            db.session.commit()

        if Post.query.count() == 0:
            test_user = User.query.filter_by(email='test@vendoor.com').first()
            if not test_user:
                test_user = User(
                    username='vendoor_test',
                    email='test@vendoor.com',
                    password=bcrypt.generate_password_hash('123456').decode('utf-8'),
                    role='user'
                )
                db.session.add(test_user)
                db.session.commit()

            sample_posts = [
                Post(
                    title='iPhone 13 Pro',
                    description='iPhone 13 Pro en excellent état. Toutes les fonctionnalités marchent parfaitement.',
                    price=450000,
                    category='Electronics',
                    type='article',
                    image='https://images.unsplash.com/photo-1592286927505-1def25115558?w=400',
                    promo=0,
                    user_id=test_user.id
                ),
                Post(
                    title='Computer repair',
                    description='PC, laptop repair, software installation, virus removal. Fast and reliable.',
                    price=5000,
                    category='Service',
                    type='service',
                    image='https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=400',
                    promo=0,
                    user_id=test_user.id
                ),
                Post(
                    title='Campus courier',
                    description='Fast delivery on campus. Parcels, documents and more.',
                    price=1000,
                    category='Delivery',
                    type='service',
                    image='https://images.unsplash.com/photo-1606576509773-297b51b64d84?w=400',
                    promo=0,
                    user_id=test_user.id
                )
            ]
            for post in sample_posts:
                db.session.add(post)
            db.session.commit()

init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)