#!/usr/bin/env python3
"""
Spotify to Jellyfin Direct Importer
Reads Spotify CSV exports and creates playlists directly in Jellyfin.
Skips the M3U intermediate step.
"""

import os
import csv
import re
import urllib.parse
import sys
import time
import difflib
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ================= CONFIGURATION =================
JELLYFIN_URL = os.getenv("JELLYFIN_URL", "")
API_KEY = os.getenv("JELLYFIN_API_KEY", "")
USER_ID = os.getenv("JELLYFIN_USER_ID", "")
FUZZY_THRESHOLD = 0.85  # 85% similarity required for fuzzy matching
# =================================================

session = requests.Session()
session.headers.update({"X-Emby-Token": API_KEY, "Content-Type": "application/json"})


def clean_text(text):
    """
    Creates a 'search key'.
    1. Decodes URL
    2. Removes brackets [] and parentheses () content
    3. Removes junk words
    4. Removes leading 'the'
    5. Returns only alphanumeric characters
    """
    if not text:
        return ""
    text = urllib.parse.unquote(text).lower()

    # Remove youtube brackets [id]
    text = re.sub(r'\[.*?\]', '', text)
    # Remove parentheses content (remix info, etc)
    text = re.sub(r'\(.*?\)', '', text)

    # Remove junk words
    junk = ["official", "video", "audio", "lyrics", "visualiser", "visualizer", 
            "hd", "4k", "mv", "soundtrack", "topic", "remaster", "remastered"]
    for word in junk:
        text = text.replace(word, "")

    # Remove non-alphanumeric (keep letters and numbers only)
    text = re.sub(r'[^a-z0-9]', '', text)

    # Remove leading "the" (The Kooks -> kooks)
    if text.startswith("the"):
        text = text[3:]

    return text


def fetch_library_index():
    """Fetches all audio items from Jellyfin and builds a search index."""
    print(f"⏳ Downloading Jellyfin library index from: {JELLYFIN_URL}")
    start = time.time()

    params = {
        "IncludeItemTypes": "Audio",
        "Recursive": "true",
        "Fields": "Name,Artists,Album",
        "UserId": USER_ID
    }

    try:
        r = session.get(f"{JELLYFIN_URL}/Items", params=params)
        r.raise_for_status()
        items = r.json().get("Items", [])
    except Exception as e:
        print(f"❌ API Error: {e}")
        sys.exit(1)

    print(f"   Fetched {len(items)} items in {round(time.time() - start, 2)}s. Building Index...")

    # Store keys pointing to IDs
    index_map = {}

    for item in items:
        item_id = item["Id"]
        name = item.get("Name", "")
        artists = item.get("Artists", [])

        # 1. Title Only Key
        t_key = clean_text(name)
        if t_key:
            index_map[t_key] = item_id

        # 2. Artist + Title Key (most reliable)
        for artist in artists:
            a_key = clean_text(artist)
            if a_key and t_key:
                full_key = a_key + t_key
                index_map[full_key] = item_id

    print(f"✅ Index ready ({len(index_map)} keys).")
    return index_map


def find_fuzzy_match(search_key, index_keys):
    """Returns the best match if score > threshold."""
    matches = difflib.get_close_matches(search_key, index_keys, n=1, cutoff=FUZZY_THRESHOLD)
    if matches:
        return matches[0]
    return None


def find_track_in_index(artist, track_name, index_map):
    """
    Attempts to find a matching track in Jellyfin library.
    Returns (item_id, match_type) or (None, reason).
    """
    candidates = []

    # Candidate 1: Artist + Title (most reliable)
    if artist and track_name:
        artist_key = clean_text(artist)
        title_key = clean_text(track_name)
        combined_key = artist_key + title_key
        candidates.append(("combined", combined_key))

    # Candidate 2: Title only
    if track_name:
        title_key = clean_text(track_name)
        candidates.append(("title", title_key))

    for match_type, key in candidates:
        if not key:
            continue

        # Step 1: Exact Match
        if key in index_map:
            return index_map[key], f"Exact ({match_type})"

        # Step 2: Fuzzy Match (catches typos, slight variations)
        if len(key) > 4:
            fuzzy_key = find_fuzzy_match(key, index_map.keys())
            if fuzzy_key:
                return index_map[fuzzy_key], f"Fuzzy ({match_type})"

    return None, "Not found"


def get_or_create_playlist(name):
    """Gets existing playlist by name or creates a new one."""
    try:
        r = session.get(
            f"{JELLYFIN_URL}/Users/{USER_ID}/Items",
            params={
                "searchTerm": name,
                "IncludeItemTypes": "Playlist",
                "Recursive": "true"
            }
        )
        data = r.json()
        if data["TotalRecordCount"] > 0:
            # Check for exact name match
            for item in data["Items"]:
                if item["Name"].lower() == name.lower():
                    return item["Id"], True
    except Exception as e:
        print(f"⚠️ Error searching for playlist: {e}")

    # Create new playlist
    try:
        r = session.post(
            f"{JELLYFIN_URL}/Playlists",
            params={"Name": name, "UserId": USER_ID}
        )
        r.raise_for_status()
        return r.json()["Id"], False
    except Exception as e:
        print(f"❌ Error creating playlist: {e}")
        sys.exit(1)


def get_playlist_items(playlist_id):
    """Gets existing items in a playlist to avoid duplicates."""
    try:
        r = session.get(
            f"{JELLYFIN_URL}/Playlists/{playlist_id}/Items",
            params={"UserId": USER_ID}
        )
        return {i["Id"] for i in r.json().get("Items", [])}
    except:
        return set()


