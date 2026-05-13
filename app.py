from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'dashboard.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

db = SQLAlchemy(app)


# ============ MODELS ============

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
    id = db.Column(db.Integer, primary_key=True)
    community = db.Column(db.String(200), nullable=False)
    period_label = db.Column(db.String(100))
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

def parse_views(s):
    if not s: return 0
    s = str(s).strip().lower().replace(',', '')
    try:
        if 'k' in s: return int(float(s.replace('k', '')) * 1000)
        if 'm' in s: return int(float(s.replace('m', '')) * 1000000)
        return int(float(s))
    except:
        return 0


def format_views(n):
    if n >= 1000000: return f"{n/1000000:.1f}m".replace('.0m', 'm')
    if n >= 1000: return f"{n/1000:.1f}k".replace('.0k', 'k')
    return str(n)


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


def auto_sync_monthly_metrics():
    """Auto-update monthly metrics from engagement data"""
    all_engs = Engagement.query.all()
    monthly_counts = {}
    for e in all_engs:
        if not e.post_date: continue
        try:
            d = datetime.strptime(e.post_date, '%Y-%m-%d')
            period_label = d.strftime('%B %Y')
        except:
            continue
        key = (e.platform, period_label)
        if key not in monthly_counts:
            monthly_counts[key] = {'count': 0, 'views': 0, 'upvotes': 0, 'comments': 0}
        monthly_counts[key]['count'] += 1
        monthly_counts[key]['views'] += e.views or 0
        monthly_counts[key]['upvotes'] += e.upvotes or 0
        monthly_counts[key]['comments'] += e.comments or 0
    
    for (platform, period_label), counts in monthly_counts.items():
        m = Metric.query.filter_by(platform=platform, period_label=period_label, period_type='Monthly').first()
        if not m:
            m = Metric(platform=platform, period_label=period_label, period_type='Monthly',
                      total_views='0', total_karma=0, total_contributions=0)
            db.session.add(m)
        m.total_views = format_views(counts['views'])
        m.total_contributions = counts['count']
    
    db.session.commit()
    recalculate_all_time('Reddit')
    recalculate_all_time('Quora')
    auto_sync_community_counts()


def auto_sync_community_counts():
    all_engs = Engagement.query.filter_by(platform='Reddit').all()
    community_counts = {}
    for e in all_engs:
        if e.community and e.community.startswith('r/'):
            community_counts[e.community] = community_counts.get(e.community, 0) + 1
    for community, count in community_counts.items():
        cm = CommunityMetric.query.filter_by(community=community, period_label='All Time').first()
        if not cm:
            cm = CommunityMetric(community=community, period_label='All Time', posts_count=0)
            db.session.add(cm)
        cm.posts_count = count
    existing = CommunityMetric.query.filter_by(period_label='All Time').all()
    for cm in existing:
        if cm.community not in community_counts:
            cm.posts_count = 0
    db.session.commit()


# ============ ROUTES ============

@app.route('/')
def index():
    return render_template('index.html')


# Fixed team members (no auth, just display)
@app.route('/api/team', methods=['GET'])
def get_team():
    return jsonify([
        {'name': 'Aman', 'avatar_color': '#8b5cf6'},
        {'name': 'Astha', 'avatar_color': '#3b82f6'},
        {'name': 'Komal', 'avatar_color': '#10b981'},
    ])


# ENGAGEMENTS
@app.route('/api/engagements', methods=['GET'])
def get_engagements():
    platform = request.args.get('platform')
    query = Engagement.query
    if platform: query = query.filter_by(platform=platform)
    engagements = query.all()
    def sort_key(e):
        if e.post_date:
            try: return datetime.strptime(e.post_date, '%Y-%m-%d')
            except: pass
        return e.created_at or datetime.min
    engagements.sort(key=sort_key, reverse=True)
    return jsonify([e.to_dict() for e in engagements])


@app.route('/api/engagements', methods=['POST'])
def create_engagement():
    e = Engagement(**{k: v for k, v in request.json.items() if hasattr(Engagement, k)})
    db.session.add(e)
    db.session.commit()
    auto_sync_monthly_metrics()
    return jsonify(e.to_dict()), 201


@app.route('/api/engagements/<int:id>', methods=['PUT'])
def update_engagement(id):
    e = Engagement.query.get_or_404(id)
    for k, v in request.json.items():
        if hasattr(e, k): setattr(e, k, v)
    db.session.commit()
    auto_sync_monthly_metrics()
    return jsonify(e.to_dict())


