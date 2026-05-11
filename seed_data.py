"""Seed database with Excel data + create team members"""
import json
import os
import re


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
            return f"{year}-{num:02d}-15"
    return None


def seed_database(db, Engagement, Pipeline, Metric, User):
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
        community = extract_community(link) or extract_community(original_link)
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
    
    # Metrics with sort_order (All Time first, then Previous, April, May)
    metrics_data = [
        # Reddit
        {'platform': 'Reddit', 'period_type': 'Total', 'period_label': 'All Time', 'total_views': '181k', 'total_karma': 167, 'total_contributions': 266, 'sort_order': 0},
        {'platform': 'Reddit', 'period_type': 'Monthly', 'period_label': 'Previous Months', 'total_views': '176k', 'total_karma': 166, 'total_contributions': 244, 'sort_order': 1},
        {'platform': 'Reddit', 'period_type': 'Monthly', 'period_label': 'April 2026', 'total_views': '5k', 'total_karma': 1, 'total_contributions': 22, 'sort_order': 2},
        {'platform': 'Reddit', 'period_type': 'Monthly', 'period_label': 'May 2026', 'total_views': '0', 'total_karma': 0, 'total_contributions': 0, 'sort_order': 3},
        # Quora
        {'platform': 'Quora', 'period_type': 'Total', 'period_label': 'All Time', 'total_views': '125', 'total_karma': 0, 'total_contributions': 10, 'sort_order': 0},
        {'platform': 'Quora', 'period_type': 'Monthly', 'period_label': 'Previous Months', 'total_views': '125', 'total_karma': 0, 'total_contributions': 10, 'sort_order': 1},
        {'platform': 'Quora', 'period_type': 'Monthly', 'period_label': 'April 2026', 'total_views': '0', 'total_karma': 0, 'total_contributions': 0, 'sort_order': 2},
        {'platform': 'Quora', 'period_type': 'Monthly', 'period_label': 'May 2026', 'total_views': '0', 'total_karma': 0, 'total_contributions': 0, 'sort_order': 3},
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
