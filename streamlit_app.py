import streamlit as st
import requests
import json
import http.client
import urllib.parse
import os
import io
from PIL import Image # For potential image manipulation if needed, st.image handles fetch

# --- Configuration ---
WATCHLIST_FILE = "watchlist.json"

# Attempt to load API keys from Streamlit secrets, fallback to placeholders
try:
    IMDB_SEARCH_API_KEY = st.secrets.get("api_keys", {}).get("imdb_search", "YOUR_RAPIDAPI_KEY")
    STREAMING_API_KEY = st.secrets.get("api_keys", {}).get("streaming", "YOUR_STREAMING_API_KEY")
except AttributeError: # Handle case where st.secrets is not available (local run without secrets file)
    IMDB_SEARCH_API_KEY = "YOUR_RAPIDAPI_KEY" # Replace if not using secrets
    STREAMING_API_KEY = "YOUR_STREAMING_API_KEY" # Replace if not using secrets & subscribing

IMDB_SEARCH_API_HOST = "imdb236.p.rapidapi.com"
STREAMING_API_HOST = "streaming-availability.p.rapidapi.com"

# --- Helper Functions ---

def load_watchlist():
    """Loads the watchlist from a JSON file."""
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
                # Use a dictionary with IMDb ID as key
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            st.error(f"Could not load watchlist file ({WATCHLIST_FILE}): {e}")
            return {}
    return {}

def save_watchlist(watchlist_data):
    """Saves the current watchlist to a JSON file."""
    try:
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(watchlist_data, f, indent=4)
    except IOError as e:
        st.error(f"Could not save watchlist file ({WATCHLIST_FILE}): {e}")

# --- API Call Functions ---

def search_imdb_autocomplete(query):
    """Searches IMDb using the autocomplete endpoint."""
    if not query:
        return None, "Please enter a search query."
    if IMDB_SEARCH_API_KEY == "YOUR_RAPIDAPI_KEY":
        return None, "IMDb Search API Key is not configured (check secrets or script)."

    results = None
    error_message = None
    conn = None
    try:
        conn = http.client.HTTPSConnection(IMDB_SEARCH_API_HOST)
        headers = {
            'x-rapidapi-key': IMDB_SEARCH_API_KEY,
            'x-rapidapi-host': IMDB_SEARCH_API_HOST
        }
        encoded_query = urllib.parse.quote(query)
        endpoint = f"/imdb/autocomplete?query={encoded_query}"

        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        status = res.status

        if 200 <= status < 300:
            decoded_data = data.decode("utf-8")
            results_raw = json.loads(decoded_data)
            if isinstance(results_raw, list):
                 # Filter out items without an ID, as they are less useful
                 results = [item for item in results_raw if item.get('id')]
            else:
                error_message = f"API Error: Unexpected response format (expected list).\nData: {decoded_data[:100]}..."
        else:
            error_message = f"API Error: {status} {res.reason}\n{data.decode('utf-8')[:100]}..."

    except http.client.HTTPException as e:
        error_message = f"Connection Error (Search): {e}"
    except json.JSONDecodeError as e:
        error_message = f"Data Error (Search): Failed to parse response. {e}"
    except Exception as e:
        error_message = f"Unexpected Error (Search): {e}"
    finally:
        if conn:
            conn.close()

    return results, error_message