@app.route('/api/engagements/<int:id>', methods=['DELETE'])
def delete_engagement(id):
    e = Engagement.query.get_or_404(id)
    db.session.delete(e)
    db.session.commit()
    auto_sync_monthly_metrics()
    return jsonify({'success': True})


# PIPELINE
@app.route('/api/pipeline', methods=['GET'])
def get_pipeline():
    platform = request.args.get('platform')
    item_type = request.args.get('item_type')
    query = Pipeline.query
    if platform: query = query.filter_by(platform=platform)
    if item_type: query = query.filter_by(item_type=item_type)
    return jsonify([p.to_dict() for p in query.order_by(Pipeline.created_at.desc()).all()])


@app.route('/api/pipeline', methods=['POST'])
def create_pipeline():
    p = Pipeline(**{k: v for k, v in request.json.items() if hasattr(Pipeline, k)})
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201


@app.route('/api/pipeline/<int:id>', methods=['PUT'])
def update_pipeline(id):
    p = Pipeline.query.get_or_404(id)
    for k, v in request.json.items():
        if hasattr(p, k): setattr(p, k, v)
    db.session.commit()
    return jsonify(p.to_dict())


@app.route('/api/pipeline/<int:id>', methods=['DELETE'])
def delete_pipeline(id):
    p = Pipeline.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'success': True})


# Pick from Pipeline → Convert to Engagement
@app.route('/api/pipeline/<int:id>/pick', methods=['POST'])
def pick_pipeline_item(id):
    p = Pipeline.query.get_or_404(id)
    data = request.json or {}
    post_date = data.get('post_date') or datetime.utcnow().strftime('%Y-%m-%d')
    eng = Engagement(
        platform=p.platform,
        title=p.content[:500] if p.content else 'Untitled',
        owner=p.assigned_to or data.get('owner', ''),
        community=p.community or data.get('community', ''),
        post_date=post_date,
        engagement_link=data.get('engagement_link', ''),
        status='Live',
        product_target=data.get('product_target', 'Generic')
    )
    db.session.add(eng)
    db.session.delete(p)
    db.session.commit()
    auto_sync_monthly_metrics()
    return jsonify({'success': True, 'engagement': eng.to_dict()})


# METRICS
@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    platform = request.args.get('platform')
    query = Metric.query
    if platform: query = query.filter_by(platform=platform)
    return jsonify([m.to_dict() for m in query.all()])


@app.route('/api/metrics', methods=['POST'])
def create_metric():
    m = Metric(**{k: v for k, v in request.json.items() if hasattr(Metric, k)})
    db.session.add(m)
    db.session.commit()
    if m.period_type == 'Monthly': recalculate_all_time(m.platform)
    return jsonify(m.to_dict()), 201


@app.route('/api/metrics/<int:id>', methods=['PUT'])
def update_metric(id):
    m = Metric.query.get_or_404(id)
    for k, v in request.json.items():
        if hasattr(m, k): setattr(m, k, v)
    db.session.commit()
    if m.period_type == 'Monthly': recalculate_all_time(m.platform)
    return jsonify(m.to_dict())


@app.route('/api/metrics/<int:id>', methods=['DELETE'])
def delete_metric(id):
    m = Metric.query.get_or_404(id)
    platform = m.platform
    pt = m.period_type
    db.session.delete(m)
    db.session.commit()
    if pt == 'Monthly': recalculate_all_time(platform)
    return jsonify({'success': True})


# COMMUNITY METRICS
@app.route('/api/community-metrics', methods=['GET'])
def get_community_metrics():
    return jsonify([m.to_dict() for m in CommunityMetric.query.all()])


@app.route('/api/community-metrics', methods=['POST'])
def create_community_metric():
    m = CommunityMetric(**{k: v for k, v in request.json.items() if hasattr(CommunityMetric, k)})
    db.session.add(m)
    db.session.commit()
    return jsonify(m.to_dict()), 201


@app.route('/api/community-metrics/<int:id>', methods=['PUT'])
def update_community_metric(id):
    m = CommunityMetric.query.get_or_404(id)
    for k, v in request.json.items():
        if hasattr(m, k): setattr(m, k, v)
    db.session.commit()
    return jsonify(m.to_dict())


