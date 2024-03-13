from pip._internal import main as pipmain
import asyncio
import os
from datetime import datetime
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import yaml
import requests
import websockets


def install_and_import(package, import_name=None):
    try:
        if import_name:
            __import__(import_name)
        else:
            __import__(package)
    except ImportError:
        pipmain(['install', package])
        if import_name:
            __import__(import_name)
        else:
            __import__(package)

install_and_import('websockets')
install_and_import('spotipy')
install_and_import('pyyaml', 'yaml')

def get_time():
    return datetime.now().strftime("[%d/%m/%Y %H:%M:%S]:")

def load_config():
    file_path = os.path.join(os.getcwd(), "config.yml")
    with open(file_path, "r") as ymlfile:
        return yaml.safe_load(ymlfile)

cfg = load_config()

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=cfg["spotify"]["clientID"],
    client_secret=cfg["spotify"]["clientSecret"],
    redirect_uri=cfg["spotify"]["redirectURI"],
    scope=cfg["spotify"]["scope"],
    cache_path=cfg["spotify"]["cache"],
    open_browser=True))

test = sp.devices()
print(get_time(), "Connected to Spotify successfully!")

async def server(websocket, path):
    print(get_time(), 'Client connected!')
    try:
        async for message in websocket:
            process_message(message, websocket)
    except Exception as e:
        print(get_time(), "Error:", e)
    finally:
        print(get_time(), "Client disconnected")

async def process_message(message, websocket):
    command, *args = message.split(";")
    if command == 'current':
        await handle_current_playback(websocket)
    elif command == 'playlists':
        await send_playlists(websocket)

async def handle_current_playback(websocket):
    result = sp.current_playback()
    if result:
        artist_names = ', '.join(artist['name'] for artist in result['item']['artists'])
        track_name = result['item']['name']
        await websocket.send(f"!current{artist_names}\t{track_name}")
    else:
        await websocket.send("!currentNone")

async def send_playlists(websocket):
    playlists = sp.current_user_playlists()
    formatted_playlists = [f"{playlist['name']}\t{playlist['images'][0]['url'] if playlist['images'] else 'No Image'}" for playlist in playlists['items']]
    await websocket.send("!playlists" + "\t".join(formatted_playlists))

async def monitor_spotify_playback():
    last_status = None
    last_track = None
    while True:
        result = sp.current_playback()
        if result:
            is_playing = result['is_playing']
            current_status = 'Playing' if is_playing else 'Paused'
            artist_names = ', '.join(artist['name'] for artist in result['item']['artists'])
            track_name = result['item']['name']
            current_track = f"{artist_names} - {track_name}"
            canvas = f"https://spotify-canvas-api-weld.vercel.app/spotify?id={result['item']['uri']}"

            if current_status != last_status or current_track != last_track:
                url = f"{canvas}"
                response = requests.get(url)
                print(f"{get_time()} Status: {current_status}, Track: {current_track}, Canvas: {response.text}")
                last_status = current_status
                last_track = current_track
        else:
            if last_status is not None or last_track is not None:
                print(f"{get_time()} No playback found or Spotify is not active.")
                last_status = None
                last_track = None

async def main():
    server_task = websockets.serve(server, "localhost", 8765)
    monitor_task = monitor_spotify_playback()
    await asyncio.gather(server_task, monitor_task)

if __name__ == "__main__":
    asyncio.run(main())



