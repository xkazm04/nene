import json
import os
import sys
from datetime import datetime
from supabase import create_client, Client
import logging

# Add parent directory to path to import models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables are required")

supabase: Client = create_client(supabase_url, supabase_key)


# Script to import timeline data from JSON file into Supabase database
# Create a sample JSON file
# python scripts/import_timeline_data.py --create-sample timeline_sample.json

# Import from JSON file
# python scripts/import_timeline_data.py --json-file timeline_sample.json

# Or import sample data directly
# python scripts/import_timeline_data.py --import-sample

def import_timeline_from_json(json_file_path: str):
    """
    Import timeline data from JSON file into Supabase database.
    
    Args:
        json_file_path: Path to JSON file containing timeline data
    """
    try:
        # Read JSON file
        with open(json_file_path, 'r', encoding='utf-8') as file:
            timeline_data = json.load(file)
        
        logger.info(f"Loaded timeline data from {json_file_path}")
        
        # Insert timeline
        timeline_insert = {
            "title": timeline_data["title"],
            "question": timeline_data["question"],
            "dimension_top_title": timeline_data["dimensionTopTitle"],
            "dimension_bottom_title": timeline_data["dimensionBottomTitle"]
        }
        
        timeline_result = supabase.table('edu_timeline').insert(timeline_insert).execute()
        
        if not timeline_result.data:
            raise Exception("Failed to insert timeline")
        
        timeline_id = timeline_result.data[0]['id']
        logger.info(f"Inserted timeline with ID: {timeline_id}")
        
        # Insert milestones and events
        for milestone_data in timeline_data["milestones"]:
            # Insert milestone
            milestone_insert = {
                "timeline_id": timeline_id,
                "date": milestone_data["date"],
                "order_index": milestone_data["order"],
                "is_top": milestone_data["isTop"]
            }
            
            milestone_result = supabase.table('edu_milestone').insert(milestone_insert).execute()
            
            if not milestone_result.data:
                raise Exception(f"Failed to insert milestone {milestone_data['id']}")
            
            milestone_id = milestone_result.data[0]['id']
            logger.info(f"Inserted milestone {milestone_data['date']} with ID: {milestone_id}")
            
            # Insert events for this milestone
            for event_data in milestone_data["events"]:
                event_insert = {
                    "milestone_id": milestone_id,
                    "title": event_data["title"],
                    "description": event_data["description"],
                    "text_1": event_data.get("text_1"),
                    "text_2": event_data.get("text_2"),
                    "text_3": event_data.get("text_3"),
                    "text_4": event_data.get("text_4"),
                    "reference_url": event_data.get("reference_url"),
                    "order_index": event_data["order"]
                }
                
                event_result = supabase.table('edu_event').insert(event_insert).execute()
                
                if not event_result.data:
                    raise Exception(f"Failed to insert event {event_data['id']}")
                
                event_id = event_result.data[0]['id']
                logger.info(f"Inserted event '{event_data['title']}' with ID: {event_id}")
        
        logger.info(f"Successfully imported complete timeline: {timeline_data['title']}")
        return timeline_id
        
    except Exception as e:
        logger.error(f"Error importing timeline: {str(e)}")
        raise

def create_sample_json_file(output_path: str):
    """
    Create a sample JSON file based on the sampleData.tsx structure.
    """
    sample_data = {
        "title": "Fact-Checking Political Misinformation Timeline",
        "question": "How have major political misinformation campaigns evolved and been debunked over time?",
        "dimensionTopTitle": "Economic Dimension",
        "dimensionBottomTitle": "Historical Facts",
        "milestones": [
            {
                "id": "milestone-1",
                "date": "1938",
                "order": 1,
                "isTop": True,
                "events": [
                    {
                        "id": "event-1",
                        "title": "War of the Worlds Radio Broadcast Panic",
                        "description": "Orson Welles' radio adaptation of H.G. Wells' 'War of the Worlds' was presented as a series of news bulletins, leading some listeners to believe that Earth was actually being invaded by Martians. While the panic was later exaggerated by newspapers, it demonstrated the power of media manipulation.",
                        "text_1": "The supposed mass panic was largely fabricated by newspapers seeking to discredit radio as a news medium. Critical analysis shows only scattered reports of genuine fear, not widespread hysteria.",
                        "text_2": "Newspaper industry was losing advertising revenue to radio. Creating the panic narrative served to undermine radio's credibility as a news source and protect print media's economic interests.",
                        "text_3": "People just got confused because they tuned in late and missed the introduction. Simple case of not paying attention to the whole story.",
                        "text_4": "Classic example of authority manipulation - using realistic news format triggers automatic trust responses. The authoritative voice patterns mimicked trusted news anchors, bypassing critical thinking.",
                        "reference_url": "https://www.snopes.com/fact-check/war-worlds-broadcast/",
                        "order": 1
                    }
                ]
            },
            {
                "id": "milestone-2",
                "date": "1950s",
                "order": 2,
                "isTop": False,
                "events": [
                    {
                        "id": "event-2",
                        "title": "McCarthyism Communist Infiltration Claims",
                        "description": "Senator Joseph McCarthy claimed to have a list of communist infiltrators in the U.S. government. His accusations were largely unfounded and destroyed many careers before being discredited.",
                        "text_1": "McCarthy's evidence was consistently vague and unsubstantiated. His refusal to provide concrete proof and constantly changing numbers indicate a politically motivated witch hunt.",
                        "text_2": "Post-war anxiety created a market for security theater. McCarthy's crusade attracted funding, media attention, and political capital while defense contractors benefited from increased security spending.",
                        "text_3": "People were scared after WWII and just wanted someone to blame for their problems. Communists were an easy target because they seemed foreign and threatening.",
                        "text_4": "Textbook scapegoating and in-group/out-group manipulation. Created an us-versus-them mentality where questioning McCarthy meant being labeled a communist sympathizer.",
                        "reference_url": "https://www.history.com/topics/cold-war/joseph-mccarthy",
                        "order": 1
                    }
                ]
            }
        ]
    }
    
    with open(output_path, 'w', encoding='utf-8') as file:
        json.dump(sample_data, file, indent=2, ensure_ascii=False)
    
    logger.info(f"Created sample JSON file at {output_path}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Import timeline data into Supabase")
    parser.add_argument("--json-file", help="Path to JSON file to import")
    parser.add_argument("--create-sample", help="Create a sample JSON file at specified path")
    parser.add_argument("--import-sample", action="store_true", help="Import the sample data directly")
    
    args = parser.parse_args()
    
    if args.create_sample:
        create_sample_json_file(args.create_sample)
    elif args.json_file:
        timeline_id = import_timeline_from_json(args.json_file)
        print(f"Successfully imported timeline with ID: {timeline_id}")
    elif args.import_sample:
        # Create temporary sample file and import it
        temp_file = "/tmp/sample_timeline.json"
        create_sample_json_file(temp_file)
        timeline_id = import_timeline_from_json(temp_file)
        os.remove(temp_file)
        print(f"Successfully imported sample timeline with ID: {timeline_id}")
    else:
        parser.print_help()
        
