# SpotifySocket 🎧

Websocket code for Resonite spotify controller

This is the server code for the Spotify controller. The code will allow you to control your Spotify client from inside of Resonite. (Premium Spotify account required).

**FORK NOTICE**: This fork includes updates to utilize the Spotify Canvas API for displaying the currently playing song's canvas art in Resonite. 🖼️

## ✨ Features:

- **Seamless Control:** See song information, including the album icon, and enjoy effortless control over playback with play, pause, skip, and previous track functionality. ⏯️
- **Smooth Seeking:** Navigate through your song with precision using the intuitive progress bar. 🏄‍♂️
- **Automatic Syncing:** Enjoy uninterrupted listening with automatic syncing to your Spotify client on startup and during playback. 🔄
- **Collaborative Listening:** Share the musical experience! You and your friends can use the player, with options to manage control access.  🎉
- **Playlist Power:** Dive into your music library and play from your public and private playlists (liked songs not supported). 🎶
- **Stream Together:** Elevate the experience by transforming the controller into a shared Spotify player! Stream your audio with friends for a truly connected listening session.  🎤
- **Canvas Art Integration:** Immerse yourself in the visual world of music with the display of the currently playing song's Canvas art in Resonite.  🎨

## 🚀 Getting Started:

### Step 0: Python Installation 🐍

This tool is powered by Python. If you don't have it installed, head over to [https://www.python.org/](https://www.python.org/) and download the latest stable version. **Make sure to click the tickbox to add Python to PATH!**

### Step 1: Spotify Configuration 🔑

1. Visit the Spotify Developer Dashboard: [https://developer.spotify.com/dashboard/login](https://developer.spotify.com/dashboard/login)
2. **Create an App:** Provide a name and description (choose something identifiable). 
3. **Edit Settings:** Go to 'Edit settings', find 'redirect URL', and enter 'http://localhost:1337'.
4. **Retrieve Credentials:** Click "show client secret" and copy the client ID, client secret, and redirect URL into the `config.yml` file.

### Step 2: Resonite Setup 🌐

1. **Find the Folder:** Locate the SpotifySocket folder in Resonite (link provided below).
2. **Spawn and Connect:** Spawn the folder and click the connect button. Grant permissions to connect to your local server (one-time setup).

Folder Link: `resrec:///U-1NWSXyNbyjY/R-E9A41D51155F6745E36D03AD17F617A3ED8DE6E3FD6589339AECEBCBAFEB4BA3`

### Step 3: Optional Streaming Setup 🎧

Transform the controller into a shared Spotify player! To do this, you'll need a way to stream your audio with low latency (e.g., VoiceMeeter). Once configured, spawn an audio stream in Resonite and drop it into the player. 

## 💡  Tips & Troubleshooting:

- **Active Device Required:**  The Spotify API needs an active device. Leaving music paused for extended periods might cause the server to disconnect. Simply restart the server if this happens.
- **Button Responsiveness:**  If the player doesn't seem to react to button presses, try clicking again. 

Let the music move you! If you have any questions or encounter errors, feel free to PM me in-game or reach out on Discord at Kodufan#7558.  🎶
