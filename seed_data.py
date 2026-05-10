"""Seed database with Excel data"""
import json
import os

def seed_database(db, Engagement, Pipeline, Draft, Account):
    # Check if already seeded
    if Engagement.query.count() > 0:
        return {'message': 'Database already seeded', 'engagement_count': Engagement.query.count()}
    
    # Load data from JSON file
    basedir = os.path.abspath(os.path.dirname(__file__))
    json_path = os.path.join(basedir, 'data.json')
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Seed engagements
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
    
    # Seed pipeline
    pipeline_count = 0
    for item in data['pipeline']:
        pipeline = Pipeline(
            content=item.get('content', ''),
            platform=item.get('platform', ''),
            status=item.get('status', 'Not Picked')
        )
        db.session.add(pipeline)
        pipeline_count += 1
    
    # Seed drafts
    draft_count = 0
    for item in data['drafts']:
        draft = Draft(
            content=item.get('content', ''),
            platform='Reddit',
            status='Draft'
        )
        db.session.add(draft)
        draft_count += 1
    
    db.session.commit()
    
    return {
        'message': 'Database seeded successfully',
        'engagements': count,
        'pipeline': pipeline_count,
        'drafts': draft_count
    }
