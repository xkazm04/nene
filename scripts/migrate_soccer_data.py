import csv
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.top.top_lists import top_lists_service
from models.top import ItemCreate, ListCreate, ListItemCreate, CategoryEnum

async def migrate_soccer_data():
    """Migrate soccer players data from CSV"""
    
    # Read CSV file
    csv_path = "data/top/soccer_players.csv"
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            # Create items first
            items = []
            for i, row in enumerate(reader):
                item_data = ItemCreate(
                    name=row['name'],
                    category=CategoryEnum.SPORTS,
                    subcategory='soccer',
                    accolades=row['accolades'] if row['accolades'] else None
                )
                
                try:
                    item = await top_lists_service.create_item(item_data)
                    items.append(item)
                    print(f"Created item {i+1}: {item.name}")
                except Exception as e:
                    print(f"Error creating item {row['name']}: {e}")
            
            # Create a predefined list
            list_data = ListCreate(
                title="Top Soccer Players of All Time",
                category=CategoryEnum.SPORTS,
                subcategory="soccer",
                predefined=True,
                size=len(items)
            )
            
            list_obj = await top_lists_service.create_list(list_data)
            print(f"Created list: {list_obj.title}")
            
            # Add items to list with rankings
            for i, item in enumerate(items):
                list_item_data = ListItemCreate(
                    list_id=list_obj.id,
                    item_id=item.id,
                    ranking=i + 1
                )
                
                try:
                    await top_lists_service.add_item_to_list(list_item_data)
                    print(f"Added {item.name} to list at ranking {i+1}")
                except Exception as e:
                    print(f"Error adding {item.name} to list: {e}")
            
            print(f"Migration completed! Created {len(items)} items and 1 list.")
            
    except FileNotFoundError:
        print(f"CSV file not found: {csv_path}")
    except Exception as e:
        print(f"Migration error: {e}")

if __name__ == "__main__":
    asyncio.run(migrate_soccer_data())