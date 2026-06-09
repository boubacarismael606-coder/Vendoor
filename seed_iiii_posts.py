from app import app, db, ensure_db_schema, User, Post, bcrypt
import random
from datetime import datetime

with app.app_context():
    db.create_all()
    ensure_db_schema()

    user = User.query.filter_by(email='ii@g').first()
    if not user:
        user = User(
            username='iiii',
            email='ii@g',
            password=bcrypt.generate_password_hash('ii123456').decode('utf-8'),
            role='user'
        )
        db.session.add(user)
        db.session.commit()
        print('Created user', user.username, user.email)
    else:
        print('User exists', user.username, user.email)

    existing = Post.query.filter_by(user_id=user.id).count()
    print('Existing posts for user:', existing)

    images = [
        f'https://placehold.co/600x400?text=Item+{i}' for i in range(1, 11)
    ]

    created = 0
    for i in range(1, 11):
        title = f'Annonce iiii {i}'
        existing_post = Post.query.filter_by(user_id=user.id, title=title).first()
        if existing_post:
            print('Already exists:', title)
            continue

        p = Post(
            title=title,
            description=f'Description de l annonce {i} créée pour le compte iiii.',
            price=round(random.uniform(1000, 10000), 2),
            category=random.choice(['Electronics', 'Accessories', 'Clothing', 'Service', 'Furniture', 'Other']),
            type='article' if i % 2 == 1 else 'service',
            image=images[i - 1],
            promo=0 if i % 3 else 10,
            delivery_method='delivery' if i % 2 else 'pickup',
            pickup_location='Campus central' if i % 2 == 0 else None,
            user_id=user.id,
            created_at=datetime.utcnow()
        )
        db.session.add(p)
        created += 1
        print('Created post:', title)

    if created:
        db.session.commit()

    print('Finished. Total posts now:', Post.query.filter_by(user_id=user.id).count())
