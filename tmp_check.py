from app import app, Post

with app.app_context():
    posts = Post.query.all()
    print('count', len(posts))
    for p in posts:
        print(p.id, p.title, p.image)
