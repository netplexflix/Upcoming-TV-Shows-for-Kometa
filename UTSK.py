import yt_dlp
import requests
import re
import json
import yaml
import sys
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict
from copy import deepcopy

VERSION = "1.0"

# ANSI color codes
GREEN = '\033[32m'
ORANGE = '\033[33m'
BLUE = '\033[34m'
RED = '\033[31m'
RESET = '\033[0m'
BOLD = '\033[1m'

def load_config(file_path='config/config.yml'):
    """Load configuration from YAML file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Config file '{file_path}' not found.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML config file: {e}")
        sys.exit(1)

def process_sonarr_url(base_url, api_key):
    """Process and validate Sonarr URL"""
    base_url = base_url.rstrip('/')
    
    if base_url.startswith('http'):
        protocol_end = base_url.find('://') + 3
        next_slash = base_url.find('/', protocol_end)
        if next_slash != -1:
            base_url = base_url[:next_slash]
    
    api_paths = [
        '/api/v3',
        '/sonarr/api/v3'
    ]
    
    for path in api_paths:
        test_url = f"{base_url}{path}"
        try:
            headers = {"X-Api-Key": api_key}
            response = requests.get(f"{test_url}/health", headers=headers, timeout=10)
            if response.status_code == 200:
                print(f"Successfully connected to Sonarr at: {test_url}")
                return test_url
        except requests.exceptions.RequestException as e:
            print(f"{ORANGE}Testing URL {test_url} - Failed: {str(e)}{RESET}")
            continue
    
    raise ConnectionError(f"{RED}Unable to establish connection to Sonarr. Tried the following URLs:\n" + 
                        "\n".join([f"- {base_url}{path}" for path in api_paths]) + 
                        f"\nPlease verify your URL and API key and ensure Sonarr is running.{RESET}")

def get_sonarr_series(sonarr_url, api_key):
    """Get all series from Sonarr"""
    try:
        url = f"{sonarr_url}/series"
        headers = {"X-Api-Key": api_key}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error connecting to Sonarr: {str(e)}{RESET}")
        sys.exit(1)

def get_sonarr_episodes(sonarr_url, api_key, series_id):
    """Get episodes for a specific series"""
    try:
        url = f"{sonarr_url}/episode?seriesId={series_id}"
        headers = {"X-Api-Key": api_key}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error fetching episodes from Sonarr: {str(e)}{RESET}")
        sys.exit(1)

def convert_utc_to_local(utc_date_str, utc_offset):
    """Convert UTC datetime to local time with offset"""
    if not utc_date_str:
        return None
        
    # Remove 'Z' if present and parse the datetime
    clean_date_str = utc_date_str.replace('Z', '')
    utc_date = datetime.fromisoformat(clean_date_str).replace(tzinfo=timezone.utc)
    
    # Apply the UTC offset
    local_date = utc_date + timedelta(hours=utc_offset)
    return local_date

def find_upcoming_shows(sonarr_url, api_key, future_days_upcoming_shows, utc_offset=0, skip_unmonitored=False, debug=False):
    """Find shows with 'upcoming' status that have their first episode airing within specified days"""
    upcoming_shows = []
    skipped_shows = []
    
    cutoff_date = datetime.now(timezone.utc) + timedelta(days=future_days_upcoming_shows)
    now_local = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
    
    if debug:
        print(f"{BLUE}[DEBUG] Cutoff date: {cutoff_date}, Now local: {now_local}{RESET}")
    
    all_series = get_sonarr_series(sonarr_url, api_key)
    
    if debug:
        print(f"{BLUE}[DEBUG] Found {len(all_series)} total series in Sonarr{RESET}")
        upcoming_count = sum(1 for s in all_series if s.get('status') == 'upcoming')
        print(f"{BLUE}[DEBUG] {upcoming_count} series have 'upcoming' status{RESET}")
    
    for series in all_series:
        if series.get('status') == 'upcoming':
            if debug:
                print(f"{BLUE}[DEBUG] Processing upcoming show: {series['title']} (monitored: {series.get('monitored', True)}){RESET}")
            
            # Check if we should skip unmonitored shows
            if skip_unmonitored and not series.get('monitored', True):
                if debug:
                    print(f"{ORANGE}[DEBUG] Skipping unmonitored show: {series['title']}{RESET}")
                continue
            
            # Get episodes for this series
            episodes = get_sonarr_episodes(sonarr_url, api_key, series['id'])
            
            if debug:
                print(f"{BLUE}[DEBUG] Found {len(episodes)} episodes for {series['title']}{RESET}")
            
            # Find the first episode of season 1
            first_episode = None
            for ep in episodes:
                if ep.get('seasonNumber') == 1 and ep.get('episodeNumber') == 1:
                    first_episode = ep
                    break
            
            if not first_episode:
                if debug:
                    print(f"{ORANGE}[DEBUG] No Season 1 Episode 1 found for {series['title']}{RESET}")
                continue  # Skip if no season 1 episode 1 found
            
            air_date_str = first_episode.get('airDateUtc')
            if not air_date_str:
                if debug:
                    print(f"{ORANGE}[DEBUG] No air date found for {series['title']} S01E01{RESET}")
                continue  # Skip if no air date
            
            air_date = convert_utc_to_local(air_date_str, utc_offset)
            
            if debug:
                print(f"{BLUE}[DEBUG] {series['title']} air date: {air_date}, within range: {air_date > now_local and air_date <= cutoff_date}{RESET}")
            
            # Only include shows where the first episode airs within the specified days
            if air_date > now_local and air_date <= cutoff_date:
                tvdb_id = series.get('tvdbId')
                air_date_str_yyyy_mm_dd = air_date.date().isoformat()
                
                show_dict = {
                    'title': series['title'],
                    'tvdbId': tvdb_id,
                    'path': series.get('path', ''),
                    'imdbId': series.get('imdbId', ''),
                    'year': series.get('year', None),
                    'airDate': air_date_str_yyyy_mm_dd
                }
                
                upcoming_shows.append(show_dict)
                
                if debug:
                    print(f"{GREEN}[DEBUG] Added to upcoming shows: {series['title']}{RESET}")
    
    return upcoming_shows, skipped_shows

def _normalize(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', (s or '').lower()).strip()

def _base_show_title(show_title: str) -> str:
    # Remove a year in parentheses/brackets, e.g., "Show (2025)" -> "Show"
    return re.sub(r'\s*[\(\[]\d{4}[\)\]]\s*', ' ', show_title or '').strip()

def _title_matches(video_title: str, show_title: str) -> bool:
    # Require base show title as a substring (ignore year)
    base = _normalize(_base_show_title(show_title))
    vt = _normalize(video_title)
    return base and base in vt

def search_trailer_on_youtube(show_title, year=None, imdb_id=None, debug=False, skip_channels=None):
    """Return the best matching trailer info from YouTube (dict) or None."""
    search_terms = [
        f"{show_title} {year} trailer" if year else None,
        f"{show_title} {year} official trailer" if year else None,
        f"{show_title} {year} teaser" if year else None,
        f"{show_title} trailer",
        f"{show_title} official trailer",
        f"{show_title} teaser",
        f"{show_title} official teaser",
        f"{show_title} first look",
    ]
    search_terms = [t for t in search_terms if t]

    avoid_keywords = [
        'reaction','review','breakdown','analysis','explained','easter eggs','theory',
        'predictions','recap','commentary','first time watching','blind reaction',
        'behind the scenes','fan made','concept','music video','news','interview'
    ]

    # Common official studios/streamers
    official_channels = [
        'netflix','hbo','max','amazon','prime video','disney','marvel','lucasfilm',
        'apple tv','paramount','showtime','starz','fx','amc','peacock','universal',
        'sony pictures','warner bros','20th century','lionsgate','bbc','itv','channel 4','hulu'
    ]

    if debug:
        print(f"{BLUE}[DEBUG] Searching for trailers with these terms: {search_terms}{RESET}")
        if skip_channels:
            print(f"{BLUE}[DEBUG] Skip channels: {skip_channels}{RESET}")

    best = None
    best_score = -1

    for term in search_terms:
        try:
            if debug:
                print(f"{BLUE}[DEBUG] Trying search term: '{term}'{RESET}")

            cmd = ['yt-dlp','--dump-json','--no-warnings','--flat-playlist', f'ytsearch15:{term}']
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=45)

            if res.returncode != 0 or not res.stdout.strip():
                if debug:
                    print(f"{ORANGE}[DEBUG] No results for '{term}'{RESET}")
                continue

            for line in res.stdout.strip().splitlines():
                try:
                    info = json.loads(line)
                except json.JSONDecodeError:
                    continue

                title = info.get('title') or ''
                vid   = info.get('id') or ''
                up    = info.get('uploader') or 'Unknown'
                dur   = info.get('duration')  # may be int/float/None

                if not title or not vid:
                    continue

                # Skip unwanted channels
                if skip_channels and any(ch.lower() in up.lower() for ch in skip_channels):
                    continue

                # Skip non-trailer-y things
                tl = title.lower()
                if any(k in tl for k in avoid_keywords):
                    continue

                # Reasonable length (10s..15m)
                if dur and not (10 <= float(dur) <= 900):
                    continue

                # Must contain the show title (without year)
                if not _title_matches(title, show_title):
                    if debug:
                        print(f"{ORANGE}[DEBUG] Skipping '{title}' - does not match '{show_title}'{RESET}")
                    continue

                # Score: prefer official-looking titles/channels and matching year
                score = 0
                if 'official' in tl: score += 3
                if 'trailer'  in tl: score += 2
                if 'teaser'   in tl: score += 1
                if any(ch in up.lower() for ch in official_channels): score += 3
                if year and str(year) in tl: score += 2

                if score > best_score:
                    d = int(dur) if isinstance(dur, (int, float)) else 0
                    duration_str = f"{d//60}:{d%60:02d}" if d else "Unknown"
                    best_score = score
                    best = {
                        'video_id': vid,
                        'video_title': title,
                        'duration': duration_str,
                        'uploader': up,
                        'url': f'https://www.youtube.com/watch?v={vid}',
                        'is_official': True
                    }

        except subprocess.TimeoutExpired:
            if debug:
                print(f"{ORANGE}[DEBUG] Search timeout for '{term}'{RESET}")
            continue
        except Exception as e:
            if debug:
                print(f"{ORANGE}[DEBUG] Search error: {e}{RESET}")
            continue

    if debug and best:
        print(f"{GREEN}[DEBUG] Best match: {best}{RESET}")

    return best

def download_trailer(show, trailer_info, debug=False):
    """
    Download trailer preferring 1080p, allowing any container/codec,
    then recode to MP4 via ffmpeg for compatibility.
    Checks if file exists first to avoid unnecessary searches.
    """
    show_path = show.get('path')
    if not show_path:
        print(f"{RED}No path found for show: {show.get('title')}{RESET}")
        return False

    season_00_path = Path(show_path) / "Season 00"
    season_00_path.mkdir(parents=True, exist_ok=True)

    clean_title = "".join(c for c in show['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
    final_mp4_path = season_00_path / f"{clean_title}.S00E00.Trailer.mp4"

    # Check if trailer already exists FIRST
    if final_mp4_path.exists():
        print(f"{GREEN}Trailer already exists for {show['title']}{RESET}")
        return True

    # Only proceed with download if file doesn't exist
    filename = f"{clean_title}.S00E00.Trailer.%(ext)s"
    output_path = season_00_path / filename

    try:
        # Helper to run a single attempt with a given format string
        def _run(format_string):
            ydl_opts = {
                # Allow any codec/container at selected resolution; we'll recode to MP4 after
                'format': format_string,
                'outtmpl': str(output_path),
                'noplaylist': True,
                # Force final file to MP4 by recoding (robust even if input is VP9/AV1+Opus)
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4'
                }],
                # Ensure faststart for streaming compatibility
                'postprocessor_args': ['-movflags', '+faststart'],
                'ignoreerrors': False,
                'quiet': not debug,
                'no_warnings': not debug,
            }
            if debug:
                print(f"{BLUE}[DEBUG] yt-dlp opts (format): {format_string}{RESET}")
                print(f"{BLUE}[DEBUG] URL: {trailer_info['url']}{RESET}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([trailer_info['url']])

        print(f"Downloading trailer for {show['title']} (prefer 1080p, will recode to MP4)...")

        try:
            # Try EXACT 1080p first (any container/codec)
            _run('bv*[height=1080]+ba/b[height=1080]')
        except Exception as e1:
            if debug:
                print(f"{ORANGE}[DEBUG] 1080p exact failed ({e1}); trying best <=1080p{RESET}")
            # Then accept the best ≤1080p
            _run('bv*[height<=1080]+ba/b[height<=1080]')

        if final_mp4_path.exists():
            size_mb = final_mp4_path.stat().st_size / (1024 * 1024)
            print(f"{GREEN}Successfully downloaded trailer for {show['title']} ({size_mb:.1f} MB){RESET}")
            return True

        print(f"{RED}Trailer file not found after download for {show['title']}{RESET}")
        return False

    except Exception as e:
        print(f"{RED}Download error for {show['title']}: {e}{RESET}")
        return False

def format_date(yyyy_mm_dd, date_format, capitalize=False):
    """Format date according to specified format"""
    dt_obj = datetime.strptime(yyyy_mm_dd, "%Y-%m-%d")
    
    format_mapping = {
        'mmm': '%b',    # Abbreviated month name
        'mmmm': '%B',   # Full month name
        'mm': '%m',     # 2-digit month
        'm': '%-m',     # 1-digit month
        'dddd': '%A',   # Full weekday name
        'ddd': '%a',    # Abbreviated weekday name
        'dd': '%d',     # 2-digit day
        'd': str(dt_obj.day),  # 1-digit day - direct integer conversion
        'yyyy': '%Y',   # 4-digit year
        'yyy': '%Y',    # 3+ digit year
        'yy': '%y',     # 2-digit year
        'y': '%y'       # Year without century
    }
    
    # Sort format patterns by length (longest first) to avoid partial matches
    patterns = sorted(format_mapping.keys(), key=len, reverse=True)
    
    # First, replace format patterns with temporary markers
    temp_format = date_format
    replacements = {}
    for i, pattern in enumerate(patterns):
        marker = f"@@{i}@@"
        if pattern in temp_format:
            replacements[marker] = format_mapping[pattern]
            temp_format = temp_format.replace(pattern, marker)
    
    # Now replace the markers with strftime formats
    strftime_format = temp_format
    for marker, replacement in replacements.items():
        strftime_format = strftime_format.replace(marker, replacement)
    
    try:
        result = dt_obj.strftime(strftime_format)
        if capitalize:
            result = result.upper()
        return result
    except ValueError as e:
        print(f"{RED}Error: Invalid date format '{date_format}'. Using default format.{RESET}")
        return yyyy_mm_dd  # Return original format as fallback

def create_overlay_yaml(output_file, shows, config_sections):
    """Create overlay YAML file with shows grouped by air date"""
    import yaml

    if not shows:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("#No matching shows found")
        return
    
    # Group shows by date
    date_to_tvdb_ids = defaultdict(list)
    all_tvdb_ids = set()
    
    for s in shows:
        if s.get("tvdbId"):
            all_tvdb_ids.add(s['tvdbId'])
        
        # Add to date groups
        if s.get("airDate"):
            date_to_tvdb_ids[s['airDate']].append(s.get('tvdbId'))
    
    overlays_dict = {}
    
    # -- Backdrop Block --
    backdrop_config = deepcopy(config_sections.get("backdrop", {}))
    enable_backdrop = backdrop_config.pop("enable", True)

    if enable_backdrop and all_tvdb_ids:
        backdrop_config["name"] = "backdrop"
        all_tvdb_ids_str = ", ".join(str(i) for i in sorted(all_tvdb_ids) if i)
        
        overlays_dict["backdrop"] = {
            "overlay": backdrop_config,
            "tvdb_show": all_tvdb_ids_str
        }
    
    # -- Text Blocks --
    text_config = deepcopy(config_sections.get("text", {}))
    enable_text = text_config.pop("enable", True)
    
    if enable_text and all_tvdb_ids:
        date_format = text_config.pop("date_format", "yyyy-mm-dd")
        use_text = text_config.pop("use_text", "Coming Soon")
        capitalize_dates = text_config.pop("capitalize_dates", True)
        
        # Create date-specific overlays for shows with air dates
        if date_to_tvdb_ids:
            for date_str in sorted(date_to_tvdb_ids):
                formatted_date = format_date(date_str, date_format, capitalize_dates)
                sub_overlay_config = deepcopy(text_config)
                sub_overlay_config["name"] = f"text({use_text} {formatted_date})"
                
                tvdb_ids_for_date = sorted(tvdb_id for tvdb_id in date_to_tvdb_ids[date_str] if tvdb_id)
                tvdb_ids_str = ", ".join(str(i) for i in tvdb_ids_for_date)
                
                block_key = f"UTSK_{formatted_date}"
                overlays_dict[block_key] = {
                    "overlay": sub_overlay_config,
                    "tvdb_show": tvdb_ids_str
                }
        else:
            # Fallback for shows without air dates
            sub_overlay_config = deepcopy(text_config)
            sub_overlay_config["name"] = f"text({use_text})"
            
            tvdb_ids_str = ", ".join(str(i) for i in sorted(all_tvdb_ids) if i)
            
            overlays_dict["UTSK_upcoming_shows"] = {
                "overlay": sub_overlay_config,
                "tvdb_show": tvdb_ids_str
            }
    
    final_output = {"overlays": overlays_dict}
    
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(final_output, f, sort_keys=False)

def create_collection_yaml(output_file, shows, config):
    """Create collection YAML file"""
    import yaml
    from yaml.representer import SafeRepresenter
    from collections import OrderedDict

    # Add representer for OrderedDict
    def represent_ordereddict(dumper, data):
        return dumper.represent_mapping('tag:yaml.org,2002:map', data.items())
    
    yaml.add_representer(OrderedDict, represent_ordereddict, Dumper=yaml.SafeDumper)

    # Get the collection configuration
    config_key = "collection_upcoming_shows"
    collection_config = {}
    collection_name = "Upcoming Shows"
    
    if config_key in config:
        collection_config = deepcopy(config[config_key])
        collection_name = collection_config.pop("collection_name", "Upcoming Shows")
    
    # Get the future_days value for summary
    future_days = config.get('future_days_upcoming_shows', 30)
    summary = f"Shows with their first episode premiering within {future_days} days"
    
    class QuotedString(str):
        pass

    def quoted_str_presenter(dumper, data):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')

    yaml.add_representer(QuotedString, quoted_str_presenter, Dumper=yaml.SafeDumper)

    # Handle the case when no shows are found
    if not shows:
        data = {
            "collections": {
                collection_name: {
                    "plex_search": {
                        "all": {
                            "label": collection_name
                        }
                    },
                    "item_label.remove": collection_name,
                    "smart_label": "random",
                    "build_collection": False
                }
            }
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, Dumper=yaml.SafeDumper, sort_keys=False)
        return
    
    tvdb_ids = [s['tvdbId'] for s in shows if s.get('tvdbId')]
    if not tvdb_ids:
        data = {
            "collections": {
                collection_name: {
                    "plex_search": {
                        "all": {
                            "label": collection_name
                        }
                    },
                    "non_item_remove_label": collection_name,
                    "build_collection": False
                }
            }
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, Dumper=yaml.SafeDumper, sort_keys=False)
        return

    # Convert to comma-separated
    tvdb_ids_str = ", ".join(str(i) for i in sorted(tvdb_ids))

    # Create the collection data structure
    collection_data = {}
    collection_data["summary"] = summary
    
    # Add all remaining parameters from the collection config
    for key, value in collection_config.items():
        if key == "sort_title":
            collection_data[key] = QuotedString(value)
        else:
            collection_data[key] = value
    
    # Add sync_mode after the config parameters
    collection_data["sync_mode"] = "sync"
    
    # Add tvdb_show as the last item
    collection_data["tvdb_show"] = tvdb_ids_str

    # Create the final structure with ordered keys
    ordered_collection = OrderedDict()
    
    # Add keys in the desired order
    ordered_collection["summary"] = collection_data["summary"]
    if "sort_title" in collection_data:
        ordered_collection["sort_title"] = collection_data["sort_title"]
    
    # Add all other keys except sync_mode and tvdb_show
    for key, value in collection_data.items():
        if key not in ["summary", "sort_title", "sync_mode", "tvdb_show"]:
            ordered_collection[key] = value
    
    # Add sync_mode and tvdb_show at the end
    ordered_collection["sync_mode"] = collection_data["sync_mode"]
    ordered_collection["tvdb_show"] = collection_data["tvdb_show"]

    data = {
        "collections": {
            collection_name: ordered_collection
        }
    }

    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f, Dumper=yaml.SafeDumper, sort_keys=False)

def check_yt_dlp_installed():
    """Check if yt-dlp is installed and accessible"""
    # First check if yt_dlp module was imported successfully
    if yt_dlp is None:
        print(f"{RED}yt-dlp not installed. Please install yt-dlp first.{RESET}")
        print(f"{ORANGE}Install with: pip install yt-dlp{RESET}")
        return False
    
    # If module is available, test if the command-line tool works
    try:
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"{GREEN}yt-dlp found: {version}{RESET}")
            return True
        else:
            print(f"{RED}yt-dlp command not working properly{RESET}")
            return False
    except FileNotFoundError:
        print(f"{RED}yt-dlp command not found in PATH. Please ensure yt-dlp is properly installed.{RESET}")
        print(f"{ORANGE}Install with: pip install yt-dlp{RESET}")
        return False
    except subprocess.TimeoutExpired:
        print(f"{RED}yt-dlp command timed out{RESET}")
        return False
    except Exception as e:
        print(f"{RED}Error checking yt-dlp: {str(e)}{RESET}")
        return False

def main():
    start_time = datetime.now()
    print(f"{BLUE}{'*' * 44}\n{'*' * 5} Upcoming TV Shows for Kometa {VERSION} {'*' * 5}\n{'*' * 44}{RESET}")
    
    # Check if yt-dlp is available
    if not check_yt_dlp_installed():
        sys.exit(1)
    
    config = load_config('config/config.yml')
    
    try:
        # Process and validate Sonarr URL
        sonarr_url = process_sonarr_url(config['sonarr_url'], config['sonarr_api_key'])
        sonarr_api_key = config['sonarr_api_key']
        
        # Get configuration values
        future_days_upcoming_shows = config.get('future_days_upcoming_shows', 30)
        utc_offset = float(config.get('utc_offset', 0))
        skip_unmonitored = str(config.get("skip_unmonitored", "false")).lower() == "true"
        download_trailers = str(config.get("download_trailers", "true")).lower() == "true"
        debug = str(config.get("debug", "false")).lower() == "true"
        skip_channels = config.get("skip_channels", [])
        
        # Parse skip_channels if it's a string
        if isinstance(skip_channels, str):
            skip_channels = [ch.strip() for ch in skip_channels.split(',') if ch.strip()]
        
        print(f"future_days_upcoming_shows: {future_days_upcoming_shows}")
        print(f"UTC offset: {utc_offset} hours")
        print(f"skip_unmonitored: {skip_unmonitored}")
        print(f"download_trailers: {download_trailers}")
        print(f"debug: {debug}")
        print(f"skip_channels: {skip_channels}\n")

        # ---- Find Upcoming Shows ----
        upcoming_shows, skipped_shows = find_upcoming_shows(
            sonarr_url, sonarr_api_key, future_days_upcoming_shows, utc_offset, skip_unmonitored, debug
        )
        
        if upcoming_shows:
            print(f"{GREEN}Found {len(upcoming_shows)} upcoming shows with first episodes within {future_days_upcoming_shows} days:{RESET}")
            for show in upcoming_shows:
                print(f"- {show['title']}" + (f" ({show['year']})" if show['year'] else "") + f" - First episode: {show['airDate']}")
        else:
            print(f"{RED}No upcoming shows found with first episodes within {future_days_upcoming_shows} days.{RESET}")
        
        if skipped_shows:
            print(f"\n{ORANGE}Skipped shows (unmonitored):{RESET}")
            for show in skipped_shows:
                print(f"- {show['title']}" + (f" ({show['year']})" if show['year'] else ""))
        
        # ---- Download Trailers ----
        if download_trailers and upcoming_shows:
            print(f"\n{BLUE}Processing trailers for upcoming shows...{RESET}")
            successful_downloads = 0
            failed_downloads = 0
            skipped_existing = 0
            
            for show in upcoming_shows:
                print(f"\nProcessing: {show['title']}")
                
                # Check if trailer already exists first
                show_path = show.get('path')
                if show_path:
                    season_00_path = Path(show_path) / "Season 00"
                    clean_title = "".join(c for c in show['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    final_mp4_path = season_00_path / f"{clean_title}.S00E00.Trailer.mp4"
                    
                    if final_mp4_path.exists():
                        print(f"{GREEN}Trailer already exists for {show['title']} - skipping{RESET}")
                        skipped_existing += 1
                        successful_downloads += 1  # Count as successful since we have the file
                        continue
                
                # Search for trailer only if file doesn't exist
                trailer_info = search_trailer_on_youtube(
                    show['title'], 
                    show.get('year'), 
                    show.get('imdbId'),
                    debug,
                    skip_channels
                )
                
                if trailer_info:
                    print(f"Found trailer: {trailer_info['video_title']} ({trailer_info['duration']}) by {trailer_info['uploader']}")
                    
                    # Download trailer
                    if download_trailer(show, trailer_info, debug):
                        successful_downloads += 1
                    else:
                        failed_downloads += 1
                else:
                    print(f"{ORANGE}No suitable trailer found for {show['title']}{RESET}")
                    failed_downloads += 1
            
            print(f"\n{GREEN}Trailer processing summary:{RESET}")
            print(f"Successful: {successful_downloads}")
            print(f"Skipped (already exist): {skipped_existing}")
            print(f"Failed: {failed_downloads}")
        else:
            if not download_trailers:
                print(f"\n{ORANGE}Trailer downloading is disabled{RESET}")
            else:
                print(f"\n{ORANGE}No upcoming shows to download trailers for{RESET}")
				
        # ---- Create Kometa subfolder ----
        kometa_folder = Path("Kometa")
        kometa_folder.mkdir(exist_ok=True)
        
        # ---- Create YAML Files ----
        overlay_file = kometa_folder / "UTSK_TV_UPCOMING_SHOWS_OVERLAYS.yml"
        collection_file = kometa_folder / "UTSK_TV_UPCOMING_SHOWS_COLLECTION.yml"
        
        create_overlay_yaml(str(overlay_file), upcoming_shows, 
                           {"backdrop": config.get("backdrop_upcoming_shows", {}),
                            "text": config.get("text_upcoming_shows", {})})
        
        create_collection_yaml(str(collection_file), upcoming_shows, config)
        
        print(f"\n{GREEN}YAML files created successfully in Kometa folder{RESET}")

        # Calculate and display runtime
        end_time = datetime.now()
        runtime = end_time - start_time
        hours, remainder = divmod(runtime.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        runtime_formatted = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        
        print(f"Total runtime: {runtime_formatted}")

    except ConnectionError as e:
        print(f"{RED}Error: {str(e)}{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"{RED}Unexpected error: {str(e)}{RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()