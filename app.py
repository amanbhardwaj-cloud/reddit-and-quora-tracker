from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import os
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'spyne-tracker-secret-key-change-in-prod-2026')

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'dashboard.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login_page'


# ============ MODELS ============

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(300), nullable=False)
    display_name = db.Column(db.String(100))
    role = db.Column(db.String(50), default='member')  # admin, member
    avatar_color = db.Column(db.String(20), default='#8b5cf6')
    theme = db.Column(db.String(20), default='dark')  # dark, light
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, pwd):
        self.password_hash = generate_password_hash(pwd)
    
    def check_password(self, pwd):
        return check_password_hash(self.password_hash, pwd)
    
    def to_dict(self):
        return {
            'id': self.id, 'email': self.email, 'display_name': self.display_name,
            'role': self.role, 'avatar_color': self.avatar_color, 'theme': self.theme,
            'is_admin': self.role == 'admin'
        }


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Engagement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), nullable=False)
    owner = db.Column(db.String(100))
    post_date = db.Column(db.String(50))
    community = db.Column(db.String(200))
    title = db.Column(db.String(500))
    engagement_link = db.Column(db.String(1000))
    original_question_link = db.Column(db.String(1000))
    product_target = db.Column(db.String(100))
    account_details = db.Column(db.Text)
    views = db.Column(db.Integer, default=0)
    upvotes = db.Column(db.Integer, default=0)
    comments = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='Live')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id, 'platform': self.platform, 'owner': self.owner,
            'post_date': self.post_date, 'community': self.community,
            'title': self.title, 'engagement_link': self.engagement_link,
            'original_question_link': self.original_question_link,
            'product_target': self.product_target, 'account_details': self.account_details,
            'views': self.views or 0, 'upvotes': self.upvotes or 0, 'comments': self.comments or 0,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Pipeline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    platform = db.Column(db.String(50))
    status = db.Column(db.String(50), default='Not Picked')
    assigned_to = db.Column(db.String(100))
    notes = db.Column(db.Text)
    item_type = db.Column(db.String(50), default='Pipeline')
    community = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id, 'content': self.content, 'platform': self.platform,
            'status': self.status, 'assigned_to': self.assigned_to, 'notes': self.notes,
            'item_type': self.item_type, 'community': self.community,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Metric(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), nullable=False)
    period_type = db.Column(db.String(50), nullable=False)
    period_label = db.Column(db.String(100))
    total_views = db.Column(db.String(50), default='0')
    total_karma = db.Column(db.Integer, default=0)
    total_contributions = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id, 'platform': self.platform, 'period_type': self.period_type,
            'period_label': self.period_label, 'total_views': self.total_views,
            'total_karma': self.total_karma or 0, 'total_contributions': self.total_contributions or 0
        }


class CommunityMetric(db.Model):
    """Reddit subreddit-specific metrics"""
    id = db.Column(db.Integer, primary_key=True)
    community = db.Column(db.String(200), nullable=False)
    period_label = db.Column(db.String(100))  # All Time, April 2026, May 2026, etc.
    views = db.Column(db.Integer, default=0)
    upvotes = db.Column(db.Integer, default=0)
    comments = db.Column(db.Integer, default=0)
    posts_count = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id, 'community': self.community,
            'period_label': self.period_label,
            'views': self.views or 0, 'upvotes': self.upvotes or 0,
            'comments': self.comments or 0, 'posts_count': self.posts_count or 0
        }


# ============ HELPERS ============

def parse_views(views_str):
    if not views_str:
        return 0
    views_str = str(views_str).strip().lower().replace(',', '')
    try:
        if 'k' in views_str:
            return int(float(views_str.replace('k', '')) * 1000)
        if 'm' in views_str:
            return int(float(views_str.replace('m', '')) * 1000000)
        return int(float(views_str))
    except:
        return 0


def format_views(num):
    if num >= 1000000:
        return f"{num/1000000:.1f}m".replace('.0m', 'm')
    if num >= 1000:
        return f"{num/1000:.1f}k".replace('.0k', 'k')
    return str(num)


