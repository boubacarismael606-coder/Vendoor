from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from flask_bcrypt import Bcrypt
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'vendoor-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vendoor.db'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'images')
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- TABLES ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
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
    delivery_method = db.Column(db.String(20), nullable=True)  # 'delivery' or 'pickup'
    pickup_location = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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

        # handle uploaded file if provided
        image_file = request.files.get('image_file')
        if image_file and image_file.filename:
            if allowed_file(image_file.filename):
                # ensure upload folder exists
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                ext = secure_filename(image_file.filename).rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(filepath)
                # store URL path for templates
                image = url_for('static', filename=f'images/{filename}')
            else:
                return render_template('publish.html', error="Type d'image non supporté. Utilisez png/jpg/gif/webp.")
        # if no uploaded file and no external URL, use placeholder
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

    return render_template('publish.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        user = User.query.filter(func.lower(User.email) == email).first()

        if not user or not bcrypt.check_password_hash(user.password, password):
            return render_template('login.html', error="Email ou mot de passe invalide.")

        session['user_id'] = user.id
        session['username'] = user.username
        return redirect(url_for('home'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        confirm = request.form['confirm_password']

        # require terms checkbox (server-side)
        if 'terms' not in request.form:
            return render_template('register.html', error="Vous devez accepter les conditions et la commission de 5%.")

        # password length validation
        if len(password) < 6:
            return render_template('register.html', error="Le mot de passe doit contenir au moins 6 caractères.")

        if password != confirm:
            return render_template('register.html', error="Les mots de passe ne correspondent pas.")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template('register.html', error="Cet email est déjà utilisé.")

        existing_username = User.query.filter_by(username=username).first()
        if existing_username:
            return render_template('register.html', error="Ce nom d'utilisateur est déjà pris.")

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, email=email, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()

        session['user_id'] = new_user.id
        session['username'] = new_user.username
        return redirect(url_for('home'))

    return render_template('register.html')

@app.route('/posts')
def posts_list():
    username = session.get('username')
    user_id = session.get('user_id')
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('posts.html', username=username, user_id=user_id, posts=posts)

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
        
        # handle new image upload
        image_file = request.files.get('image_file')
        if image_file and image_file.filename:
            if allowed_file(image_file.filename):
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                ext = secure_filename(image_file.filename).rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(filepath)
                post.image = url_for('static', filename=f'images/{filename}')
        
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

# --- LANCEMENT ---

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # seed initial posts if none exist
        if Post.query.count() == 0:
            # create a test user for these posts
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
            
            # add sample posts
            sample_posts = [
                Post(
                    title='iPhone 13 Pro',
                    description='iPhone 13 Pro en excellent état. Toutes les fonctionnalités marchent parfaitement.',
                    price=450000,
                    category='Électronique',
                    type='article',
                    image='https://images.unsplash.com/photo-1592286927505-1def25115558?w=400',
                    promo=0,
                    user_id=test_user.id
                ),
                Post(
                    title='Dépannage informatique',
                    description='Reparation de PC, laptop, installation de logiciels, nettoyage virus. Intervention rapide et efficace.',
                    price=5000,
                    category='Service',
                    type='service',
                    image='https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=400',
                    promo=0,
                    user_id=test_user.id
                ),
                Post(
                    title='Coursier campus',
                    description='Service de livraison rapide sur le campus. Livraison de colis, documents et autres articles.',
                    price=1000,
                    category='Livraison',
                    type='service',
                    image='https://images.unsplash.com/photo-1606576509773-297b51b64d84?w=400',
                    promo=0,
                    user_id=test_user.id
                )
            ]
            for post in sample_posts:
                db.session.add(post)
            db.session.commit()
        
        print("Base de données créée ✅")
    app.run(debug=True)