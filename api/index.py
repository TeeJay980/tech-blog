from flask import Flask, request, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'thub-secret-key-12345'

# Priority: Cloud (Postgres) -> Local (SQLite)
# Note: Supabase provides a postgres:// URL which SQLALchemy needs as postgresql://
db_url = os.environ.get('DATABASE_URL', 'sqlite:///blog.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
CORS(app, supports_credentials=True)

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    bio = db.Column(db.String(200), default="Tech enthusiast.")
    
    posts = db.relationship('Post', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    link = db.Column(db.String(500), unique=True)
    summary = db.Column(db.Text)
    excerpt = db.Column(db.String(300))
    content = db.Column(db.Text)
    image = db.Column(db.String(500))
    source = db.Column(db.String(100))
    category = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_user_post = db.Column(db.Boolean, default=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    likes_count = db.Column(db.Integer, default=0)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# API Endpoints
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    if User.query.filter_by(username=data['username']).first():
        return jsonify({"error": "Username already exists"}), 400
    
    hashed_pw = generate_password_hash(data['password'])
    new_user = User(username=data['username'], password_hash=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"success": "Account created!"}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data['username']).first()
    if user and check_password_hash(user.password_hash, data['password']):
        login_user(user, remember=True)
        return jsonify({"username": user.username, "success": True})
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({"success": True})

@app.route('/api/auth/me', methods=['GET'])
def get_me():
    if current_user.is_authenticated:
        return jsonify({"username": current_user.username, "id": current_user.id})
    return jsonify({"authenticated": False}), 401

@app.route('/api/posts', methods=['GET'])
def get_posts():
    try:
        posts = Post.query.order_by(Post.created_at.desc()).all()
        output = []
        for post in posts:
            liked = False
            if current_user.is_authenticated:
                try:
                    liked = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None
                except:
                    liked = False
            
            output.append({
                "id": post.id,
                "title": post.title,
                "link": post.link or f"/post.html?id={post.id}", 
                "summary": post.summary,
                "excerpt": post.excerpt,
                "content": post.content,
                "image": post.image,
                "source": post.source,
                "category": post.category,
                "is_user_post": post.is_user_post,
                "likes_count": post.likes_count,
                "liked": liked,
                "author": post.author.username if (post.author and hasattr(post.author, 'username')) else "System"
            })
        return jsonify(output)
    except Exception as e:
        return jsonify({"error": str(e), "msg": "Database query failed"}), 500

@app.route('/api/posts/create', methods=['POST'])
@login_required
def create_post():
    data = request.json
    new_post = Post(
        title=data['title'],
        content=data['content'],
        excerpt=data.get('excerpt', data['content'][:150] + "..."),
        image=data.get('image', 'assets/placeholder.png'),
        category=data.get('category', 'User Story'),
        source=current_user.username,
        is_user_post=True,
        author_id=current_user.id
    )
    db.session.add(new_post)
    db.session.commit()
    return jsonify({"success": True, "id": new_post.id})

@app.route('/api/posts/like', methods=['POST'])
@login_required
def toggle_like():
    data = request.json
    post_id = data['post_id']
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    post = Post.query.get_or_404(post_id)
    if existing_like:
        db.session.delete(existing_like)
        post.likes_count -= 1
        status = "unliked"
    else:
        new_like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(new_like)
        post.likes_count += 1
        status = "liked"
    
    db.session.commit()
    return jsonify({"status": status, "count": post.likes_count})

@app.route('/api/health')
def health():
    return jsonify({
        "status": "online",
        "database": "connected" if os.environ.get('DATABASE_URL') else "local-sqlite"
    })

@app.route('/')
def index():
    return send_from_directory('../', 'index.html')

@app.route('/<path:path>')
def catch_all(path):
    # Try to serve the file from the root directory
    return send_from_directory('../', path)
try:
    with app.app_context():
        db.create_all()
except Exception as e:
    print(f"Database initialization error: {e}")

if __name__ == '__main__':
    app.run(port=5000, debug=True)
