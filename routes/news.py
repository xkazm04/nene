from fastapi import APIRouter, Query, HTTPException
from fastapi_cache.decorator import cache
from typing import List, Optional, Dict, Any
from supabase import create_client, Client
from models.research_models import  StatementCategory
import logging
import os
from datetime import datetime, date

router = APIRouter(tags=["news"])
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

def parse_research_response(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse Supabase response into research results."""
    results = []
    for row in data:
        result = {
            "id": str(row.get('id', '')),
            "statement": row.get('statement', ''),
            "source": row.get('source'),
            "context": row.get('context'),
            "request_datetime": row.get('request_datetime'),
            "statement_date": row.get('statement_date'),
            "country": row.get('country'),
            "category": row.get('category'),
            "valid_sources": row.get('valid_sources'),
            "verdict": row.get('verdict'),
            "status": row.get('status'),
            "correction": row.get('correction'),
            "resources_agreed": row.get('resources_agreed'),
            "resources_disagreed": row.get('resources_disagreed'),
            "experts": row.get('experts'),
            "processed_at": row.get('processed_at'),
            "created_at": row.get('created_at'),
            "updated_at": row.get('updated_at')
        }
        results.append(result)
    return results

@router.get("/", response_model=List[Dict[str, Any]])
# @cache(expire=300)  # Cache for 5 minutes
async def get_research_results(
    # Pagination
    limit: int = Query(default=50, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    # Filtering
    status: Optional[str] = Query(default=None, description="Filter by status (TRUE, FALSE, MISLEADING, etc.)"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    country: Optional[str] = Query(default=None, description="Filter by country code"),
    source: Optional[str] = Query(default=None, description="Filter by source"),
    date_from: Optional[str] = Query(default=None, description="Filter by statement date from (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(default=None, description="Filter by statement date to (YYYY-MM-DD)"),
    processed_from: Optional[str] = Query(default=None, description="Filter by processed date from (YYYY-MM-DD)"),
    processed_to: Optional[str] = Query(default=None, description="Filter by processed date to (YYYY-MM-DD)"),
    # Search
    search: Optional[str] = Query(default=None, description="Search in statement, source, or context"),
    # Sorting
    sort_by: str = Query(default="processed_at", description="Sort field"),
    sort_order: str = Query(default="desc", regex="^(asc|desc)$", description="Sort order")
):
    """
    Get all research results with filtering, searching, sorting and pagination.
    """
    try:
        # Start with base query
        query = supabase.table('research_results').select(
            'id, statement, source, context, request_datetime, statement_date, '
            'country, category, valid_sources, verdict, status, correction, '
            'resources_agreed, resources_disagreed, experts, '
            'processed_at, created_at, updated_at'
        )
        
        # Apply basic filters
        if status:
            valid_statuses = ['TRUE', 'FALSE', 'MISLEADING', 'PARTIALLY_TRUE', 'UNVERIFIABLE']
            if status.upper() in valid_statuses:
                query = query.eq('status', status.upper())
            else:
                raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        
        if category:
            # Validate category exists in enum
            try:
                StatementCategory(category.lower())
                query = query.eq('category', category.lower())
            except ValueError:
                valid_categories = [cat.value for cat in StatementCategory]
                raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {valid_categories}")
        
        if country:
            query = query.eq('country', country.lower())
        
        if source:
            query = query.ilike('source', f'%{source}%')
        
        # Date filtering
        if date_from:
            try:
                date.fromisoformat(date_from)
                query = query.gte('statement_date', date_from)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_from format. Use YYYY-MM-DD")
        
        if date_to:
            try:
                date.fromisoformat(date_to)
                query = query.lte('statement_date', date_to)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_to format. Use YYYY-MM-DD")
        
        if processed_from:
            try:
                datetime.fromisoformat(processed_from + "T00:00:00")
                query = query.gte('processed_at', processed_from + "T00:00:00")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid processed_from format. Use YYYY-MM-DD")
        
        if processed_to:
            try:
                datetime.fromisoformat(processed_to + "T23:59:59")
                query = query.lte('processed_at', processed_to + "T23:59:59")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid processed_to format. Use YYYY-MM-DD")
        
        # Handle search functionality
        if search:
            # Use text search across multiple fields
            search_queries = []
            search_fields = ['statement', 'source', 'context', 'verdict']
            
            for field in search_fields:
                field_query = supabase.table('research_results').select('id').ilike(field, f'%{search}%')
                try:
                    result = field_query.execute()
                    search_queries.extend([row['id'] for row in result.data])
                except Exception as e:
                    logger.warning(f"Search in {field} failed: {e}")
            
            if search_queries:
                unique_ids = list(set(search_queries))
                query = query.in_('id', unique_ids)
            else:
                return []
        
        # Add sorting
        valid_sort_fields = {
            "processed_at", "created_at", "updated_at", "request_datetime", 
            "statement_date", "status", "category", "country", "source"
        }
        if sort_by not in valid_sort_fields:
            sort_by = "processed_at"
        
        if sort_order == "desc":
            query = query.order(sort_by, desc=True)
        else:
            query = query.order(sort_by, desc=False)
        
        # Add pagination
        query = query.range(offset, offset + limit - 1)
        
        # Execute query
        result = query.execute()
        
        if result.data is None:
            logger.warning("No data returned from Supabase query")
            return []
        
        results = parse_research_response(result.data)
        
        logger.info(f"Retrieved {len(results)} research results with filters: status={status}, category={category}, country={country}")
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving research results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve research results: {str(e)}")

@router.get("/{research_id}")
@cache(expire=600)  # Cache for 10 minutes
async def get_research_result(research_id: str):
    """
    Get a specific research result by ID.
    """
    try:
        result = supabase.table('research_results').select('*').eq('id', research_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Research result not found")
        
        research_data = result.data[0]
        
        # Parse and return the research result
        return {
            "id": str(research_data['id']),
            "statement": research_data['statement'],
            "source": research_data.get('source'),
            "context": research_data.get('context'),
            "request_datetime": research_data['request_datetime'],
            "statement_date": research_data.get('statement_date'),
            "country": research_data.get('country'),
            "category": research_data.get('category'),
            "valid_sources": research_data.get('valid_sources'),
            "verdict": research_data.get('verdict'),
            "status": research_data.get('status'),
            "correction": research_data.get('correction'),
            "resources_agreed": research_data.get('resources_agreed'),
            "resources_disagreed": research_data.get('resources_disagreed'),
            "experts": research_data.get('experts'),
            "processed_at": research_data.get('processed_at'),
            "created_at": research_data.get('created_at'),
            "updated_at": research_data.get('updated_at')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving research result {research_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve research result: {str(e)}")

@router.get("/search/advanced")
@cache(expire=300)
async def search_research_advanced(
    search_text: Optional[str] = Query(default=None, description="Search text"),
    status_filter: Optional[str] = Query(default=None, description="Status filter"),
    country_filter: Optional[str] = Query(default=None, description="Country filter"),
    category_filter: Optional[str] = Query(default=None, description="Category filter"),
    source_filter: Optional[str] = Query(default=None, description="Source filter"),
    limit_count: int = Query(default=50, ge=1, le=100, description="Limit results"),
    offset_count: int = Query(default=0, ge=0, description="Offset results")
):
    """
    Advanced search using the database search function.
    """
    try:
        # Use the PostgreSQL search function
        result = supabase.rpc('search_research_results', {
            'search_text': search_text,
            'status_filter': status_filter,
            'country_filter': country_filter,
            'category_filter': category_filter,
            'limit_count': limit_count,
            'offset_count': offset_count
        }).execute()  # Add .execute() here
        
        if not result.data:
            return []
        
        # Transform results to include match ranking
        results = []
        for row in result.data:
            result_data = {
                "id": str(row['id']),
                "statement": row['statement'],
                "source": row['source'],
                "status": row['status'],
                "country": row['country'],
                "category": row['category'],
                "processed_at": row['processed_at'],
                "match_rank": row['match_rank']
            }
            results.append(result_data)
        
        return results
        
    except Exception as e:
        logger.error(f"Error in advanced search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/stats/summary")
@cache(expire=600)
async def get_research_stats():
    """
    Get summary statistics about research results.
    """
    try:
        # Get basic stats
        result = supabase.table('research_results').select(
            'id, status, category, country, created_at, statement_date'
        ).execute()
        
        if not result.data:
            return {
                "total_results": 0,
                "status_distribution": {},
                "category_distribution": {},
                "country_distribution": {},
                "recent_results": 0,
                "earliest_result": None,
                "latest_result": None
            }
        
        data = result.data
        
        # Calculate statistics
        total_results = len(data)
        
        # Status distribution
        status_distribution = {}
        for row in data:
            status = row.get('status', 'UNKNOWN')
            status_distribution[status] = status_distribution.get(status, 0) + 1
        
        # Category distribution
        category_distribution = {}
        for row in data:
            category = row.get('category', 'other')
            if category:
                category_distribution[category] = category_distribution.get(category, 0) + 1
        
        # Country distribution
        country_distribution = {}
        for row in data:
            country = row.get('country')
            if country:
                country_distribution[country] = country_distribution.get(country, 0) + 1
        
        # Date analysis
        created_dates = [row.get('created_at') for row in data if row.get('created_at')]
        earliest_result = min(created_dates) if created_dates else None
        latest_result = max(created_dates) if created_dates else None
        
        # Recent results (last 7 days)
        from datetime import datetime, timedelta
        week_ago = datetime.now() - timedelta(days=7)
        recent_results = sum(1 for row in data 
                           if row.get('created_at') and 
                           datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) > week_ago)
        
        return {
            "total_results": total_results,
            "status_distribution": status_distribution,
            "category_distribution": category_distribution,
            "country_distribution": country_distribution,
            "recent_results": recent_results,
            "earliest_result": earliest_result,
            "latest_result": latest_result
        }
        
    except Exception as e:
        logger.error(f"Error getting research stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")

@router.get("/categories/available")
@cache(expire=1800)  # Cache for 30 minutes
async def get_available_categories():
    """
    Get all available categories from research results.
    """
    try:
        result = supabase.table('research_results').select('category').execute()
        
        if not result.data:
            return []
        
        # Get unique categories, excluding null values
        categories = list(set([
            row['category'] for row in result.data 
            if row.get('category') is not None
        ]))
        
        # Return sorted list with category counts
        category_stats = {}
        for row in result.data:
            if row.get('category'):
                category_stats[row['category']] = category_stats.get(row['category'], 0) + 1
        
        return [
            {
                "category": category,
                "count": category_stats.get(category, 0)
            }
            for category in sorted(categories)
        ]
        
    except Exception as e:
        logger.error(f"Error getting available categories: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get categories")

@router.get("/countries/available")
@cache(expire=1800)  # Cache for 30 minutes
async def get_available_countries():
    """
    Get all available countries from research results.
    """
    try:
        result = supabase.table('research_results').select('country').execute()
        
        if not result.data:
            return []
        
        # Get unique countries, excluding null values
        countries = list(set([
            row['country'] for row in result.data 
            if row.get('country') is not None
        ]))
        
        # Return sorted list with country counts
        country_stats = {}
        for row in result.data:
            if row.get('country'):
                country_stats[row['country']] = country_stats.get(row['country'], 0) + 1
        
        return [
            {
                "country": country,
                "count": country_stats.get(country, 0)
            }
            for country in sorted(countries)
        ]
        
    except Exception as e:
        logger.error(f"Error getting available countries: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get countries")