def recalculate_all_time(platform):
    monthly = Metric.query.filter_by(platform=platform, period_type='Monthly').all()
    total_v = sum(parse_views(m.total_views) for m in monthly)
    total_k = sum(m.total_karma or 0 for m in monthly)
    total_c = sum(m.total_contributions or 0 for m in monthly)
    
    all_time = Metric.query.filter_by(platform=platform, period_type='Total').first()
    if all_time:
        all_time.total_views = format_views(total_v)
        all_time.total_karma = total_k
        all_time.total_contributions = total_c
        db.session.commit()


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


# ============ AUTH ROUTES ============

@app.route('/login', methods=['GET'])
def login_page():
    if current_user.is_authenticated:
        return redirect('/')
    return render_template('login.html')


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json
    user = User.query.filter_by(email=data.get('email', '').lower().strip()).first()
    if user and user.check_password(data.get('password', '')):
        login_user(user, remember=True)
        return jsonify({'success': True, 'user': user.to_dict()})
    return jsonify({'error': 'Invalid email or password'}), 401


@app.route('/api/auth/signup', methods=['POST'])
def api_signup():
    data = request.json
    email = data.get('email', '').lower().strip()
    password = data.get('password', '')
    display_name = data.get('display_name', '').strip() or email.split('@')[0]
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 400
    
    # First user becomes admin
    is_first = User.query.count() == 0
    
    user = User(
        email=email,
        display_name=display_name,
        role='admin' if is_first else 'member',
        avatar_color=data.get('avatar_color', '#8b5cf6')
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    login_user(user, remember=True)
    return jsonify({'success': True, 'user': user.to_dict()}), 201


@app.route('/api/auth/logout', methods=['POST'])
@login_required
def api_logout():
    logout_user()
    return jsonify({'success': True})


@app.route('/api/auth/me', methods=['GET'])
def api_me():
    if current_user.is_authenticated:
        return jsonify({'user': current_user.to_dict()})
    return jsonify({'user': None}), 401


@app.route('/api/auth/update-profile', methods=['POST'])
@login_required
def update_profile():
    data = request.json
    if 'display_name' in data:
        current_user.display_name = data['display_name']
    if 'avatar_color' in data:
        current_user.avatar_color = data['avatar_color']
    if 'theme' in data:
        current_user.theme = data['theme']
    if 'new_password' in data and data['new_password']:
        current_user.set_password(data['new_password'])
    db.session.commit()
    return jsonify({'success': True, 'user': current_user.to_dict()})


# Team management (admin-controlled)
@app.route('/api/team', methods=['GET'])
@login_required
def get_team():
    users = User.query.all()
    return jsonify([u.to_dict() for u in users])


@app.route('/api/team/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_team_member(user_id):
    if user_id == current_user.id:
        return jsonify({'error': "Can't delete yourself"}), 400
    u = User.query.get_or_404(user_id)
    db.session.delete(u)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/team/<int:user_id>/role', methods=['PUT'])
@login_required
@admin_required
def update_role(user_id):
    u = User.query.get_or_404(user_id)
    u.role = request.json.get('role', 'member')
    db.session.commit()
    return jsonify({'success': True, 'user': u.to_dict()})


# ============ MAIN ============

@app.route('/')
@login_required
def index():
    return render_template('index.html')


# ENGAGEMENTS
@app.route('/api/engagements', methods=['GET'])
@login_required
def get_engagements():
    platform = request.args.get('platform')
    query = Engagement.query
    if platform:
        query = query.filter_by(platform=platform)
    engagements = query.all()
    
    def sort_key(e):
        if e.post_date:
            try:
                return datetime.strptime(e.post_date, '%Y-%m-%d')
            except:
                pass
        return e.created_at or datetime.min
    
    engagements.sort(key=sort_key, reverse=True)
    return jsonify([e.to_dict() for e in engagements])


@app.route('/api/engagements', methods=['POST'])
@login_required
def create_engagement():
    e = Engagement(**{k: v for k, v in request.json.items() if hasattr(Engagement, k)})
    db.session.add(e)
    db.session.commit()
    return jsonify(e.to_dict()), 201


@app.route('/api/engagements/<int:id>', methods=['PUT'])
@login_required
def update_engagement(id):
    e = Engagement.query.get_or_404(id)
    for k, v in request.json.items():
        if hasattr(e, k): setattr(e, k, v)
    db.session.commit()
    return jsonify(e.to_dict())


@app.route('/api/engagements/<int:id>', methods=['DELETE'])
@login_required
def delete_engagement(id):
    e = Engagement.query.get_or_404(id)
    db.session.delete(e)
    db.session.commit()
    return jsonify({'success': True})


# PIPELINE
@app.route('/api/pipeline', methods=['GET'])
@login_required
def get_pipeline():
    platform = request.args.get('platform')
    item_type = request.args.get('item_type')
    query = Pipeline.query
    if platform: query = query.filter_by(platform=platform)
    if item_type: query = query.filter_by(item_type=item_type)
    return jsonify([p.to_dict() for p in query.order_by(Pipeline.created_at.desc()).all()])


@app.route('/api/pipeline', methods=['POST'])
@login_required
def create_pipeline():
    p = Pipeline(**{k: v for k, v in request.json.items() if hasattr(Pipeline, k)})
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201


@app.route('/api/pipeline/<int:id>', methods=['PUT'])
@login_required
def update_pipeline(id):
    p = Pipeline.query.get_or_404(id)
    for k, v in request.json.items():
        if hasattr(p, k): setattr(p, k, v)
    db.session.commit()
    return jsonify(p.to_dict())


@app.route('/api/pipeline/<int:id>', methods=['DELETE'])
@login_required
def delete_pipeline(id):
    p = Pipeline.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'success': True})


