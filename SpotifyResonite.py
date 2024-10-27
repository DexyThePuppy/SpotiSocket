import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import yaml
import aiohttp
import websockets
from websockets.server import WebSocketServerProtocol
from bs4 import BeautifulSoup

# Color codes for terminal output
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m' + '\033[1m'  # Bold OKCYAN
    OKGREEN = '\033[92m' + '\033[1m'  # Bold OKGREEN
    WARNING = '\033[93m' + '\033[1m'  # Bold WARNING
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Configure logging with color
logging.basicConfig(
    level=logging.INFO,
    format=f'{bcolors.OKBLUE}%(asctime)s{bcolors.ENDC} - '
           f'{bcolors.OKGREEN}%(levelname)s{bcolors.ENDC} - '
           f'{bcolors.ENDC}%(message)s',
    datefmt='[%d/%m/%Y %H:%M:%S]'
)
logger = logging.getLogger(__name__)

class SpotifyWebSocketServer:
    def __init__(self, config_path: str = "config.yml"):
        self.config = self._load_config(config_path)
        self.spotify: Optional[spotipy.Spotify] = None
        self.last_playback_state: Dict[str, Any] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.websocket_port = 8765
        self.search_results = None

    @staticmethod
    def _load_config(config_path: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, "r") as file:
                return yaml.safe_load(file)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    async def initialize(self) -> None:
        """Initialize Spotify client and aiohttp session."""
        try:
            auth_manager = SpotifyOAuth(
                client_id=self.config["spotify"]["clientID"],
                client_secret=self.config["spotify"]["clientSecret"],
                redirect_uri="http://localhost:1337/callback",
                scope=self.config["spotify"]["scope"],
                cache_path=self.config["spotify"]["cache"],
                open_browser=True
            )

            self.spotify = spotipy.Spotify(auth_manager=auth_manager)
            self.session = aiohttp.ClientSession()

            # Test connection with retry logic
            retry_count = 3
            for attempt in range(retry_count):
                try:
                    self.spotify.devices()
                    logger.info(f"{bcolors.OKGREEN}Connected to Spotify successfully!{bcolors.ENDC}")
                    break
                except Exception as e:
                    if attempt == retry_count - 1:
                        raise
                    logger.warning(f"Connection attempt {attempt + 1} failed: {e}. Retrying...")
                    await asyncio.sleep(0.3)

        except Exception as e:
            logger.error(f"Failed to initialize Spotify client: {e}")
            raise

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self.session:
            await self.session.close()

    async def handle_websocket(self, websocket: WebSocketServerProtocol) -> None:
        """Handle WebSocket connections."""
        logger.info(f'{bcolors.OKGREEN}Client connected!{bcolors.ENDC}')
        try:
            # Send initial state
            await self.send_initial_state(websocket)
            async for message in websocket:
                await self.process_message(message, websocket)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"{bcolors.OKGREEN}Client disconnected normally{bcolors.ENDC}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            logger.info(f"{bcolors.OKGREEN}Client disconnected{bcolors.ENDC}")

    async def send_initial_state(self, websocket: WebSocketServerProtocol) -> None:
        """Send initial state to newly connected client."""
        try:
            result = self.spotify.current_playback()
            if result:
                tempstatus = '!init'
                tempstatus += f"{str(result['shuffle_state'])}\t"
                
                repeat_state = result['repeat_state']
                repeat_value = {'off': '0', 'context': '1', 'track': '2'}.get(repeat_state, '0')
                tempstatus += f"{repeat_value}\t"
                
                tempstatus += f"{str(result['is_playing'])}\t\t\t\t\t"
                await websocket.send(tempstatus)
        except Exception as e:
            logger.error(f"Error sending initial state: {e}")
            await websocket.send("!initError")

    async def process_message(self, message: str, websocket: WebSocketServerProtocol) -> None:
        """Process incoming WebSocket messages."""
        try:
            parts = message.split(";")
            command = parts[0]
            query = parts[1] if len(parts) > 1 else ""
            extra1 = parts[2] if len(parts) > 2 else ""
            extra2 = parts[3] if len(parts) > 3 else ""

            handlers = {
                'current': self.handle_current_playback,
                'playlists': self.send_playlists,
                'next': self.handle_next_track,
                'previous': self.handle_previous_track,
                'pause': self.handle_pause,
                'resume': self.handle_resume,
                'volume': lambda ws: self.handle_volume(ws, extra1),
                'shuffle': lambda ws: self.handle_shuffle(ws, True),
                'shuffle_off': lambda ws: self.handle_shuffle(ws, False),
                'repeat': lambda ws: self.handle_repeat(ws, 'context'),
                'repeat_off': lambda ws: self.handle_repeat(ws, 'off'),
                'repeat_one': lambda ws: self.handle_repeat(ws, 'track'),
                'search': lambda ws: self.handle_search(ws, query, extra2),
                'addqueue': lambda ws: self.handle_add_queue(ws, extra1, extra2),
                'playplaylist': lambda ws: self.handle_play_playlist(ws, extra1),
                'seek': lambda ws: self.handle_seek(ws, extra1)
            }

            handler = handlers.get(command)
            if handler:
                await handler(websocket)
            else:
                logger.warning(f"Unknown command: {command}")
                await websocket.send("!statusUnknown Command")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await websocket.send(f"!error{str(e)}")

    async def handle_current_playback(self, websocket: WebSocketServerProtocol) -> None:
        """Handle current playback request with detailed information."""
        try:
            result = self.spotify.current_playback()
            if result and result.get('item'):
                artist_names = ', '.join(artist['name'] for artist in result['item']['artists'])
                album = result['item']['album']['name']
                album_img = result['item']['album']['images'][1]['url'] if result['item']['album']['images'] else "https://developer.spotify.com/assets/branding-guidelines/icon3@2x.png"
                track_name = result['item']['name']
                song_progress = result['progress_ms']
                song_duration = result['item']['duration_ms']
                is_playing = result['is_playing']
                volume = result['device']['volume_percent']
                canvas_url = await self.get_spotify_track_download_url(result['item']['uri'])

                await websocket.send(
                    f"!current{artist_names}\t{album}\t{album_img}\t{track_name}\t"
                    f"{volume}\t{song_progress}\t{song_duration}\t{str(is_playing)}\t{canvas_url}"
                )
            else:
                await websocket.send("!currentNone")
        except Exception as e:
            logger.error(f"Error handling current playback: {e}")
            await websocket.send("!statusFatal error in fetching current info")

    async def send_playlists(self, websocket: WebSocketServerProtocol) -> None:
        """Send playlists to client."""
        try:
            playlists = self.spotify.current_user_playlists()
            formatted_playlists = []
            for playlist in playlists['items']:
                name = playlist['name']
                icon = playlist['images'][0]['url'] if playlist['images'] else "https://developer.spotify.com/assets/branding-guidelines/icon3@2x.png"
                formatted_playlists.append(f"{name}\b{icon}")
            
            output = "!playlists" + "\n".join(formatted_playlists) + "\t\t\t\t\t\t\t"
            await websocket.send(output)
        except Exception as e:
            logger.error(f"Error sending playlists: {e}")
            await websocket.send("!playlistsError")

    async def handle_next_track(self, websocket: WebSocketServerProtocol) -> None:
        """Handle next track command."""
        try:
            self.spotify.next_track()
            await websocket.send('!statusPlaying next track')
        except Exception as e:
            logger.error(f"Error playing next track: {e}")
            await websocket.send('!statusError playing next track')

    async def handle_previous_track(self, websocket: WebSocketServerProtocol) -> None:
        """Handle previous track command."""
        try:
            self.spotify.previous_track()
            await websocket.send('!statusPlaying previous track')
        except Exception as e:
            logger.error(f"Error playing previous track: {e}")
            await websocket.send('!statusError playing previous track')

    async def handle_pause(self, websocket: WebSocketServerProtocol) -> None:
        """Handle pause command."""
        try:
            self.spotify.pause_playback()
            await websocket.send('!statusPaused')
        except Exception as e:
            logger.error(f"Error pausing playback: {e}")
            await websocket.send('!statusFailed to pause')

    async def handle_resume(self, websocket: WebSocketServerProtocol) -> None:
        """Handle resume command."""
        try:
            self.spotify.start_playback()
            await websocket.send('!statusPlaying')
        except Exception as e:
            logger.error(f"Error resuming playback: {e}")
            await websocket.send('!statusFailed to resume')

    async def handle_volume(self, websocket: WebSocketServerProtocol, volume: str) -> None:
        """Handle volume change command."""
        try:
            volume_int = int(volume)
            self.spotify.volume(volume_percent=volume_int)
            await websocket.send(f'!statusVolume set to: {volume}')
        except spotipy.exceptions.SpotifyException:
            await websocket.send('!statusError adjusting volume, it might not be allowed on your selected device')
        except ValueError:
            await websocket.send('!statusInvalid volume value')

    async def handle_shuffle(self, websocket: WebSocketServerProtocol, state: bool) -> None:
        """Handle shuffle command."""
        try:
            self.spotify.shuffle(state=state)
            await websocket.send(f'!statusShuffle {"enabled" if state else "disabled"}')
        except Exception as e:
            logger.error(f"Error setting shuffle: {e}")
            await websocket.send('!statusError setting shuffle state')

    async def handle_repeat(self, websocket: WebSocketServerProtocol, state: str) -> None:
        """Handle repeat command."""
        try:
            self.spotify.repeat(state=state)
            await websocket.send(f'!statusRepeat mode set to: {state}')
        except Exception as e:
            logger.error(f"Error setting repeat: {e}")
            await websocket.send('!statusError setting repeat state')

    async def handle_search(self, websocket: WebSocketServerProtocol, query: str, extra2: str) -> None:
        """Handle search command."""
        try:
            if not query:
                return
            
            cache_num = 25
            self.search_results = self.spotify.search(query, limit=cache_num)
            output = "!search"

            if extra2 == "nameartistcover":
                for track in self.search_results['tracks']['items']:
                    track_name = track['name']
                    artist = ', '.join(artist['name'] for artist in track['artists'])
                    cover = track['album']['images'][1]['url'] if track['album']['images'] else "https://developer.spotify.com/assets/branding-guidelines/icon3@2x.png"
                    output += f"{track_name}\b{artist}\b{cover}\n"
                output += "\t\t\t\t\t\t\t"

            output = output[:-2]
            await websocket.send(output)
        except Exception as e:
            logger.error(f"Error performing search: {e}")
            await websocket.send('!statusError performing search')

    async def handle_add_queue(self, websocket: WebSocketServerProtocol, index: str, source: str) -> None:
        """Handle add to queue command."""
        try:
            if source == 'fromsearch' and self.search_results:
                track_id = self.search_results['tracks']['items'][int(index)]['id']
                self.spotify.add_to_queue(track_id)
                await websocket.send('!statusTrack added to queue')
            else:
                await websocket.send('!statusNo search results available')
        except Exception as e:
            logger.error(f"Error adding to queue: {e}")
            await websocket.send('!statusError adding track to queue')

    async def handle_play_playlist(self, websocket: WebSocketServerProtocol, playlist_index: str) -> None:
        """Handle play playlist command."""
        try:
            playlists = self.spotify.current_user_playlists()
            playlist_uri = playlists['items'][int(playlist_index)]['uri']
            self.spotify.start_playback(context_uri=playlist_uri)
            await websocket.send('!statusPlaying playlist')
        except Exception as e:
            logger.error(f"Error playing playlist: {e}")
            await websocket.send('!statusError playing playlist')

    async def handle_seek(self, websocket: WebSocketServerProtocol, position: str) -> None:
        """Handle seek command."""
        try:
            position_ms = int(position)
            self.spotify.seek_track(position_ms)
            await websocket.send(f'!statusSeeked to position: {position_ms}ms')
        except Exception as e:
            logger.error(f"Error seeking track: {e}")
            await websocket.send('!statusError seeking track')

    async def monitor_spotify_playback(self) -> None:
        """Monitor Spotify playback changes with enhanced logging."""
        while True:
            try:
                result = self.spotify.current_playback()
                if result and result.get('item'):
                    current_state = {
                        'is_playing': result['is_playing'],
                        'track_id': result['item']['id'],
                        'uri': result['item']['uri']
                    }

                    if current_state != self.last_playback_state:
                        artist_names = ', '.join(artist['name'] for artist in result['item']['artists'])
                        track_name = result['item']['name']
                        status = 'Playing' if current_state['is_playing'] else 'Paused'
                        
                        # Fetch canvas URL asynchronously
                        canvas_url = await self.get_spotify_track_download_url(current_state['uri'])
                        
                        track_url = f"https://open.spotify.com/track/{result['item']['id']}"

                        # Use ANSI escape codes for clickable links without showing the URL
                        # For "Status", we simulate a click by sending a command to the application
                        logger.info(
                            f"{bcolors.OKCYAN}Status:{bcolors.ENDC} \033]8;;spotify:toggle_playback\033\\{status}\033]8;;\033\\, "
                            f"{bcolors.OKCYAN}Track:{bcolors.ENDC} \033]8;;spotify:{track_url}\033\\{bcolors.BOLD}{track_name}\033]8;;\033\\{bcolors.ENDC}, "
                            f"{bcolors.OKCYAN}Canvas:{bcolors.ENDC} \033]8;;{canvas_url}\033\\{canvas_url}\033]8;;\033\\" 
                        )
                        self.last_playback_state = current_state
                elif self.last_playback_state:
                    logger.info(f"{bcolors.OKCYAN}No playback found or Spotify is not active.{bcolors.ENDC}")
                    self.last_playback_state = {}
                
                await asyncio.sleep(1)
            except Exception as e:
                # Log error with a general message
                logger.error(f"Error monitoring playback: {e}")
                await asyncio.sleep(5)

    async def get_spotify_track_download_url(self, track_uri):
        """Retrieves the download URL for a Spotify track from canvasdownloader.com."""
        url = f"https://www.canvasdownloader.com/canvas?link=https://open.spotify.com/track/{track_uri.split(':')[-1]}"
        try:
            response = await self.session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(await response.text(), 'html.parser')
            download_button = soup.find('button', {'class': 'download-button'})
            if download_button:
                download_link = download_button['onclick'].split("'")[1]
                return download_link
            else:
                return None
        except Exception as e:
            # Handle the error gracefully, returning None
            return None

    async def start(self) -> None:
        """Start the WebSocket server and monitoring."""
        await self.initialize()
        try:
            server = await websockets.serve(self.handle_websocket, "localhost", self.websocket_port)
            logger.info(f"WebSocket server started on port {self.websocket_port}")

            await asyncio.gather(
                server.wait_closed(),
                self.monitor_spotify_playback()
            )
        finally:
            await self.cleanup()

async def main():
    while True:
        try:
            server = SpotifyWebSocketServer()
            await server.start()
        except Exception as e:
            logger.error(f"Server error: {e}")
            logger.info(f"{bcolors.WARNING}Restarting server in 5 seconds...{bcolors.ENDC}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info(f"{bcolors.OKGREEN}Server shutdown requested{bcolors.ENDC}")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
