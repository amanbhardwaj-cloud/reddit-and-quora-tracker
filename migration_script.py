import json
import os
import re
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

# Setup firebase credentials
cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json")
if not os.path.exists(cred_path):
    raise FileNotFoundError(
        f"Firebase Service Account Key not found at: {cred_path}. Please place your JSON key file here."
    )

cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)
db = firestore.client()


def parse_views(s):
    if not s:
        return 0
    s = str(s).strip().lower().replace(',', '')
    try:
        if 'k' in s:
            return int(float(s.replace('k', '')) * 1000)
        if 'm' in s:
            return int(float(s.replace('m', '')) * 1000000)
        return int(float(s))
    except:
        return 0


def extract_community(link):
    if not link:
        return ''
    reddit_match = re.search(r'reddit\.com/r/([^/]+)', link)
    if reddit_match:
        return 'r/' + reddit_match.group(1)
    if 'quora.com' in link:
        return 'Quora'
    return ''


def month_to_date(month_str):
    if not month_str:
        return None
    month_str = str(month_str).strip()
    month_map = {
        'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
        'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
        'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
        'august': 8, 'aug': 8, 'september': 9, 'sep': 9,
        'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
        'december': 12, 'dec': 12
    }
    lower = month_str.lower()
    for name, num in month_map.items():
        if name in lower:
            year = 2026
            year_match = re.search(r'20\d{2}', month_str)
            if year_match:
                year = int(year_match.group())
            return datetime(year, num, 15)  # Seed mid-month
    return datetime.utcnow()


def migrate_data():
    print("🚀 Beginning Migration to Firestore...")
    
    # Load raw JSON data provided
    data_file = "data.json"
    if not os.path.exists(data_file):
        print(f"❌ Error: Raw data JSON file not found at {data_file}")
        return

    with open(data_file, "r") as f:
        raw_data = json.load(f)

    # 1. Migrate Engagements
    print("📦 Migrating Engagements (Reddit + Quora)...")
    engagement_ref = db.collection("engagements")
    community_counts = {}

    all_raw_engagements = raw_data.get("reddit", []) + raw_data.get("quora", [])
    
    for idx, item in enumerate(all_raw_engagements):
        link = item.get('engagement_link', '')
        original_link = item.get('original_question_link', '')
        community = extract_community(link) or extract_community(original_link)
        post_date_dt = month_to_date(item.get('month', ''))
        
        # Structure payload to match model schema
        payload = {
            'platform': item.get('platform', 'Reddit'),
            'owner': item.get('owner', ''),
            'post_date': post_date_dt.strftime('%Y-%m-%d') if post_date_dt else datetime.utcnow().strftime('%Y-%m-%d'),
            'community': community,
            'title': item.get('title', '')[:500],
            'engagement_link': link[:1000],
            'original_question_link': original_link[:1000],
            'product_target': item.get('product_target', 'Generic'),
            'account_details': item.get('account_details', ''),
            'views': 0,
            'upvotes': 0,
            'comments': 0,
            'status': 'Live',
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        # Add to Firestore (Letting Firestore generate unique IDs)
        engagement_ref.add(payload)
        
        if payload['platform'] == 'Reddit' and community and community.startswith('r/'):
            community_counts[community] = community_counts.get(community, 0) + 1

    print(f"✅ Created {len(all_raw_engagements)} Engagement documents.")

    # 2. Migrate Pipeline Items
    print("📦 Migrating Pipeline...")
    pipeline_ref = db.collection("pipeline")
    raw_pipelines = raw_data.get("pipeline", [])
    
    for item in raw_pipelines:
        payload = {
            'content': item.get('content', ''),
            'platform': item.get('platform', ''),
            'status': item.get('status', 'Not Picked'),
            'assigned_to': item.get('assigned_to', ''),
            'notes': item.get('notes', ''),
            'item_type': 'Pipeline',
            'community': item.get('community', ''),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        pipeline_ref.add(payload)
    print(f"✅ Created {len(raw_pipelines)} Pipeline items.")

    # 3. Migrate Drafts
    print("📦 Migrating Drafts...")
    raw_drafts = raw_data.get("drafts", [])
    for item in raw_drafts:
        payload = {
            'content': item.get('content', ''),
            'platform': 'Reddit',
            'status': 'Draft',
            'assigned_to': '',
            'notes': '',
            'item_type': 'Draft',
            'community': '',
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        pipeline_ref.add(payload)
    print(f"✅ Created {len(raw_drafts)} Draft items.")

    # 4. Migrate Metrics
    print("📦 Migrating Default Platform Metrics...")
    metrics_ref = db.collection("metrics")
    metrics_data = [
        {'platform': 'Reddit', 'period_type': 'Monthly', 'period_label': 'Previous Months', 'total_views': '176k', 'total_karma': 166, 'total_contributions': 244, 'updated_at': datetime.utcnow()},
        {'platform': 'Reddit', 'period_type': 'Monthly', 'period_label': 'April 2026', 'total_views': '5k', 'total_karma': 1, 'total_contributions': 22, 'updated_at': datetime.utcnow()},
        {'platform': 'Reddit', 'period_type': 'Monthly', 'period_label': 'May 2026', 'total_views': '0', 'total_karma': 0, 'total_contributions': 0, 'updated_at': datetime.utcnow()},
        {'platform': 'Reddit', 'period_type': 'Total', 'period_label': 'All Time', 'total_views': '181k', 'total_karma': 167, 'total_contributions': 266, 'updated_at': datetime.utcnow()},
        {'platform': 'Quora', 'period_type': 'Monthly', 'period_label': 'Previous Months', 'total_views': '125', 'total_karma': 0, 'total_contributions': 10, 'updated_at': datetime.utcnow()},
        {'platform': 'Quora', 'period_type': 'Monthly', 'period_label': 'April 2026', 'total_views': '0', 'total_karma': 0, 'total_contributions': 0, 'updated_at': datetime.utcnow()},
        {'platform': 'Quora', 'period_type': 'Monthly', 'period_label': 'May 2026', 'total_views': '0', 'total_karma': 0, 'total_contributions': 0, 'updated_at': datetime.utcnow()},
        {'platform': 'Quora', 'period_type': 'Total', 'period_label': 'All Time', 'total_views': '125', 'total_karma': 0, 'total_contributions': 10, 'updated_at': datetime.utcnow()},
    ]
    for metric in metrics_data:
        metrics_ref.add(metric)
    print("✅ Created default metrics references.")

    # 5. Migrate Community Metrics
    print("📦 Migrating Community Metrics...")
    community_ref = db.collection("community_metrics")
    top_communities = sorted(community_counts.items(), key=lambda x: -x[1])[:10]
    
    for community, count in top_communities:
        payload = {
            'community': community,
            'period_label': 'All Time',
            'posts_count': count,
            'views': 0,
            'upvotes': 0,
            'comments': 0,
            'updated_at': datetime.utcnow()
        }
        community_ref.add(payload)
    print(f"✅ Created {len(top_communities)} top Community tracking metric references.")
    print("🎉 Database Migration Finished Successfully!")


if __name__ == "__main__":
    migrate_data()