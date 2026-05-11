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


class Engagement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), nullable=False)
    owner = db.Column(db.String(100))
    month = db.Column(db.String(50))
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
            'month': self.month, 'title': self.title,
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
    subreddit = db.Column(db.String(100))
    draft_type = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id, 'content': self.content, 'platform': self.platform,
            'status': self.status, 'assigned_to': self.assigned_to, 'notes': self.notes,
            'item_type': self.item_type, 'subreddit': self.subreddit, 'draft_type': self.draft_type,
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
            'total_karma': self.total_karma or 0, 'total_contributions': self.total_contributions or 0,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


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
    return jsonify([e.to_dict() for e in query.order_by(Engagement.created_at.desc()).all()])


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
    return jsonify(m.to_dict()), 201


@app.route('/api/metrics/<int:id>', methods=['PUT'])
def update_metric(id):
    m = Metric.query.get_or_404(id)
    for k, v in request.json.items():
        if hasattr(m, k): setattr(m, k, v)
    db.session.commit()
    return jsonify(m.to_dict())


@app.route('/api/metrics/<int:id>', methods=['DELETE'])
def delete_metric(id):
    m = Metric.query.get_or_404(id)
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
        'pending_count': sum(1 for e in engagements if e.status == 'Pending'),
        'pipeline_total': len(pipeline_items),
        'pipeline_picked': sum(1 for p in pipeline_items if p.status != 'Not Picked'),
        'pipeline_not_picked': sum(1 for p in pipeline_items if p.status == 'Not Picked'),
        'drafts_count': len(drafts),
        'total_views': sum(e.views or 0 for e in engagements),
        'total_upvotes': sum(e.upvotes or 0 for e in engagements),
        'total_comments': sum(e.comments or 0 for e in engagements),
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
    
    owners_data = {}
    for e in engagements:
        if e.owner:
            if e.owner not in owners_data:
                owners_data[e.owner] = {'count': 0, 'views': 0, 'upvotes': 0, 'comments': 0}
            owners_data[e.owner]['count'] += 1
            owners_data[e.owner]['views'] += e.views or 0
            owners_data[e.owner]['upvotes'] += e.upvotes or 0
            owners_data[e.owner]['comments'] += e.comments or 0
    
    products_data = {}
    for e in engagements:
        if e.product_target:
            p = e.product_target.strip()
            products_data[p] = products_data.get(p, 0) + 1
    
    status_data = {}
    for e in engagements:
        s = e.status or 'Unknown'
        status_data[s] = status_data.get(s, 0) + 1
    
    monthly_data = {}
    for e in engagements:
        m = e.month or 'Unknown'
        monthly_data[m] = monthly_data.get(m, 0) + 1
    
    return jsonify({
        'total': len(engagements),
        'live_count': sum(1 for e in engagements if e.status == 'Live'),
        'pending_count': sum(1 for e in engagements if e.status == 'Pending'),
        'pipeline_total': len(pipeline_items),
        'pipeline_picked': sum(1 for p in pipeline_items if p.status != 'Not Picked'),
        'pipeline_not_picked': sum(1 for p in pipeline_items if p.status == 'Not Picked'),
        'drafts_count': len(drafts),
        'total_views': sum(e.views or 0 for e in engagements),
        'total_upvotes': sum(e.upvotes or 0 for e in engagements),
        'total_comments': sum(e.comments or 0 for e in engagements),
        'owners_data': owners_data,
        'products_data': products_data,
        'status_data': status_data,
        'monthly_data': monthly_data
    })


@app.route('/api/master-stats', methods=['GET'])
def get_master_stats():
    """Combined stats for master dashboard"""
    all_engagements = Engagement.query.all()
    all_pipeline = Pipeline.query.filter_by(item_type='Pipeline').all()
    all_drafts = Pipeline.query.filter_by(item_type='Draft').all()
    
    # Combined totals
    combined = {
        'total': len(all_engagements),
        'reddit_count': sum(1 for e in all_engagements if e.platform == 'Reddit'),
        'quora_count': sum(1 for e in all_engagements if e.platform == 'Quora'),
        'live_count': sum(1 for e in all_engagements if e.status == 'Live'),
        'pending_count': sum(1 for e in all_engagements if e.status == 'Pending'),
        'pipeline_total': len(all_pipeline),
        'pipeline_picked': sum(1 for p in all_pipeline if p.status != 'Not Picked'),
        'pipeline_not_picked': sum(1 for p in all_pipeline if p.status == 'Not Picked'),
        'drafts_count': len(all_drafts),
        'total_views': sum(e.views or 0 for e in all_engagements),
        'total_upvotes': sum(e.upvotes or 0 for e in all_engagements),
        'total_comments': sum(e.comments or 0 for e in all_engagements),
    }
    
    # Monthly data - combined
    monthly_data = {}
    for e in all_engagements:
        m = e.month or 'Unknown'
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
    
    # Top engaging posts (by upvotes + comments + views)
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


with app.app_context():
    db.create_all()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
