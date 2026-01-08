# 🎵 Spotify to Jellyfin Playlist Importer

Import your Spotify playlists directly into Jellyfin! This tool reads Spotify CSV exports and creates matching playlists in your Jellyfin library using fuzzy matching to find the best track matches.

> ⚠️ **Important**: This tool does **not** download any tracks from Spotify. It creates playlists in your Jellyfin server by searching for existing tracks that are already in your library.

## ✨ Features

- **Direct Import**: Creates playlists directly in Jellyfin (no M3U intermediate files)
- **Smart Matching**: Uses fuzzy matching (85% threshold) to find tracks even with slight naming variations
- **Duplicate Detection**: Skips tracks already in the playlist
- **Batch Processing**: Import a single CSV or an entire folder of playlists
- **Missing Track Report**: Generates a report of tracks that couldn't be matched

## 📋 Prerequisites

- Python 3.6+
- A running Jellyfin server
- Jellyfin API key
- Spotify playlist exports in CSV format

## 🚀 Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/amrit260/spotify_to_jellyfin.git
   cd spotify-to-jellyfin
   ```

2. **Create and activate a virtual environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # Or on Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure your environment**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your Jellyfin credentials:
   ```
   JELLYFIN_URL=http://your-jellyfin-server:8096
   JELLYFIN_API_KEY=your_api_key_here
   JELLYFIN_USER_ID=your_user_id_here
   ```

## ⚙️ Getting Your Jellyfin Credentials

### API Key

1. Go to Jellyfin Dashboard → API Keys
2. Click "+" to create a new API key
3. Give it a name (e.g., "Spotify Importer")
4. Copy the generated key

### User ID

1. Go to Jellyfin Dashboard → Users
2. Click on your user
3. The User ID is in the URL: `.../users/YOUR_USER_ID/...`

## 📦 Exporting Spotify Playlists

You can export your Spotify playlists to CSV using tools like:

- [Exportify](https://exportify.net/)
- [Spotify Playlist Exporter](https://github.com/watsonbox/exportify)

The CSV should contain columns like:

- `Track Name` or `name`
- `Artist Name(s)` or `Artist` or `artist`

## 🎮 Usage

Run the script:

```bash
python spotify_to_jellyfin.py
```

You'll be prompted to:

1. Choose single CSV or folder import
2. Enable/disable verbose output
3. Provide the file/folder path
4. (For single CSV) Enter the playlist name

### Example

```
🎵 Spotify to Jellyfin Direct Importer
========================================
Import (1) single CSV or (2) folder of CSVs? [1/2]: 2
Show verbose output? [y/N]: y
Enter folder path [./exports]: ./my_playlists
```

## 📊 Output

The tool provides:

- ✅ Number of tracks added
- ⏭️ Number of duplicates skipped
- ❌ Number of missing tracks
- 📝 A `_missing_tracks.txt` file with tracks that couldn't be matched

## 🔧 Configuration

You can adjust the fuzzy matching threshold in the script:

```python
FUZZY_THRESHOLD = 0.85  # 85% similarity required
```

Lower values = more matches but potentially less accurate
Higher values = fewer matches but more precise

## 📁 Project Structure

```
spotify-to-jellyfin/
├── spotify_to_jellyfin.py  # Main script
├── .env.example            # Example environment configuration
├── .gitignore              # Git ignore file
├── requirements.txt        # Python dependencies
├── LICENSE                 # MIT License
└── README.md               # This file
```

## 🤝 Contributing

Contributions are welcome! Feel free to:

- Report bugs
- Suggest features
- Submit pull requests

## ⚠️ Disclaimer

This tool do not come with any gurantee. Use at your own risk.