@app.route('/api/community-metrics/<int:id>', methods=['DELETE'])
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
def get_master_stats():
    all_engagements = Engagement.query.all()
    all_pipeline = Pipeline.query.filter_by(item_type='Pipeline').all()
    all_drafts = Pipeline.query.filter_by(item_type='Draft').all()
    
    combined = {
        'total': len(all_engagements),
        'reddit_count': sum(1 for e in all_engagements if e.platform == 'Reddit'),
        'quora_count': sum(1 for e in all_engagements if e.platform == 'Quora'),
        'live_count': sum(1 for e in all_engagements if e.status == 'Live'),
        'pipeline_total': len(all_pipeline) + len(all_drafts),
        'pipeline_picked': sum(1 for p in all_pipeline if p.status != 'Not Picked'),
        'pipeline_not_picked': sum(1 for p in all_pipeline if p.status == 'Not Picked'),
        'drafts_count': len(all_drafts),
    }
    
    top_posts = sorted(all_engagements, key=lambda e: (e.upvotes or 0) + (e.comments or 0) + (e.views or 0)//100, reverse=True)[:5]
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


@app.route('/api/chart-data', methods=['GET'])
def chart_data():
    metric = request.args.get('metric', 'views')
    date_range = request.args.get('range', '30d')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    groupby = request.args.get('groupby', 'day')
    
    now = datetime.utcnow().date()
    if date_range == '7d': start, end = now - timedelta(days=7), now
    elif date_range == '15d': start, end = now - timedelta(days=15), now
    elif date_range == '30d': start, end = now - timedelta(days=30), now
    elif date_range == '90d': start, end = now - timedelta(days=90), now
    elif date_range == 'custom' and start_date_str and end_date_str:
        try:
            start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except:
            start, end = now - timedelta(days=30), now
    else:
        start, end = now - timedelta(days=30), now
    
    engagements = Engagement.query.all()
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
        else:
            label = current.strftime('%b %Y')
            key = current.replace(day=1).isoformat()
            if key not in buckets:
                buckets[key] = {'label': label, 'Reddit': 0, 'Quora': 0}
            if current.month == 12:
                current = current.replace(year=current.year+1, month=1, day=1)
            else:
                current = current.replace(month=current.month+1, day=1)
    
    field_map = {'views': 'views', 'upvotes': 'upvotes', 'contributions': 'comments', 'posts': None}
    field = field_map.get(metric, 'views')
    
    for e in engagements:
        post_date = None
        if e.post_date:
            try: post_date = datetime.strptime(e.post_date, '%Y-%m-%d').date()
            except: pass
        if not post_date and e.created_at: post_date = e.created_at.date()
        if not post_date or post_date < start or post_date > end: continue
        
        if groupby == 'day': key = post_date.isoformat()
        elif groupby == 'week':
            days_from_start = (post_date - start).days
            bucket_start = start + timedelta(days=(days_from_start // 7) * 7)
            key = bucket_start.isoformat()
        else: key = post_date.replace(day=1).isoformat()
        
        if key in buckets:
            value = 1 if field is None else (getattr(e, field, 0) or 0)
            buckets[key][e.platform] = buckets[key].get(e.platform, 0) + value
    
    sorted_keys = sorted(buckets.keys())
    return jsonify({
        'labels': [buckets[k]['label'] for k in sorted_keys],
        'reddit': [buckets[k].get('Reddit', 0) for k in sorted_keys],
        'quora': [buckets[k].get('Quora', 0) for k in sorted_keys],
        'metric': metric, 'range': date_range, 'groupby': groupby
    })


@app.route('/api/health')
def health():
    return {'status': 'ok'}


@app.route('/api/seed', methods=['POST'])
def seed_data():
    from seed_data import seed_database
    return jsonify(seed_database(db, Engagement, Pipeline, Metric, CommunityMetric))


# Initialize DB
def init_db():
    try:
        if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
            try:
                Engagement.query.first()
                Pipeline.query.first()
                Metric.query.first()
                CommunityMetric.query.first()
            except Exception as e:
                print(f"⚠️  Schema mismatch: {e}")
                print("🔄 Recreating database...")
                db.drop_all()
                db.create_all()
                print("✅ Database recreated")
        else:
            db.create_all()
        db.create_all()
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ DB error: {e}")
        try:
            db.session.rollback()
            db.drop_all()
            db.create_all()
            print("🔄 Fresh database created")
        except Exception as e2:
            print(f"❌ Recovery failed: {e2}")


with app.app_context():
    init_db()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
