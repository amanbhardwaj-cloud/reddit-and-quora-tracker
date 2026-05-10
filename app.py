from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Database setup - SQLite (no need for PostgreSQL on free tier!)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'dashboard.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Fix for Render PostgreSQL URL
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

db = SQLAlchemy(app)


# ============ DATABASE MODELS ============

class Engagement(db.Model):
    """Reddit & Quora engagement posts"""
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), nullable=False)  # Reddit/Quora
    owner = db.Column(db.String(100))
    month = db.Column(db.String(50))
    title = db.Column(db.String(500))
    engagement_link = db.Column(db.String(1000))
    original_question_link = db.Column(db.String(1000))
    product_target = db.Column(db.String(100))
    account_details = db.Column(db.Text)
    
    # Manual metrics (you'll fill these)
    views = db.Column(db.Integer, default=0)
    upvotes = db.Column(db.Integer, default=0)
    comments = db.Column(db.Integer, default=0)
    
    # Status tracking
    status = db.Column(db.String(50), default='Live')  # Live, Draft, Completed
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'platform': self.platform,
            'owner': self.owner,
            'month': self.month,
            'title': self.title,
            'engagement_link': self.engagement_link,
            'original_question_link': self.original_question_link,
            'product_target': self.product_target,
            'account_details': self.account_details,
            'views': self.views or 0,
            'upvotes': self.upvotes or 0,
            'comments': self.comments or 0,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Pipeline(db.Model):
    """Pipeline of content ideas"""
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    platform = db.Column(db.String(50))
    status = db.Column(db.String(50), default='Not Picked')  # Not Picked, Picked, In Progress, Live
    assigned_to = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'platform': self.platform,
            'status': self.status,
            'assigned_to': self.assigned_to,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Draft(db.Model):
    """Draft content"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500))
    content = db.Column(db.Text)
    platform = db.Column(db.String(50))
    subreddit = db.Column(db.String(100))
    draft_type = db.Column(db.String(100))
    status = db.Column(db.String(50), default='Draft')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'platform': self.platform,
            'subreddit': self.subreddit,
            'draft_type': self.draft_type,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Account(db.Model):
    """Accounts used for posting"""
    id = db.Column(db.Integer, primary_key=True)
    account_details = db.Column(db.Text)
    owner = db.Column(db.String(100))
    platform = db.Column(db.String(50))
    
    def to_dict(self):
        return {
            'id': self.id,
            'account_details': self.account_details,
            'owner': self.owner,
            'platform': self.platform
        }


# ============ ROUTES ============

@app.route('/')
def index():
    return render_template('index.html')


# ===== ENGAGEMENTS =====
@app.route('/api/engagements', methods=['GET'])
def get_engagements():
    engagements = Engagement.query.order_by(Engagement.created_at.desc()).all()
    return jsonify([e.to_dict() for e in engagements])


@app.route('/api/engagements', methods=['POST'])
def create_engagement():
    data = request.json
    engagement = Engagement(
        platform=data.get('platform'),
        owner=data.get('owner'),
        month=data.get('month'),
        title=data.get('title'),
        engagement_link=data.get('engagement_link'),
        original_question_link=data.get('original_question_link'),
        product_target=data.get('product_target'),
        account_details=data.get('account_details'),
        views=data.get('views', 0),
        upvotes=data.get('upvotes', 0),
        comments=data.get('comments', 0),
        status=data.get('status', 'Live')
    )
    db.session.add(engagement)
    db.session.commit()
    return jsonify(engagement.to_dict()), 201


@app.route('/api/engagements/<int:id>', methods=['PUT'])
def update_engagement(id):
    engagement = Engagement.query.get_or_404(id)
    data = request.json
    for key, value in data.items():
        if hasattr(engagement, key):
            setattr(engagement, key, value)
    db.session.commit()
    return jsonify(engagement.to_dict())


@app.route('/api/engagements/<int:id>', methods=['DELETE'])
def delete_engagement(id):
    engagement = Engagement.query.get_or_404(id)
    db.session.delete(engagement)
    db.session.commit()
    return jsonify({'success': True})


# ===== PIPELINE =====
@app.route('/api/pipeline', methods=['GET'])
def get_pipeline():
    items = Pipeline.query.order_by(Pipeline.created_at.desc()).all()
    return jsonify([p.to_dict() for p in items])


@app.route('/api/pipeline', methods=['POST'])
def create_pipeline():
    data = request.json
    item = Pipeline(
        content=data.get('content'),
        platform=data.get('platform'),
        status=data.get('status', 'Not Picked'),
        assigned_to=data.get('assigned_to'),
        notes=data.get('notes')
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@app.route('/api/pipeline/<int:id>', methods=['PUT'])
def update_pipeline(id):
    item = Pipeline.query.get_or_404(id)
    data = request.json
    for key, value in data.items():
        if hasattr(item, key):
            setattr(item, key, value)
    db.session.commit()
    return jsonify(item.to_dict())


@app.route('/api/pipeline/<int:id>', methods=['DELETE'])
def delete_pipeline(id):
    item = Pipeline.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'success': True})


# ===== DRAFTS =====
@app.route('/api/drafts', methods=['GET'])
def get_drafts():
    drafts = Draft.query.order_by(Draft.created_at.desc()).all()
    return jsonify([d.to_dict() for d in drafts])


@app.route('/api/drafts', methods=['POST'])
def create_draft():
    data = request.json
    draft = Draft(
        title=data.get('title'),
        content=data.get('content'),
        platform=data.get('platform'),
        subreddit=data.get('subreddit'),
        draft_type=data.get('draft_type'),
        status=data.get('status', 'Draft')
    )
    db.session.add(draft)
    db.session.commit()
    return jsonify(draft.to_dict()), 201


@app.route('/api/drafts/<int:id>', methods=['PUT'])
def update_draft(id):
    draft = Draft.query.get_or_404(id)
    data = request.json
    for key, value in data.items():
        if hasattr(draft, key):
            setattr(draft, key, value)
    db.session.commit()
    return jsonify(draft.to_dict())


@app.route('/api/drafts/<int:id>', methods=['DELETE'])
def delete_draft(id):
    draft = Draft.query.get_or_404(id)
    db.session.delete(draft)
    db.session.commit()
    return jsonify({'success': True})


# ===== STATS =====
@app.route('/api/stats', methods=['GET'])
def get_stats():
    total = Engagement.query.count()
    reddit_count = Engagement.query.filter_by(platform='Reddit').count()
    quora_count = Engagement.query.filter_by(platform='Quora').count()
    
    live_count = Engagement.query.filter_by(status='Live').count()
    draft_count = Engagement.query.filter_by(status='Draft').count()
    
    pipeline_total = Pipeline.query.count()
    pipeline_picked = Pipeline.query.filter(Pipeline.status != 'Not Picked').count()
    pipeline_not_picked = Pipeline.query.filter_by(status='Not Picked').count()
    
    drafts_count = Draft.query.count()
    
    # Calculate engagement metrics
    all_engagements = Engagement.query.all()
    total_views = sum(e.views or 0 for e in all_engagements)
    total_upvotes = sum(e.upvotes or 0 for e in all_engagements)
    total_comments = sum(e.comments or 0 for e in all_engagements)
    
    # Weekly stats (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    weekly_engagements = Engagement.query.filter(Engagement.created_at >= week_ago).count()
    
    # Monthly stats (last 30 days)
    month_ago = datetime.utcnow() - timedelta(days=30)
    monthly_engagements = Engagement.query.filter(Engagement.created_at >= month_ago).count()
    
    # By owner
    owners_data = {}
    for e in all_engagements:
        if e.owner:
            if e.owner not in owners_data:
                owners_data[e.owner] = {'count': 0, 'views': 0, 'upvotes': 0, 'comments': 0}
            owners_data[e.owner]['count'] += 1
            owners_data[e.owner]['views'] += e.views or 0
            owners_data[e.owner]['upvotes'] += e.upvotes or 0
            owners_data[e.owner]['comments'] += e.comments or 0
    
    # By product
    products_data = {}
    for e in all_engagements:
        if e.product_target:
            product = e.product_target.strip()
            products_data[product] = products_data.get(product, 0) + 1
    
    return jsonify({
        'total': total,
        'reddit_count': reddit_count,
        'quora_count': quora_count,
        'live_count': live_count,
        'draft_count': draft_count,
        'pipeline_total': pipeline_total,
        'pipeline_picked': pipeline_picked,
        'pipeline_not_picked': pipeline_not_picked,
        'drafts_count': drafts_count,
        'total_views': total_views,
        'total_upvotes': total_upvotes,
        'total_comments': total_comments,
        'weekly_engagements': weekly_engagements,
        'monthly_engagements': monthly_engagements,
        'owners_data': owners_data,
        'products_data': products_data
    })


@app.route('/api/health')
def health():
    return {'status': 'ok'}


# ===== SEED DATABASE =====
@app.route('/api/seed', methods=['POST'])
def seed_data():
    """Initialize database with your Excel data"""
    from seed_data import seed_database
    result = seed_database(db, Engagement, Pipeline, Draft, Account)
    return jsonify(result)


# Initialize database
with app.app_context():
    db.create_all()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
