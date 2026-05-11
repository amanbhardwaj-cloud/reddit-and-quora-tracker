"""Seed database with Excel data"""
import json
import os
import re
from datetime import datetime


def extract_community(link):
    """Extract subreddit/community from Reddit/Quora URL"""
    if not link:
        return ''
    # Reddit pattern: /r/something/
    reddit_match = re.search(r'reddit\.com/r/([^/]+)', link)
    if reddit_match:
        return 'r/' + reddit_match.group(1)
    # Quora pattern
    if 'quora.com' in link:
        return 'Quora'
    return ''


def month_to_date(month_str):
    """Convert month string to a date estimate"""
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
    
    # Try to find first month mentioned
    lower = month_str.lower()
    for name, num in month_map.items():
        if name in lower:
            # Default to 2026 if no year context
            year = 2026
            year_match = re.search(r'20\d{2}', month_str)
            if year_match:
                year = int(year_match.group())
            # Use 15th as default day
            return f"{year}-{num:02d}-15"
    return None


def seed_database(db, Engagement, Pipeline, Metric):
    if Engagement.query.count() > 0:
        return {'message': 'Database already seeded', 'engagement_count': Engagement.query.count()}
    
    basedir = os.path.abspath(os.path.dirname(__file__))
    json_path = os.path.join(basedir, 'data.json')
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    count = 0
    for item in data['reddit'] + data['quora']:
        link = item.get('engagement_link', '')
        original_link = item.get('original_question_link', '')
        
        # Try community from engagement_link first, then original
        community = extract_community(link) or extract_community(original_link)
        
        # Convert month to date
        post_date = month_to_date(item.get('month', ''))
        
        engagement = Engagement(
            platform=item.get('platform', 'Reddit'),
            owner=item.get('owner', ''),
            post_date=post_date,
            community=community,
            title=item.get('title', '')[:500],
            engagement_link=link[:1000],
            original_question_link=original_link[:1000],
            product_target=item.get('product_target', 'Generic'),
            account_details=item.get('account_details', ''),
            status='Live'
        )
        db.session.add(engagement)
        count += 1
    
    pipeline_count = 0
    for item in data['pipeline']:
        pipeline = Pipeline(
            content=item.get('content', ''),
            platform=item.get('platform', ''),
            status=item.get('status', 'Not Picked'),
            item_type='Pipeline'
        )
        db.session.add(pipeline)
        pipeline_count += 1
    
    draft_count = 0
    for item in data['drafts']:
        draft = Pipeline(
            content=item.get('content', ''),
            platform='Reddit',
            status='Draft',
            item_type='Draft'
        )
        db.session.add(draft)
        draft_count += 1
    
    # Metrics with proper monthly breakdown
    # Reddit: All Time (181k, 167, 266) = April (5k, 1, 22) + earlier months
    # So existing earlier months total: 181k - 5k = 176k, 167-1=166, 266-22=244
    metrics_data = [
        # Reddit Monthly metrics (these will SUM to All Time)
        {'platform': 'Reddit', 'period_type': 'Monthly', 'period_label': 'Previous Months', 'total_views': '176k', 'total_karma': 166, 'total_contributions': 244},
        {'platform': 'Reddit', 'period_type': 'Monthly', 'period_label': 'April 2026', 'total_views': '5k', 'total_karma': 1, 'total_contributions': 22},
        {'platform': 'Reddit', 'period_type': 'Monthly', 'period_label': 'May 2026', 'total_views': '0', 'total_karma': 0, 'total_contributions': 0},
        # Reddit All Time - will be auto-calculated
        {'platform': 'Reddit', 'period_type': 'Total', 'period_label': 'All Time', 'total_views': '181k', 'total_karma': 167, 'total_contributions': 266},
        
        # Quora Monthly metrics (these will SUM to All Time)
        {'platform': 'Quora', 'period_type': 'Monthly', 'period_label': 'Previous Months', 'total_views': '125', 'total_karma': 0, 'total_contributions': 10},
        {'platform': 'Quora', 'period_type': 'Monthly', 'period_label': 'April 2026', 'total_views': '0', 'total_karma': 0, 'total_contributions': 0},
        {'platform': 'Quora', 'period_type': 'Monthly', 'period_label': 'May 2026', 'total_views': '0', 'total_karma': 0, 'total_contributions': 0},
        # Quora All Time - will be auto-calculated
        {'platform': 'Quora', 'period_type': 'Total', 'period_label': 'All Time', 'total_views': '125', 'total_karma': 0, 'total_contributions': 10},
    ]
    
    metric_count = 0
    for m in metrics_data:
        metric = Metric(**m)
        db.session.add(metric)
        metric_count += 1
    
    db.session.commit()
    
    return {
        'message': 'Database seeded successfully',
        'engagements': count,
        'pipeline': pipeline_count,
        'drafts': draft_count,
        'metrics': metric_count
    }
