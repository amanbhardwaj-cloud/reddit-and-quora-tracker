from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import os
import re
import secrets

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'dashboard.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

db = SQLAlchemy(app)


# ============ MODELS ============

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(300), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), default='content')  # content, admin, manager
    theme = db.Column(db.String(20), default='dark')  # dark or light
    avatar_color = db.Column(db.String(20), default='#8b5cf6')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self, include_email=True):
        d = {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'theme': self.theme,
            'avatar_color': self.avatar_color,
        }
        if include_email:
            d['email'] = self.email
        return d


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
            'title': self.title,
            'engagement_link': self.engagement_link,
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
    sort_order = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id, 'platform': self.platform, 'period_type': self.period_type,
            'period_label': self.period_label, 'total_views': self.total_views,
            'total_karma': self.total_karma or 0, 'total_contributions': self.total_contributions or 0,
            'sort_order': self.sort_order or 0,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
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
    monthly_metrics = Metric.query.filter_by(platform=platform, period_type='Monthly').all()
    total_views = sum(parse_views(m.total_views) for m in monthly_metrics)
    total_karma = sum(m.total_karma or 0 for m in monthly_metrics)
    total_contributions = sum(m.total_contributions or 0 for m in monthly_metrics)
    
    all_time = Metric.query.filter_by(platform=platform, period_type='Total').first()
    if all_time:
        all_time.total_views = format_views(total_views)
        all_time.total_karma = total_karma
        all_time.total_contributions = total_contributions
        db.session.commit()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


# ============ AUTH ROUTES ============

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('index.html')


@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect('/')
    return render_template('login.html')


@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    name = (data.get('name') or '').strip()
    
    if not email or not password or not name:
        return jsonify({'error': 'All fields are required'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return jsonify({'error': 'Invalid email address'}), 400
    
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 400
    
    # Pick color based on existing count
    colors = ['#8b5cf6', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#06b6d4', '#ff6b35']
    color = colors[User.query.count() % len(colors)]
    
    user = User(email=email, name=name, avatar_color=color)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    session.permanent = True
    session['user_id'] = user.id
    
    return jsonify({'success': True, 'user': user.to_dict()})


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    session.permanent = True
    session['user_id'] = user.id
    
    return jsonify({'success': True, 'user': user.to_dict()})


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'success': True})


@app.route('/api/auth/me', methods=['GET'])
def get_me():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    return jsonify(user.to_dict())


@app.route('/api/auth/profile', methods=['PUT'])
@login_required
def update_profile():
    user = get_current_user()
    data = request.json
    
    if 'name' in data and data['name']:
        user.name = data['name'].strip()
    if 'theme' in data and data['theme'] in ['dark', 'light']:
        user.theme = data['theme']
    if 'avatar_color' in data:
        user.avatar_color = data['avatar_color']
    if 'password' in data and data['password']:
        if len(data['password']) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        user.set_password(data['password'])
    
    db.session.commit()
    return jsonify({'success': True, 'user': user.to_dict()})


# ============ TEAM ROUTES ============

@app.route('/api/team', methods=['GET'])
@login_required
def get_team():
    users = User.query.order_by(User.created_at.asc()).all()
    return jsonify([u.to_dict(include_email=False) for u in users])


# ============ ENGAGEMENTS ============

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


# ============ PIPELINE ============

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


# ============ METRICS ============

@app.route('/api/metrics', methods=['GET'])
@login_required
def get_metrics():
    platform = request.args.get('platform')
    query = Metric.query
    if platform: query = query.filter_by(platform=platform)
    return jsonify([m.to_dict() for m in query.order_by(Metric.sort_order.asc()).all()])


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
    period_type = m.period_type
    db.session.delete(m)
    db.session.commit()
    if period_type == 'Monthly':
        recalculate_all_time(platform)
    return jsonify({'success': True})


# ============ STATS ============

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
        'pipeline_total': len(all_pipeline),
        'pipeline_picked': sum(1 for p in all_pipeline if p.status != 'Not Picked'),
        'pipeline_not_picked': sum(1 for p in all_pipeline if p.status == 'Not Picked'),
        'drafts_count': len(all_drafts),
        'pipeline_and_drafts': len(all_pipeline) + len(all_drafts),  # Combined
    }
    
    # Monthly data from engagements
    monthly_data = {}
    for e in all_engagements:
        m = 'Unknown'
        if e.post_date:
            try:
                d = datetime.strptime(e.post_date, '%Y-%m-%d')
                m = d.strftime('%b %Y')
            except:
                m = e.post_date
        elif e.created_at:
            m = e.created_at.strftime('%b %Y')
        
        if m not in monthly_data:
            monthly_data[m] = {'reddit': 0, 'quora': 0}
        if e.platform == 'Reddit':
            monthly_data[m]['reddit'] += 1
        else:
            monthly_data[m]['quora'] += 1
    
    weekly_trend = []
    now = datetime.utcnow()
    for i in range(7, -1, -1):
        week_start = now - timedelta(days=(i+1)*7)
        week_end = now - timedelta(days=i*7)
        reddit_count = sum(1 for e in all_engagements if e.platform == 'Reddit' and e.created_at and week_start <= e.created_at < week_end)
        quora_count = sum(1 for e in all_engagements if e.platform == 'Quora' and e.created_at and week_start <= e.created_at < week_end)
        weekly_trend.append({
            'week': f"W{8-i}",
            'date': week_end.strftime('%b %d'),
            'reddit': reddit_count,
            'quora': quora_count
        })
    
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
        'monthly_data': monthly_data,
        'weekly_trend': weekly_trend,
        'top_posts': top_posts_data
    })


@app.route('/api/health')
def health():
    return {'status': 'ok'}


@app.route('/api/seed', methods=['POST'])
@login_required
def seed_data():
    from seed_data import seed_database
    return jsonify(seed_database(db, Engagement, Pipeline, Metric, User))


with app.app_context():
    db.create_all()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
