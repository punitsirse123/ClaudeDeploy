from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from scrapy_spider import run_spider
import pandas as pd
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    requests_used = db.Column(db.Integer, default=0)
    last_reset = db.Column(db.DateTime, default=datetime.utcnow)
    max_requests = db.Column(db.Integer, default=10)  # Default quota

    def check_reset_quota(self):
        """Reset quota if a month has passed"""
        if datetime.utcnow() - self.last_reset > timedelta(days=30):
            self.requests_used = 0
            self.last_reset = datetime.utcnow()
            db.session.commit()

    def can_make_request(self):
        """Check if user can make a request"""
        self.check_reset_quota()
        return self.requests_used < self.max_requests

    def increment_requests(self):
        """Increment request count"""
        self.requests_used += 1
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Email already exists'}), 400

    hashed_password = generate_password_hash(password)
    new_user = User(email=email, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User created successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password, password):
        login_user(user)
        return jsonify({'message': 'Login successful'}), 200
    return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/process', methods=['POST'])
@login_required
def process_keywords():
    if not current_user.can_make_request():
        return jsonify({'message': 'Quota exceeded. Please wait for reset.'}), 429

    data = request.json
    keywords = data.get('keywords', [])
    asins = data.get('asins', [])

    if len(keywords) != len(asins):
        return jsonify({'message': 'Keywords and ASINs must be of equal length'}), 400

    results = run_spider(keywords, asins)
    current_user.increment_requests()

    return jsonify(results), 200

@app.route('/quota', methods=['GET'])
@login_required
def get_quota():
    current_user.check_reset_quota()
    return jsonify({
        'max_requests': current_user.max_requests,
        'requests_used': current_user.requests_used,
        'last_reset': current_user.last_reset.isoformat()
    }), 200

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Logged out successfully'}), 200

if __name__ == '__main__':
    app.run(debug=True)