from typing import List, Dict, Any

def parse_timeline_response(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse Supabase response into timeline list."""
    results = []
    for row in data:
        result = {
            "id": str(row.get('id', '')),
            "title": row.get('title', ''),
            "question": row.get('question', ''),
            "dimension_top_title": row.get('dimension_top_title', ''),
            "dimension_bottom_title": row.get('dimension_bottom_title', ''),
            "created_at": row.get('created_at'),
            "updated_at": row.get('updated_at')
        }
        results.append(result)
    return results

def parse_timeline_detail_response(timeline_data: Dict[str, Any], milestones_data: List[Dict[str, Any]], events_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Parse timeline detail with milestones and events."""
    
    # Group events by milestone_id
    events_by_milestone = {}
    for event in events_data:
        milestone_id = str(event['milestone_id'])
        if milestone_id not in events_by_milestone:
            events_by_milestone[milestone_id] = []
        
        event_obj = {
            "id": str(event['id']),
            "milestone_id": str(event['milestone_id']),
            "title": event['title'],
            "description": event['description'],
            "text_1": event.get('text_1'),
            "text_2": event.get('text_2'),
            "text_3": event.get('text_3'),
            "text_4": event.get('text_4'),
            "reference_url": event.get('reference_url'),
            "order": event['order_index']
        }
        events_by_milestone[milestone_id].append(event_obj)
    
    # Sort events within each milestone by order
    for milestone_id in events_by_milestone:
        events_by_milestone[milestone_id].sort(key=lambda x: x['order'])
    
    # Build milestones with their events
    milestones = []
    for milestone in milestones_data:
        milestone_id = str(milestone['id'])
        milestone_obj = {
            "id": milestone_id,
            "date": milestone['date'],
            "events": events_by_milestone.get(milestone_id, []),
            "order": milestone['order_index'],
            "is_top": milestone['is_top']
        }
        milestones.append(milestone_obj)
    
    # Sort milestones by order
    milestones.sort(key=lambda x: x['order'])
    
    # Build complete timeline response
    return {
        "id": str(timeline_data['id']),
        "title": timeline_data['title'],
        "question": timeline_data['question'],
        "dimension_top_title": timeline_data['dimension_top_title'],
        "dimension_bottom_title": timeline_data['dimension_bottom_title'],
        "milestones": milestones,
        "created_at": timeline_data['created_at'],
        "updated_at": timeline_data['updated_at']
    }