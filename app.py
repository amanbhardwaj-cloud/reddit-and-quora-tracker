from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import re

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'dashboard.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

db = SQLAlchemy(app)


class Engagement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), nullable=False)
    owner = db.Column(db.String(100))
    post_date = db.Column(db.String(50))  # NEW: date field replacing month
    community = db.Column(db.String(200))  # NEW: subreddit/topic community
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
    period_type = db.Column(db.String(50), nullable=False)  # Total or Monthly
    period_label = db.Column(db.String(100))  # e.g., "All Time", "April 2026"
    total_views = db.Column(db.String(50), default='0')
    total_karma = db.Column(db.Integer, default=0)
    total_contributions = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id, 'platform': self.platform, 'period_type': self.period_type,
            'period_label': self.period_label, 'total_views': self.total_views,
            'total_karma': self.total_karma or 0, 'total_contributions': self.total_contributions or 0,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


def parse_views(views_str):
    """Parse views like '181k', '5k', '125' into numbers"""
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
    """Format number back to readable format like '181k'"""
    if num >= 1000000:
        return f"{num/1000000:.1f}m".replace('.0m', 'm')
    if num >= 1000:
        return f"{num/1000:.1f}k".replace('.0k', 'k')
    return str(num)


def recalculate_all_time(platform):
    """Sum all monthly metrics and update All Time for a platform"""
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
    return all_time.to_dict() if all_time else None


@app.route('/')
def index():
    return render_template('index.html')


# ENGAGEMENTS
@app.route('/api/engagements', methods=['GET'])
def get_engagements():
    platform = request.args.get('platform')
    query = Engagement.query
    if platform:
        query = query.filter_by(platform=platform)
    # Sort newest to oldest by post_date (if present) else by created_at
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
def create_engagement():
    e = Engagement(**{k: v for k, v in request.json.items() if hasattr(Engagement, k)})
    db.session.add(e)
    db.session.commit()
    return jsonify(e.to_dict()), 201


@app.route('/api/engagements/<int:id>', methods=['PUT'])
def update_engagement(id):
    e = Engagement.query.get_or_404(id)
    for k, v in request.json.items():
        if hasattr(e, k): setattr(e, k, v)
    db.session.commit()
    return jsonify(e.to_dict())


@app.route('/api/engagements/<int:id>', methods=['DELETE'])
def delete_engagement(id):
    e = Engagement.query.get_or_404(id)
    db.session.delete(e)
    db.session.commit()
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
    # Auto-recalculate All Time when adding a monthly metric
    if m.period_type == 'Monthly':
        recalculate_all_time(m.platform)
    return jsonify(m.to_dict()), 201


@app.route('/api/metrics/<int:id>', methods=['PUT'])
def update_metric(id):
    m = Metric.query.get_or_404(id)
    for k, v in request.json.items():
        if hasattr(m, k): setattr(m, k, v)
    db.session.commit()
    
    # If a Monthly metric was updated, recalculate All Time
    if m.period_type == 'Monthly':
        recalculate_all_time(m.platform)
    
    return jsonify(m.to_dict())


@app.route('/api/metrics/<int:id>', methods=['DELETE'])
def delete_metric(id):
    m = Metric.query.get_or_404(id)
    platform = m.platform
    period_type = m.period_type
    db.session.delete(m)
    db.session.commit()
    if period_type == 'Monthly':
        recalculate_all_time(platform)
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
        'pending_count': sum(1 for e in engagements if e.status == 'Pending'),
        'pipeline_total': len(pipeline_items),
        'pipeline_picked': sum(1 for p in pipeline_items if p.status != 'Not Picked'),
        'pipeline_not_picked': sum(1 for p in pipeline_items if p.status == 'Not Picked'),
        'drafts_count': len(drafts),
    }


@app.route('/api/stats', methods=['GET'])
def get_stats():
    platform = request.args.get('platform')
    
    eng_query = Engagement.query
    pipe_query = Pipeline.query
    if platform:
        eng_query = eng_query.filter_by(platform=platform)
        pipe_query = pipe_query.filter_by(platform=platform)
    
    engagements = eng_query.all()
    pipeline_items = pipe_query.filter_by(item_type='Pipeline').all()
    drafts = pipe_query.filter_by(item_type='Draft').all()
    
    return jsonify({
        'total': len(engagements),
        'live_count': sum(1 for e in engagements if e.status == 'Live'),
        'pipeline_total': len(pipeline_items),
        'drafts_count': len(drafts),
    })


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
        'pipeline_total': len(all_pipeline),
        'pipeline_picked': sum(1 for p in all_pipeline if p.status != 'Not Picked'),
        'pipeline_not_picked': sum(1 for p in all_pipeline if p.status == 'Not Picked'),
        'drafts_count': len(all_drafts),
    }
    
    # Monthly data from engagements (based on post_date or created_at)
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
    
    # Weekly trend (last 8 weeks)
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
    
    # Top posts (when engagement metrics exist)
    top_posts = sorted(all_engagements, key=lambda e: (e.upvotes or 0) + (e.comments or 0) + (e.views or 0)//100, reverse=True)[:10]
    top_posts_data = [{
        'id': e.id,
        'title': e.title,
        'platform': e.platform,
        'owner': e.owner,
        'views': e.views or 0,
        'upvotes': e.upvotes or 0,
        'comments': e.comments or 0,
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
def seed_data():
    from seed_data import seed_database
    return jsonify(seed_database(db, Engagement, Pipeline, Metric))


@app.route('/api/recalculate-metrics', methods=['POST'])
def recalc_metrics():
    """Manual trigger to recalculate All Time metrics"""
    recalculate_all_time('Reddit')
    recalculate_all_time('Quora')
    return jsonify({'success': True})


with app.app_context():
    db.create_all()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
