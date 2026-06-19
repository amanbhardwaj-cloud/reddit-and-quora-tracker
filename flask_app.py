from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import os
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# Initialize Firebase Admin using credentials
# If deployed on Render, credentials will be parsed from a file or local configuration environment variables
try:
    if not firebase_admin._apps:
        # Check environment variable first
        cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            # Fallback configuration for Render secret files/literal credentials injection
            firebase_admin.initialize_app()
    db = firestore.client()
    print("✅ Firestore Client Initialized Successfully")
except Exception as e:
    print(f"❌ Error initializing Firebase: {e}")
    # Initialize mock app context setup to prevent application crashing if firestore isn't configured yet
    db = None


# ============ STRUCTURAL SCHEMAS & HELPERS ============

def doc_to_dict(doc):
    """Converts a Firestore document snapshot to a Python dictionary mapping the original ID."""
    data = doc.to_dict()
    data['id'] = doc.id
    
    # Handle ISO string formatting on timestamps inside Firestore
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    return data


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
    """Calculates all time data from monthly entries and synchronizes base collections."""
    if not db: return
    try:
        metrics_ref = db.collection('metrics')
        monthly_docs = metrics_ref.filter('platform', '==', platform).filter('period_type', '==', 'Monthly').stream()
        
        total_v = 0
        total_k = 0
        total_c = 0
        
        for doc in monthly_docs:
            data = doc.to_dict()
            total_v += parse_views(data.get('total_views', '0'))
            total_k += int(data.get('total_karma', 0) or 0)
            total_c += int(data.get('total_contributions', 0) or 0)
            
        # Find and update 'Total' / 'All Time' metric record
        all_time_docs = metrics_ref.filter('platform', '==', platform).filter('period_type', '==', 'Total').limit(1).stream()
        all_time_list = list(all_time_docs)
        
        if all_time_list:
            all_time_list[0].reference.update({
                'total_views': format_views(total_v),
                'total_karma': total_k,
                'total_contributions': total_c,
                'updated_at': datetime.utcnow()
            })
    except Exception as e:
        print(f"⚠️ Recalculate metrics synchronization error: {e}")


def auto_sync_monthly_metrics():
    """Auto-update monthly metrics directly inside Firestore collections."""
    if not db: return
    try:
        eng_docs = db.collection('engagements').stream()
        monthly_counts = {}
        
        for doc in eng_docs:
            e = doc.to_dict()
            post_date = e.get('post_date')
            if not post_date: continue
            try:
                dt = datetime.strptime(post_date, '%Y-%m-%d')
                period_label = dt.strftime('%B %Y')
            except:
                continue
                
            key = (e.get('platform', 'Reddit'), period_label)
            if key not in monthly_counts:
                monthly_counts[key] = {'count': 0, 'views': 0, 'upvotes': 0, 'comments': 0}
            monthly_counts[key]['count'] += 1
            monthly_counts[key]['views'] += int(e.get('views', 0) or 0)
            monthly_counts[key]['upvotes'] += int(e.get('upvotes', 0) or 0)
            monthly_counts[key]['comments'] += int(e.get('comments', 0) or 0)
            
        for (platform, period_label), counts in monthly_counts.items():
            metrics_ref = db.collection('metrics')
            match_docs = metrics_ref.filter('platform', '==', platform).filter('period_label', '==', period_label).filter('period_type', '==', 'Monthly').limit(1).stream()
            matched_list = list(match_docs)
            
            payload = {
                'platform': platform,
                'period_label': period_label,
                'period_type': 'Monthly',
                'total_views': format_views(counts['views']),
                'total_karma': counts['upvotes'],
                'total_contributions': counts['count'],
                'updated_at': datetime.utcnow()
            }
            
            if matched_list:
                matched_list[0].reference.update(payload)
            else:
                metrics_ref.add(payload)
                
        recalculate_all_time('Reddit')
        recalculate_all_time('Quora')
        auto_sync_community_counts()
    except Exception as e:
        print(f"⚠️ Auto sync metrics failed: {e}")