def add_items_to_playlist(playlist_id, item_ids):
    """Adds items to a Jellyfin playlist."""
    if not item_ids:
        return

    try:
        session.post(
            f"{JELLYFIN_URL}/Playlists/{playlist_id}/Items",
            params={"Ids": ",".join(item_ids), "UserId": USER_ID}
        )
    except Exception as e:
        print(f"⚠️ Error adding items to playlist: {e}")


def process_csv(csv_path, playlist_name, index_map, verbose=False):
    """Processes a Spotify CSV file and creates/updates a Jellyfin playlist."""
    print(f"\n📂 Processing: {csv_path}")
    print(f"   Playlist name: {playlist_name}")

    # Get or create playlist
    playlist_id, exists = get_or_create_playlist(playlist_name)
    status = "Found existing" if exists else "Created new"
    print(f"   {status} playlist (ID: {playlist_id})")

    # Get existing items to avoid duplicates
    existing_ids = get_playlist_items(playlist_id) if exists else set()

    to_add = []
    missing = []
    found_count = 0
    skipped_count = 0
    fieldnames = []

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []

            for row in reader:
                # Handle different CSV column names
                artist = row.get('Artist Name(s)') or row.get('Artist') or row.get('artist') or ''
                track = row.get('Track Name') or row.get('Track') or row.get('track') or row.get('name') or ''

                if not track:
                    continue

                found_id, match_type = find_track_in_index(artist, track, index_map)

                if found_id:
                    if found_id not in existing_ids and found_id not in to_add:
                        to_add.append(found_id)
                        found_count += 1
                        if verbose:
                            print(f"   ✓ {artist} - {track} [{match_type}]")
                    else:
                        skipped_count += 1
                else:
                    missing.append(row)

    except FileNotFoundError:
        print(f"❌ File not found: {csv_path}")
        return
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return

    # Add tracks to playlist
    if to_add:
        add_items_to_playlist(playlist_id, to_add)

    # Print summary
    print(f"\n   📊 Results for '{playlist_name}':")
    print(f"      ✅ Added: {found_count}")
    print(f"      ⏭️  Skipped (duplicates): {skipped_count}")
    print(f"      ❌ Missing: {len(missing)}")

    # Print missing tracks
    if missing and verbose:
        print(f"\n   Missing tracks:")
        for row in missing:
            artist = row.get('Artist Name(s)') or row.get('Artist') or row.get('artist') or ''
            track = row.get('Track Name') or row.get('Track') or row.get('track') or row.get('name') or ''
            print(f"      ❌ {artist} - {track}")

    return {
        "added": found_count,
        "skipped": skipped_count,
        "missing": len(missing),
        "missing_tracks": missing,
        "fieldnames": fieldnames
    }


def process_folder(folder_path, index_map, verbose=False):
    """Processes all CSV files in a folder."""
    if not os.path.isdir(folder_path):
        print(f"❌ Folder not found: {folder_path}")
        return

    csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
    csv_files.sort()

    if not csv_files:
        print(f"❌ No CSV files found in: {folder_path}")
        return

    print(f"\n🚀 Processing {len(csv_files)} CSV files...")

    total_added = 0
    total_missing = 0
    all_missing = []
    all_fieldnames = set()

    for csv_file in csv_files:
        playlist_name = os.path.splitext(csv_file)[0].replace("_", " ")
        csv_path = os.path.join(folder_path, csv_file)

        result = process_csv(csv_path, playlist_name, index_map, verbose)
        if result:
            total_added += result["added"]
            total_missing += result["missing"]
            all_missing.extend([(playlist_name, t) for t in result["missing_tracks"]])
            all_fieldnames.update(result["fieldnames"])

    print(f"\n{'='*50}")
    print(f"📊 TOTAL: Added {total_added} tracks, Missing {total_missing} tracks")

    # Optionally save missing tracks to CSV file
    if all_missing:
        missing_file = "_missing_tracks.csv"
        # Use original CSV columns + Playlist column
        columns = ['Playlist'] + list(all_fieldnames)
        with open(missing_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
            writer.writeheader()
            for playlist, row in all_missing:
                row_with_playlist = {'Playlist': playlist, **row}
                writer.writerow(row_with_playlist)
        print(f"📝 Missing tracks saved to: {missing_file}")


def main():
    print("🎵 Spotify to Jellyfin Direct Importer")
    print("=" * 40)

    # Validate configuration
    if not all([JELLYFIN_URL, API_KEY, USER_ID]):
        print("❌ Error: Missing configuration!")
        print("   Please set the following environment variables:")
        print("   - JELLYFIN_URL")
        print("   - JELLYFIN_API_KEY")
        print("   - JELLYFIN_USER_ID")
        print("\n   You can create a .env file from .env.example")
        sys.exit(1)

    mode = input("Import (1) single CSV or (2) folder of CSVs? [1/2]: ").strip()
    verbose_input = input("Show verbose output? [y/N]: ").strip().lower()
    verbose = verbose_input in ('y', 'yes')

    # Fetch Jellyfin library index
    index_map = fetch_library_index()

    if mode == "2":
        folder = input("Enter folder path [./exports]: ").strip() or "./exports"
        process_folder(folder, index_map, verbose)
    else:
        csv_path = input("Enter CSV file path: ").strip()
        default_name = os.path.splitext(os.path.basename(csv_path))[0].replace("_", " ") if csv_path else "Imported Playlist"
        playlist_name = input(f"Enter playlist name [{default_name}]: ").strip() or default_name
        process_csv(csv_path, playlist_name, index_map, verbose)

    print("\n🏁 Done!")


if __name__ == "__main__":
    main()