# --- (Placeholder) Streaming Availability Fetch ---
def fetch_streaming_availability(imdb_id):
    """Fetches streaming info using the separate Streaming Availability API."""
    if not imdb_id:
        return None, "IMDb ID required for streaming lookup."
    if STREAMING_API_KEY == "YOUR_STREAMING_API_KEY":
        # Add explanation about needing the separate API
        info = ("Streaming info requires separate API subscription/key. "
                "Configure `secrets.toml` or script with key for "
                f"'{STREAMING_API_HOST}'. This app uses imdb236 for search, "
                "but needs a different API for where-to-watch data.")
        return info, None # Return info message, no actual error

    streaming_info_str = None
    error_message = None
    conn_stream = None
    try:
        conn_stream = http.client.HTTPSConnection(STREAMING_API_HOST)
        headers_stream = {
            'x-rapidapi-key': STREAMING_API_KEY,
            'x-rapidapi-host': STREAMING_API_HOST
        }
        # --- Endpoint Example - Check API Docs for correct path/params! ---
        # Adding `country=us` as an example parameter. VERIFY THIS.
        endpoint_stream = f"/shows/{imdb_id}?country=in"

        conn_stream.request("GET", endpoint_stream, headers=headers_stream)
        res_stream = conn_stream.getresponse()
        data_stream = res_stream.read()
        status_stream = res_stream.status

        if 200 <= status_stream < 300:
            decoded_stream_data = data_stream.decode("utf-8")
            stream_results = json.loads(decoded_stream_data)
            # --- !! PARSING LOGIC - HIGHLY DEPENDENT ON ACTUAL API RESPONSE !! ---
            options_text = "Not found or parsing failed."
            # Example Parsing (Needs Verification with actual API response)
            if isinstance(stream_results, dict):
                streaming_options_key = None
                if 'streamingOptions' in stream_results: # Direct key?
                        streaming_options_key = stream_results['streamingOptions']
                elif 'result' in stream_results and isinstance(stream_results['result'], dict) and 'streamingOptions' in stream_results['result']: # Nested under 'result'?
                        streaming_options_key = stream_results['result']['streamingOptions']

                if streaming_options_key and isinstance(streaming_options_key, dict):
                    # Focusing on 'us' options as per endpoint example
                    country_options = streaming_options_key.get('in', [])
                    if country_options:
                        services = set()
                        for option in country_options:
                            service_name = option.get('service', {}).get('id', 'Unknown')
                            option_type = option.get('type', 'N/A')
                            if option_type == 'subscription':
                                    services.add(f"{service_name.capitalize()}")
                            elif option_type in ['rent', 'buy']:
                                    services.add(f"{service_name.capitalize()} ({option_type})")
                            else:
                                    services.add(f"{service_name.capitalize()} ({option_type})")
                        options_text = ", ".join(sorted(list(services))) if services else "None found in US."
                    else:
                        options_text = "None found in India."
                else:
                        options_text = "Streaming data structure not recognized."

            streaming_info_str = f"Available in (India): {options_text}"
            # --- End Parsing Logic ---

        elif status_stream == 404:
                streaming_info_str = "Streaming info not found for this title (404)."
        else:
            try:
                error_body = data_stream.decode("utf-8")[:150]
            except: error_body = "(Could not decode error body)"
            error_message = f"Streaming API Error: {status_stream} {res_stream.reason}\n{error_body}"

    except http.client.HTTPException as e:
        error_message = f"Connection Error (Streaming): {e}"
    except json.JSONDecodeError as e:
        error_message = f"Data Error (Streaming): Failed to parse response. {e}"
    except Exception as e:
        error_message = f"Unexpected Error (Streaming): {e}"
    finally:
        if conn_stream:
            conn_stream.close()

    return streaming_info_str, error_message


# --- Initialize Session State ---
# Persists data across user interactions and script reruns
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = load_watchlist()
if 'search_results' not in st.session_state:
    st.session_state.search_results = None
if 'selected_movie_data' not in st.session_state:
    st.session_state.selected_movie_data = None
if 'streaming_info_msg' not in st.session_state: # Store message/error separately
    st.session_state.streaming_info_msg = None
if 'error_message' not in st.session_state: # General errors
    st.session_state.error_message = None
if 'info_message' not in st.session_state: # General info/success
     st.session_state.info_message = None


# --- Streamlit UI Layout ---

st.set_page_config(layout="wide", page_title="Movie Search")
st.title("🎬 Movie Search & Watchlist")

# Use columns for layout: Search/Details | Watchlist
main_col, watchlist_col = st.columns([3, 1]) # Main area wider