# METRICS
@app.route('/api/metrics', methods=['GET'])
@login_required
def get_metrics():
    platform = request.args.get('platform')
    query = Metric.query
    if platform: query = query.filter_by(platform=platform)
    return jsonify([m.to_dict() for m in query.all()])


@app.route('/api/metrics', methods=['POST'])
@login_required
def create_metric():
    m = Metric(**{k: v for k, v in request.json.items() if hasattr(Metric, k)})
    db.session.add(m)
    db.session.commit()
    if m.period_type == 'Monthly':
        recalculate_all_time(m.platform)
    return jsonify(m.to_dict()), 201


@app.route('/api/metrics/<int:id>', methods=['PUT'])
@login_required
def update_metric(id):
    m = Metric.query.get_or_404(id)
    for k, v in request.json.items():
        if hasattr(m, k): setattr(m, k, v)
    db.session.commit()
    if m.period_type == 'Monthly':
        recalculate_all_time(m.platform)
    return jsonify(m.to_dict())


@app.route('/api/metrics/<int:id>', methods=['DELETE'])
@login_required
def delete_metric(id):
    m = Metric.query.get_or_404(id)
    platform = m.platform
    pt = m.period_type
    db.session.delete(m)
    db.session.commit()
    if pt == 'Monthly':
        recalculate_all_time(platform)
    return jsonify({'success': True})


# COMMUNITY METRICS
@app.route('/api/community-metrics', methods=['GET'])
@login_required
def get_community_metrics():
    metrics = CommunityMetric.query.all()
    return jsonify([m.to_dict() for m in metrics])


@app.route('/api/community-metrics', methods=['POST'])
@login_required
def create_community_metric():
    m = CommunityMetric(**{k: v for k, v in request.json.items() if hasattr(CommunityMetric, k)})
    db.session.add(m)
    db.session.commit()
    return jsonify(m.to_dict()), 201


@app.route('/api/community-metrics/<int:id>', methods=['PUT'])
@login_required
def update_community_metric(id):
    m = CommunityMetric.query.get_or_404(id)
    for k, v in request.json.items():
        if hasattr(m, k): setattr(m, k, v)
    db.session.commit()
    return jsonify(m.to_dict())


@app.route('/api/community-metrics/<int:id>', methods=['DELETE'])
@login_required
def delete_community_metric(id):
    m = CommunityMetric.query.get_or_404(id)
    db.session.delete(m)
    db.session.commit()
    return jsonify({'success': True})