def auto_sync_community_counts():
    if not db: return
    try:
        engs = db.collection('engagements').filter('platform', '==', 'Reddit').stream()
        community_counts = {}
        
        for doc in engs:
            e = doc.to_dict()
            comm = e.get('community')
            if comm and comm.startswith('r/'):
                community_counts[comm] = community_counts.get(comm, 0) + 1
                
        # Synchronize community counts inside the community_metrics tracking table
        comm_ref = db.collection('community_metrics')
        for community, count in community_counts.items():
            match_docs = comm_ref.filter('community', '==', community).filter('period_label', '==', 'All Time').limit(1).stream()
            matched_list = list(match_docs)
            
            payload = {
                'community': community,
                'period_label': 'All Time',
                'posts_count': count,
                'updated_at': datetime.utcnow()
            }
            if matched_list:
                matched_list[0].reference.update(payload)
            else:
                payload.update({'views': 0, 'upvotes': 0, 'comments': 0})
                comm_ref.add(payload)
                
        # Reset outdated metrics to 0 post count
        existing = comm_ref.filter('period_label', '==', 'All Time').stream()
        for doc in existing:
            data = doc.to_dict()
            name = data.get('community')
            if name not in community_counts:
                doc.reference.update({'posts_count': 0, 'updated_at': datetime.utcnow()})
    except Exception as e:
        print(f"⚠️ Auto sync community counts failed: {e}")


# ============ API ROUTES ============

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/team', methods=['GET'])
def get_team():
    return jsonify([
        {'name': 'Aman', 'avatar_color': '#8b5cf6'},
        {'name': 'Astha', 'avatar_color': '#3b82f6'},
        {'name': 'Komal', 'avatar_color': '#10b981'},
    ])


# ENGAGEMENTS API
@app.route('/api/engagements', methods=['GET'])
def get_engagements():
    if not db: return jsonify([])
    platform = request.args.get('platform')
    
    query = db.collection('engagements')
    if platform:
        docs = query.filter('platform', '==', platform).stream()
    else:
        docs = query.stream()
        
    engagements = [doc_to_dict(d) for d in docs]
    
    def sort_key(e):
        post_date = e.get('post_date')
        if post_date:
            try: return datetime.strptime(post_date, '%Y-%m-%d')
            except: pass
        created_at_str = e.get('created_at')
        if created_at_str:
            try: return datetime.fromisoformat(created_at_str)
            except: pass
        return datetime.min

    engagements.sort(key=sort_key, reverse=True)
    return jsonify(engagements)


@app.route('/api/engagements', methods=['POST'])
def create_engagement():
    if not db: return jsonify({"error": "No Database Connection"}), 500
    data = request.json
    payload = {
        'platform': data.get('platform'),
        'owner': data.get('owner', ''),
        'post_date': data.get('post_date', ''),
        'community': data.get('community', ''),
        'title': data.get('title', '')[:500],
        'engagement_link': data.get('engagement_link', '')[:1000],
        'original_question_link': data.get('original_question_link', '')[:1000],
        'product_target': data.get('product_target', 'Generic'),
        'account_details': data.get('account_details', ''),
        'views': int(data.get('views', 0) or 0),
        'upvotes': int(data.get('upvotes', 0) or 0),
        'comments': int(data.get('comments', 0) or 0),
        'status': data.get('status', 'Live'),
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }
    
    ref_ref = db.collection('engagements').document()
    ref_ref.set(payload)
    
    auto_sync_monthly_metrics()
    
    saved_doc = ref_ref.get()
    return jsonify(doc_to_dict(saved_doc)), 201


@app.route('/api/engagements/<id>', methods=['PUT'])
def update_engagement(id):
    if not db: return jsonify({"error": "No DB Link"}), 500
    data = request.json
    doc_ref = db.collection('engagements').document(id)
    if not doc_ref.get().exists:
        return jsonify({"error": "Engagement not found"}), 404
        
    payload = {}
    valid_fields = [
        'platform', 'owner', 'post_date', 'community', 'title', 
        'engagement_link', 'original_question_link', 'product_target', 
        'account_details', 'views', 'upvotes', 'comments', 'status'
    ]
    for key in valid_fields:
        if key in data:
            if key in ['views', 'upvotes', 'comments']:
                payload[key] = int(data[key] or 0)
            else:
                payload[key] = data[key]
                
    payload['updated_at'] = datetime.utcnow()
    doc_ref.update(payload)
    auto_sync_monthly_metrics()
    
    return jsonify(doc_to_dict(doc_ref.get()))


@app.route('/api/engagements/<id>', methods=['DELETE'])
def delete_engagement(id):
    if not db: return jsonify({"error": "No DB"}), 500
    doc_ref = db.collection('engagements').document(id)
    if not doc_ref.get().exists:
        return jsonify({"error": "Document not found"}), 404
    doc_ref.delete()
    auto_sync_monthly_metrics()
    return jsonify({'success': True})


