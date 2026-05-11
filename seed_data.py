"""Seed database with Excel data"""
import json
import os

def seed_database(db, Engagement, Pipeline, Metric):
    if Engagement.query.count() > 0:
        return {'message': 'Database already seeded', 'engagement_count': Engagement.query.count()}
    
    basedir = os.path.abspath(os.path.dirname(__file__))
    json_path = os.path.join(basedir, 'data.json')
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    count = 0
    for item in data['reddit'] + data['quora']:
        engagement = Engagement(
            platform=item.get('platform', 'Reddit'),
            owner=item.get('owner', ''),
            month=item.get('month', ''),
            title=item.get('title', '')[:500],
            engagement_link=item.get('engagement_link', '')[:1000],
            original_question_link=item.get('original_question_link', '')[:1000],
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
    
    # Seed metrics from your tracker file
    metrics_data = [
        {'platform': 'Reddit', 'period_type': 'Total', 'period_label': 'All Time', 'total_views': '181k', 'total_karma': 167, 'total_contributions': 266},
        {'platform': 'Reddit', 'period_type': 'Monthly', 'period_label': 'April 2026', 'total_views': '5k', 'total_karma': 1, 'total_contributions': 22},
        {'platform': 'Reddit', 'period_type': 'Monthly', 'period_label': 'May 2026', 'total_views': '0', 'total_karma': 0, 'total_contributions': 0},
        {'platform': 'Quora', 'period_type': 'Total', 'period_label': 'All Time', 'total_views': '125', 'total_karma': 0, 'total_contributions': 10},
        {'platform': 'Quora', 'period_type': 'Monthly', 'period_label': 'April 2026', 'total_views': '0', 'total_karma': 0, 'total_contributions': 0},
        {'platform': 'Quora', 'period_type': 'Monthly', 'period_label': 'May 2026', 'total_views': '0', 'total_karma': 0, 'total_contributions': 0},
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