def calculate_platform_stats(platform=None):
    eng_query = Engagement.query
    pipe_query = Pipeline.query
    if platform:
        eng_query = eng_query.filter_by(platform=platform)
        pipe_query = pipe_query.filter_by(platform=platform)
    
    engagements = eng_query.all()
    pipeline_items = pipe_query.filter_by(item_type='Pipeline').all()
    drafts = pipe_query.filter_by(item_type='Draft').all()
    
    return {
        'total': len(engagements),
        'live_count': sum(1 for e in engagements if e.status == 'Live'),
        'pipeline_total': len(pipeline_items),
        'pipeline_picked': sum(1 for p in pipeline_items if p.status != 'Not Picked'),
        'pipeline_not_picked': sum(1 for p in pipeline_items if p.status == 'Not Picked'),
        'drafts_count': len(drafts),
    }


@app.route('/api/master-stats', methods=['GET'])
@login_required
def get_master_stats():
    all_engagements = Engagement.query.all()
    all_pipeline = Pipeline.query.filter_by(item_type='Pipeline').all()
    all_drafts = Pipeline.query.filter_by(item_type='Draft').all()
    
    combined = {
        'total': len(all_engagements),
        'reddit_count': sum(1 for e in all_engagements if e.platform == 'Reddit'),
        'quora_count': sum(1 for e in all_engagements if e.platform == 'Quora'),
        'live_count': sum(1 for e in all_engagements if e.status == 'Live'),
        'pipeline_total': len(all_pipeline) + len(all_drafts),  # Combined!
        'pipeline_picked': sum(1 for p in all_pipeline if p.status != 'Not Picked'),
        'pipeline_not_picked': sum(1 for p in all_pipeline if p.status == 'Not Picked'),
        'drafts_count': len(all_drafts),
    }
    
    top_posts = sorted(all_engagements, key=lambda e: (e.upvotes or 0) + (e.comments or 0) + (e.views or 0)//100, reverse=True)[:10]
    top_posts_data = [{
        'id': e.id, 'title': e.title, 'platform': e.platform, 'owner': e.owner,
        'views': e.views or 0, 'upvotes': e.upvotes or 0, 'comments': e.comments or 0,
        'engagement_score': (e.upvotes or 0) + (e.comments or 0) + (e.views or 0)//100,
        'engagement_link': e.engagement_link
    } for e in top_posts if (e.upvotes or 0) + (e.comments or 0) + (e.views or 0) > 0]
    
    return jsonify({
        'combined': combined,
        'reddit': calculate_platform_stats('Reddit'),
        'quora': calculate_platform_stats('Quora'),
        'top_posts': top_posts_data
    })


# ADVANCED CHART DATA with date range and metric type
@app.route('/api/chart-data', methods=['GET'])
@login_required
def chart_data():
    """
    Returns data filtered by:
    - metric: views, upvotes, contributions
    - range: 7d, 15d, 30d, custom
    - start_date, end_date (for custom)
    - groupby: day, week, month
    """
    metric = request.args.get('metric', 'views')  # views, upvotes, contributions
    date_range = request.args.get('range', '30d')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    groupby = request.args.get('groupby', 'day')
    
    now = datetime.utcnow().date()
    
    if date_range == '7d':
        start = now - timedelta(days=7)
        end = now
    elif date_range == '15d':
        start = now - timedelta(days=15)
        end = now
    elif date_range == '30d':
        start = now - timedelta(days=30)
        end = now
    elif date_range == '90d':
        start = now - timedelta(days=90)
        end = now
    elif date_range == 'custom' and start_date_str and end_date_str:
        try:
            start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except:
            start = now - timedelta(days=30)
            end = now
    else:
        start = now - timedelta(days=30)
        end = now
    
    # For views/upvotes/comments: use engagement data
    engagements = Engagement.query.all()
    
    # Build date buckets
    buckets = {}
    current = start
    while current <= end:
        if groupby == 'day':
            label = current.strftime('%b %d')
            buckets[current.isoformat()] = {'label': label, 'Reddit': 0, 'Quora': 0}
            current += timedelta(days=1)
        elif groupby == 'week':
            label = f"Week of {current.strftime('%b %d')}"
            buckets[current.isoformat()] = {'label': label, 'Reddit': 0, 'Quora': 0}
            current += timedelta(days=7)
        else:  # month
            label = current.strftime('%b %Y')
            key = current.replace(day=1).isoformat()
            if key not in buckets:
                buckets[key] = {'label': label, 'Reddit': 0, 'Quora': 0}
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year+1, month=1, day=1)
            else:
                current = current.replace(month=current.month+1, day=1)
    
    # Map metric name to field
    field_map = {
        'views': 'views',
        'upvotes': 'upvotes',
        'contributions': 'comments',  # contributions = comments
        'posts': None  # count of posts
    }
    field = field_map.get(metric, 'views')
    
    # Aggregate
    for e in engagements:
        post_date = None
        if e.post_date:
            try:
                post_date = datetime.strptime(e.post_date, '%Y-%m-%d').date()
            except:
                pass
        if not post_date and e.created_at:
            post_date = e.created_at.date()
        
        if not post_date or post_date < start or post_date > end:
            continue
        
        # Find correct bucket
        if groupby == 'day':
            key = post_date.isoformat()
        elif groupby == 'week':
            # Find the start of the bucket week
            days_from_start = (post_date - start).days
            bucket_start = start + timedelta(days=(days_from_start // 7) * 7)
            key = bucket_start.isoformat()
        else:  # month
            key = post_date.replace(day=1).isoformat()
        
        if key in buckets:
            value = 1 if field is None else (getattr(e, field, 0) or 0)
            buckets[key][e.platform] = buckets[key].get(e.platform, 0) + value
    
    sorted_keys = sorted(buckets.keys())
    return jsonify({
        'labels': [buckets[k]['label'] for k in sorted_keys],
        'reddit': [buckets[k].get('Reddit', 0) for k in sorted_keys],
        'quora': [buckets[k].get('Quora', 0) for k in sorted_keys],
        'metric': metric,
        'range': date_range,
        'groupby': groupby
    })


@app.route('/api/health')
def health():
    return {'status': 'ok'}


@app.route('/api/seed', methods=['POST'])
@login_required
def seed_data():
    from seed_data import seed_database
    return jsonify(seed_database(db, Engagement, Pipeline, Metric, CommunityMetric, User))


# Initialize DB and ensure default admin team exists
def init_db():
    """Initialize database - handles schema migrations gracefully"""
    try:
        # Drop and recreate ALL tables if schema mismatch (SQLite only)
        # This is safe because we re-seed data on first login
        if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
            try:
                # Test if schema is compatible
                User.query.first()
                Engagement.query.first()
                Pipeline.query.first()
                Metric.query.first()
                CommunityMetric.query.first()
            except Exception as e:
                print(f"⚠️  Schema mismatch detected: {e}")
                print("🔄 Recreating database with new schema...")
                db.drop_all()
                db.create_all()
                print("✅ Database recreated")
        else:
            db.create_all()
        
        # Ensure tables exist
        db.create_all()
        
        # Ensure team members exist (Aman, Astha, Komal)
        default_team = [
            {'email': 'aman.bhardwaj@spyne.ai', 'display_name': 'Aman Bhardwaj', 'role': 'admin', 'avatar_color': '#8b5cf6', 'password': 'spyne123'},
            {'email': 'astha@spyne.ai', 'display_name': 'Astha', 'role': 'member', 'avatar_color': '#3b82f6', 'password': 'spyne123'},
            {'email': 'komal@spyne.ai', 'display_name': 'Komal', 'role': 'member', 'avatar_color': '#10b981', 'password': 'spyne123'},
        ]
        for t in default_team:
            if not User.query.filter_by(email=t['email']).first():
                u = User(
                    email=t['email'], display_name=t['display_name'],
                    role=t['role'], avatar_color=t['avatar_color']
                )
                u.set_password(t['password'])
                db.session.add(u)
        db.session.commit()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ DB init error: {e}")
        # Try to recover by creating fresh tables
        try:
            db.session.rollback()
            db.drop_all()
            db.create_all()
            print("🔄 Fresh database created after error")
        except Exception as e2:
            print(f"❌ Recovery failed: {e2}")


with app.app_context():
    init_db()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