# PIPELINE API
@app.route('/api/pipeline', methods=['GET'])
def get_pipeline():
    if not db: return jsonify([])
    platform = request.args.get('platform')
    item_type = request.args.get('item_type')
    
    query = db.collection('pipeline')
    if platform:
        query = query.filter('platform', '==', platform)
    if item_type:
        query = query.filter('item_type', '==', item_type)
        
    docs = query.stream()
    pipelines = [doc_to_dict(d) for d in docs]
    
    # Sort descending by created_at field
    def get_created_at(p):
        created = p.get('created_at')
        if created:
            try: return datetime.fromisoformat(created)
            except: pass
        return datetime.min
        
    pipelines.sort(key=get_created_at, reverse=True)
    return jsonify(pipelines)


@app.route('/api/pipeline', methods=['POST'])
def create_pipeline():
    if not db: return jsonify({"error": "No database Connection"}), 500
    data = request.json
    payload = {
        'content': data.get('content', ''),
        'platform': data.get('platform', 'Reddit'),
        'status': data.get('status', 'Not Picked'),
        'assigned_to': data.get('assigned_to', ''),
        'notes': data.get('notes', ''),
        'item_type': data.get('item_type', 'Pipeline'),
        'community': data.get('community', ''),
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }
    
    doc_ref = db.collection('pipeline').document()
    doc_ref.set(payload)
    return jsonify(doc_to_dict(doc_ref.get())), 201


@app.route('/api/pipeline/<id>', methods=['PUT'])
def update_pipeline(id):
    if not db: return jsonify({"error": "No DB connection"}), 500
    data = request.json
    doc_ref = db.collection('pipeline').document(id)
    if not doc_ref.get().exists:
        return jsonify({"error": "Not Found"}), 404
        
    payload = {}
    valid_fields = ['content', 'platform', 'status', 'assigned_to', 'notes', 'item_type', 'community']
    for field in valid_fields:
        if field in data:
            payload[field] = data[field]
            
    payload['updated_at'] = datetime.utcnow()
    doc_ref.update(payload)
    return jsonify(doc_to_dict(doc_ref.get()))


@app.route('/api/pipeline/<id>', methods=['DELETE'])
def delete_pipeline(id):
    if not db: return jsonify({"error": "No database Reference"}), 500
    doc_ref = db.collection('pipeline').document(id)
    if not doc_ref.get().exists:
        return jsonify({"error": "Item not found"}), 404
    doc_ref.delete()
    return jsonify({'success': True})


@app.route('/api/pipeline/<id>/pick', methods=['POST'])
def pick_pipeline_item(id):
    if not db: return jsonify({"error": "No connection"}), 500
    p_doc = db.collection('pipeline').document(id).get()
    if not p_doc.exists:
        return jsonify({"error": "Pipeline item not found"}), 404
        
    p = p_doc.to_dict()
    data = request.json or {}
    post_date = data.get('post_date') or datetime.utcnow().strftime('%Y-%m-%d')
    
    eng_payload = {
        'platform': p.get('platform', 'Reddit'),
        'title': p.get('content', '')[:500] if p.get('content') else 'Untitled',
        'owner': p.get('assigned_to') or data.get('owner', ''),
        'community': p.get('community') or data.get('community', ''),
        'post_date': post_date,
        'engagement_link': data.get('engagement_link', ''),
        'original_question_link': '',
        'product_target': data.get('product_target', 'Generic'),
        'account_details': '',
        'views': 0,
        'upvotes': 0,
        'comments': 0,
        'status': 'Live',
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }
    
    # Write transactions: Save to Engagements, Delete Pipeline Document reference
    db.collection('engagements').add(eng_payload)
    db.collection('pipeline').document(id).delete()
    
    auto_sync_monthly_metrics()
    return jsonify({'success': True})


# PLATFORM METRICS API
@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    if not db: return jsonify([])
    platform = request.args.get('platform')
    
    query = db.collection('metrics')
    if platform:
        docs = query.filter('platform', '==', platform).stream()
    else:
        docs = query.stream()
    return jsonify([doc_to_dict(d) for d in docs])


