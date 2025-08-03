import json
import os
import time
from datetime import datetime

# Assuming these functions are available from app.py or a shared utility
# For now, we'll assume they are passed in or imported from a common source.
# In the final implementation, we'll ensure proper import paths.

CACHE_FILE = 'cached_series_data.json'

def get_cached_data():
    """Loads cached series data from a JSON file."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Cache file {CACHE_FILE} is empty or contains invalid JSON. Returning None.")
            return None
    return None

def save_cached_data(data):
    """Saves series data to a JSON file."""
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def process_and_cache_series_data(get_categories_func, get_series_by_category_func, progress_callback=None):
    """Fetches, processes, and caches series data."""
    print("Starting series data caching process...")
    cached_data = {
        "last_fetch_date": datetime.now().isoformat(),
        "categories": [],
        "series": {}
    }

    categories = get_categories_func()
    if not categories:
        print("No categories found to cache.")
        if progress_callback:
            progress_callback(100, "No categories found.", "error")
        return False

    total_categories = len(categories)
    total_series_processed = 0
    failed_series_count = 0

    for i, category in enumerate(categories):
        category_id = category.get("category_id")
        category_name = category.get("category_name")
        
        if progress_callback:
            progress = int(((i + 1) / total_categories) * 100)
            progress_callback(progress, f"Processing category: {category_name}", "in_progress")

        if category_id and category_name:
            print(f"Processing category: {category_name} (ID: {category_id})")
            series_list = get_series_by_category_func(category_id)
            if series_list:
                for series in series_list:
                    series_id = series.get("series_id")
                    series_name = series.get("name")
                    actors = series.get("cast")
                    plot = series.get("plot")
                    
                    if series_id and series_name:
                        cached_data["series"][str(series_id)] = {
                            "series_name": series_name,
                            "category_ID": category_id,
                            "actors": actors.split(', ') if actors else [],
                            "plot": plot if plot else ""
                        }
                        total_series_processed += 1
                        print(f"  Cached series: {series_name} (Total processed: {total_series_processed})")
                    else:
                        failed_series_count += 1
                        print(f"  Skipping series due to missing ID or name: {series} (Failed: {failed_series_count})")
            else:
                print(f"  No series found for category: {category_name}")
        else:
            failed_series_count += 1 # Consider if this should count as a failed series or category
            print(f"Skipping category due to missing ID or name: {category}")

    save_cached_data(cached_data)
    print(f"Caching process completed. Total series processed: {total_series_processed}, Failed series: {failed_series_count}.")
    if progress_callback:
        progress_callback(100, "Caching process completed.", "complete")
    return True

def search_series(query):
    """Searches cached series data for matching series names, actors, or plot."""
    cached_data = get_cached_data()
    if not cached_data:
        return [], None

    results = []
    query_lower = query.lower()
    last_fetch_date = cached_data.get("last_fetch_date")

    for series_id, series_data in cached_data.get("series", {}).items():
        series_name_lower = series_data.get('series_name', '').lower()
        actors_lower = ' '.join(series_data.get('actors', [])).lower()
        plot_lower = series_data.get('plot', '').lower()

        if query_lower in series_name_lower or \
           query_lower in actors_lower or \
           query_lower in plot_lower:
            # Add series_id to the dictionary before appending to results
            series_data['series_id'] = series_id
            results.append(series_data)
            
    return results, last_fetch_date


def get_series_count_by_category():
    """Returns a dictionary mapping category IDs to their series count."""
    cached_data = get_cached_data()
    if not cached_data:
        return {}
        
    category_counts = {}
    for series_data in cached_data.get("series", {}).values():
        category_id = series_data.get("category_ID")
        if category_id:
            category_counts[category_id] = category_counts.get(category_id, 0) + 1
            
    return category_counts