with main_col:
    # --- Search Area ---
    search_query = st.text_input("Enter movie title:", key="search_input", placeholder="e.g., The Dark Knight")
    search_button = st.button("Search", key="search_button")

    if search_button and search_query:
        # Clear previous state on new search
        st.session_state.selected_movie_data = None
        st.session_state.streaming_info_msg = None
        st.session_state.error_message = None
        st.session_state.info_message = None
        st.session_state.search_results = None # Clear previous results immediately

        with st.spinner(f"Searching for '{search_query}'..."):
            results, error = search_imdb_autocomplete(search_query)
            if error:
                st.session_state.error_message = error
            else:
                st.session_state.search_results = results
                if not results:
                    st.session_state.info_message = f"No results found for '{search_query}'."

    # --- Display Messages ---
    if st.session_state.error_message:
        st.error(st.session_state.error_message)
        # Don't clear immediately, let user see it until next action
    if st.session_state.info_message:
        st.info(st.session_state.info_message)
        # Don't clear immediately


    # --- Display Search Results OR Selected Movie Details ---
    st.markdown("---") # Separator

    # If a movie is selected, show details
    if st.session_state.selected_movie_data:
        movie = st.session_state.selected_movie_data
        imdb_id = movie.get('id', 'N/A')
        title = movie.get('primaryTitle', 'N/A')
        year = movie.get('startYear', 'N/A')
        rating = movie.get('averageRating', 'N/A')
        votes = movie.get('numVotes') # Get number for formatting
        genres = ", ".join(movie.get('genres', ['N/A']))
        description = movie.get('description', 'No description available.')
        image_url = movie.get('primaryImage')

        st.subheader("Movie Details")

        # --- Details Layout ---
        detail_col1, detail_col2 = st.columns([1, 3]) # Image column, Text column

        with detail_col1:
            if image_url:
                # Use width to control size; Streamlit handles aspect ratio
                st.image(image_url, caption=f"{title} Poster", width=200)
            else:
                st.caption("No Image Available")

        with detail_col2:
            st.subheader(f"{title} ({year})")
            st.caption(f"IMDb ID: {imdb_id}")
            if rating != 'N/A' and votes is not None:
                 st.write(f"**Rating:** {rating} ({votes:,} votes)") # Format votes
            else:
                 st.write("**Rating:** N/A")
            st.write(f"**Genres:** {genres}")

            # Add to Watchlist Button
            add_key = f"add_{imdb_id}"
            if st.button("Add to Watchlist", key=add_key):
                if imdb_id != 'N/A':
                    if imdb_id in st.session_state.watchlist:
                        st.toast(f"'{title}' is already in watchlist.", icon="ℹ️")
                    else:
                        st.session_state.watchlist[imdb_id] = {
                            'title': title, 'year': year, 'id': imdb_id, 'type': movie.get('type', '')
                        }
                        save_watchlist(st.session_state.watchlist)
                        st.toast(f"Added '{title}' to watchlist!", icon="✅")
                        # No rerun needed, watchlist display will update automatically
                else:
                    st.error("Cannot add movie without an IMDb ID.")

            # Button to go back to search results
            if st.button("Back to Search Results", key="back_to_search"):
                st.session_state.selected_movie_data = None
                st.session_state.streaming_info_msg = None
                st.session_state.error_message = None # Clear error when going back
                st.rerun()

        # Description below image/basic info
        st.markdown("**Description:**")
        st.write(description if description else "_No description available._")


        # --- Streaming Info Section ---
        st.markdown("---")
        st.subheader("Streaming Availability")
        if imdb_id != 'N/A':
            # Fetch only if not already fetched for this selected movie
            if st.session_state.streaming_info_msg is None:
                 with st.spinner("Fetching streaming info..."):
                     streaming_data, error = fetch_streaming_availability(imdb_id)
                     if error:
                         st.session_state.streaming_info_msg = f"⚠️ Error: {error}"
                     else:
                         st.session_state.streaming_info_msg = streaming_data # Store the info string or specific message

            # Display fetched info or error/info message
            if st.session_state.streaming_info_msg:
                 if st.session_state.streaming_info_msg.startswith("⚠️ Error:"):
                      st.warning(st.session_state.streaming_info_msg)
                 else:
                      st.info(st.session_state.streaming_info_msg)
            else:
                 st.caption("No streaming information fetched yet.")
        else:
            st.warning("Streaming info lookup requires IMDb ID.")


    # Otherwise, show search results (if any)
    elif st.session_state.search_results is not None:
        if not st.session_state.search_results:
            st.write("No results to display (matching the search or with valid IDs).")
        else:
            st.subheader(f"Search Results ({len(st.session_state.search_results)}):")
            # Display results more clearly
            for index, item in enumerate(st.session_state.search_results):
                res_title = item.get('primaryTitle', 'N/A')
                res_year = item.get('startYear', '')
                res_type = item.get('type', '')
                res_id = item.get('id', f"no_id_{index}") # Fallback key if ID somehow missing
                display_text = f"**{res_title}** ({res_year})" if res_year else f"**{res_title}**"
                display_text += f"  <small>[{res_type}]</small>" # Smaller type indicator

                res_col1, res_col2 = st.columns([4, 1])
                with res_col1:
                     st.markdown(display_text, unsafe_allow_html=True) # Allow small tag
                with res_col2:
                     # Use unique key for each details button
                     if st.button("Details", key=f"details_{res_id}"):
                         st.session_state.selected_movie_data = item
                         st.session_state.streaming_info_msg = None # Clear old streaming info
                         st.session_state.error_message = None # Clear old errors
                         st.rerun() # Rerun to show details view
                st.divider() # Add a visual separator between results


# --- Watchlist Column ---
with watchlist_col:
    st.header("My Watchlist")
    st.caption(f"Total items: {len(st.session_state.watchlist)}")
    st.markdown("---")

    if not st.session_state.watchlist:
        st.caption("Your watchlist is empty. Add movies from the details view.")
    else:
        # Sort watchlist items alphabetically by title for consistent display
        sorted_watchlist_items = sorted(st.session_state.watchlist.items(), key=lambda item: item[1].get('title', '').lower())

        for imdb_id, item_data in sorted_watchlist_items:
            wl_title = item_data.get('title', 'N/A')
            wl_year = item_data.get('year', '')
            wl_type = item_data.get('type', '')
            display_text = f"**{wl_title}** ({wl_year}) <small>[{wl_type}]</small>"

            wl_item_col1, wl_item_col2 = st.columns([3, 1])
            with wl_item_col1:
                st.markdown(display_text, unsafe_allow_html=True)
            with wl_item_col2:
                 # Unique key for remove button, use short imdb id part if possible
                 remove_key = f"remove_{imdb_id}"
                 if st.button("➖", key=remove_key, help=f"Remove '{wl_title}'"):
                     if imdb_id in st.session_state.watchlist:
                         del st.session_state.watchlist[imdb_id]
                         save_watchlist(st.session_state.watchlist)
                         st.toast(f"Removed '{wl_title}'.")
                         st.rerun() # Rerun to refresh the list display
            st.divider()


# Optional: Display session state for debugging
# st.divider()
# if st.checkbox("Show Debug Info (Session State)"):
#     st.json(st.session_state)