@app.route('/api/metrics', methods=['POST'])
def create_metric():
    if not db: return jsonify({"error": "No Firestore DB Connection"}), 500
    data = request.json
    payload = {
        'platform': data.get('platform'),
        'period_type': data.get('period_type'),
        'period_label': data.get('period_label', ''),
        'total_views': data.get('total_views', '0'),
        'total_karma': int(data.get('total_karma', 0) or 0),
        'total_contributions': int(data.get('total_contributions', 0) or 0),
        'updated_at': datetime.utcnow()
    }
    
    doc_ref = db.collection('metrics').document()
    doc_ref.set(payload)
    if payload['period_type'] == 'Monthly':
        recalculate_all_time(payload['platform'])
    return jsonify(doc_to_dict(doc_ref.get())), 201


@app.route('/api/metrics/<id>', methods=['PUT'])
def update_metric(id):
    if not db: return jsonify({"error": "No database"}), 500
    data = request.json
    doc_ref = db.collection('metrics').document(id)
    if not doc_ref.get().exists:
        return jsonify({"error": "Metric not found"}), 404
        
    payload = {}
    fields = ['platform', 'period_type', 'period_label', 'total_views', 'total_karma', 'total_contributions']
    for f in fields:
        if f in data:
            if f in ['total_karma', 'total_contributions']:
                payload[f] = int(data[f] or 0)
            else:
                payload[f] = data[f]
    payload['updated_at'] = datetime.utcnow()
    
    doc_ref.update(payload)
    current_data = doc_ref.get().to_dict()
    if current_data.get('period_type') == 'Monthly':
        recalculate_all_time(current_data.get('platform'))
        
    return jsonify(doc_to_dict(doc_ref.get()))


@app.route('/api/metrics/<id>', methods=['DELETE'])
def delete_metric(id):
    if not db: return jsonify({"error": "No DB connection"}), 500
    doc_ref = db.collection('metrics').document(id)
    if not doc_ref.get().exists:
        return jsonify({"error": "Metric not found"}), 404
        
    data = doc_ref.get().to_dict()
    pt = data.get('period_type')
    pf = data.get('platform')
    doc_ref.delete()
    
    if pt == 'Monthly':
        recalculate_all_time(pf)
    return jsonify({'success': True})


# COMMUNITY METRICS API
@app.route('/api/community-metrics', methods=['GET'])
def get_community_metrics():
    if not db: return jsonify([])
    docs = db.collection('community_metrics').stream()
    return jsonify([doc_to_dict(d) for d in docs])


@app.route('/api/community-metrics', methods=['POST'])
def create_community_metric():
    if not db: return jsonify({"error": "No DB"}), 500
    data = request.json
    payload = {
        'community': data.get('community'),
        'period_label': data.get('period_label', 'All Time'),
        'views': int(data.get('views', 0) or 0),
        'upvotes': int(data.get('upvotes', 0) or 0),
        'comments': int(data.get('comments', 0) or 0),
        'posts_count': int(data.get('posts_count', 0) or 0),
        'updated_at': datetime.utcnow()
    }
    
    doc_ref = db.collection('community_metrics').document()
    doc_ref.set(payload)
    return jsonify(doc_to_dict(doc_ref.get())), 201


@app.route('/api/community-metrics/<id>', methods=['PUT'])
def update_community_metric(id):
    if not db: return jsonify({"error": "No connection"}), 500
    data = request.json
    doc_ref = db.collection('community_metrics').document(id)
    if not doc_ref.get().exists:
        return jsonify({"error": "Not Found"}), 404
        
    payload = {}
    fields = ['community', 'period_label', 'views', 'upvotes', 'comments', 'posts_count']
    for f in fields:
        if f in data:
            if f in ['views', 'upvotes', 'comments', 'posts_count']:
                payload[f] = int(data[f] or 0)
            else:
                payload[f] = data[f]
    payload['updated_at'] = datetime.utcnow()
    doc_ref.update(payload)
    return jsonify(doc_to_dict(doc_ref.get()))


@app.route('/api/community-metrics/<id>', methods=['DELETE'])
def delete_community_metric(id):
    if not db: return jsonify({"error": "DB Link missing"}), 500
    doc_ref = db.collection('community_metrics').document(id)
    if not doc_ref.get().exists:
        return jsonify({"error": "Not Found"}), 404
    doc_ref.delete()
    return jsonify({'success': True})


# ANALYTICS & STATS HELPERS
def calculate_platform_stats(platform=None):
    if not db: return {}
    eng_query = db.collection('engagements')
    pipe_query = db.collection('pipeline')
    
    if platform:
        engagements = [d.to_dict() for d in eng_query.filter('platform', '==', platform).stream()]
        all_pipelines = [d.to_dict() for d in pipe_query.filter('platform', '==', platform).stream()]
    else:
        engagements = [d.to_dict() for d in eng_query.stream()]
        all_pipelines = [d.to_dict() for d in pipe_query.stream()]
        
    pipeline_items = [p for p in all_pipelines if p.get('item_type') == 'Pipeline']
    drafts = [p for p in all_pipelines if p.get('item_type') == 'Draft']
    
    return {
        'total': len(engagements),
        'live_count': sum(1 for e in engagements if e.get('status') == 'Live'),
        'pipeline_total': len(pipeline_items),
        'pipeline_picked': sum(1 for p in pipeline_items if p.get('status') != 'Not Picked'),
        'pipeline_not_picked': sum(1 for p in pipeline_items if p.get('status') == 'Not Picked'),
        'drafts_count': len(drafts),
    }


@app.route('/api/master-stats', methods=['GET'])
def get_master_stats():
    if not db: return jsonify({})
    
    engagements_docs = list(db.collection('engagements').stream())
    engs = [d.to_dict() for d in engagements_docs]
    
    pipelines_docs = list(db.collection('pipeline').stream())
    pipelines = [d.to_dict() for d in pipelines_docs]
    
    all_pipeline = [p for p in pipelines if p.get('item_type') == 'Pipeline']
    all_drafts = [p for p in pipelines if p.get('item_type') == 'Draft']
    
    combined = {
        'total': len(engs),
        'reddit_count': sum(1 for e in engs if e.get('platform') == 'Reddit'),
        'quora_count': sum(1 for e in engs if e.get('platform') == 'Quora'),
        'live_count': sum(1 for e in engs if e.get('status') == 'Live'),
        'pipeline_total': len(all_pipeline) + len(all_drafts),
        'pipeline_picked': sum(1 for p in all_pipeline if p.get('status') != 'Not Picked'),
        'pipeline_not_picked': sum(1 for p in all_pipeline if p.get('status') == 'Not Picked'),
        'drafts_count': len(all_drafts),
    }
    
    # Calculate Engagement scores and sort to fetch Top Posts (excluding structural items)
    score_list = []
    for doc in engagements_docs:
        e = doc.to_dict()
        upvotes = int(e.get('upvotes', 0) or 0)
        comments = int(e.get('comments', 0) or 0)
        views = int(e.get('views', 0) or 0)
        score = upvotes + comments + (views // 100)
        
        if upvotes + comments + views > 0:
            score_list.append({
                'id': doc.id,
                'title': e.get('title', 'Untitled'),
                'platform': e.get('platform', 'Reddit'),
                'owner': e.get('owner', ''),
                'views': views,
                'upvotes': upvotes,
                'comments': comments,
                'engagement_score': score,
                'engagement_link': e.get('engagement_link', '')
            })
            
    top_posts = sorted(score_list, key=lambda x: x['engagement_score'], reverse=True)[:5]
    
    return jsonify({
        'combined': combined,
        'reddit': calculate_platform_stats('Reddit'),
        'quora': calculate_platform_stats('Quora'),
        'top_posts': top_posts
    })


@app.route('/api/chart-data', methods=['GET'])
def chart_data():
    if not db: return jsonify({})
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
        else: # monthly
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
    
    # Retrieve all engagement data to bucket internally
    engagements_stream = db.collection('engagements').stream()
    for doc in engagements_stream:
        e = doc.to_dict()
        post_date = None
        p_date_str = e.get('post_date')
        if p_date_str:
            try: post_date = datetime.strptime(p_date_str, '%Y-%m-%d').date()
            except: pass
        if not post_date and e.get('created_at'):
            try:
                # Fallback to created timestamp if parsed successfully
                post_date = datetime.fromisoformat(e['created_at'].replace('Z', '+00:00')).date()
            except:
                pass
                
        if not post_date or post_date < start or post_date > end: continue
        
        if groupby == 'day': key = post_date.isoformat()
        elif groupby == 'week':
            days_from_start = (post_date - start).days
            bucket_start = start + timedelta(days=(days_from_start // 7) * 7)
            key = bucket_start.isoformat()
        else: key = post_date.replace(day=1).isoformat()
        
        if key in buckets:
            value = 1 if field is None else int(e.get(field, 0) or 0)
            platform = e.get('platform', 'Reddit')
            if platform in ['Reddit', 'Quora']:
                buckets[key][platform] = buckets[key].get(platform, 0) + value
                
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


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)