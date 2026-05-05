# Atom Discord Bot

Atom is a Discord bot built with discord.py, currently under development with more features on the way.

## Features
- Action Commands — Fun interactive commands with GIFs (powered by nekos.best)
- Question of the Day System — Automatically post daily discussion questions
- Hourly Cat Images — Adorable cat pictures delivered every hour
- Sticky Messages — Keep important info visible by automatically reposting it when chat moves
- Dice Roller — Roll dice in NdM format (e.g. 2d6, 1d20+3, or 2d6+1d8-2) for games or random fun
- Use Anywhere — Add Atom to servers or use it directly as a user app
- More Features Coming Soon

## Invite Atom
- Add Atom to your server as a bot:  
[Invite as Bot](https://discord.com/oauth2/authorize?client_id=1379696768765132872&permissions=8&integration_type=0&scope=applications.commands+bot)

- Add Atom as a user app (use anywhere):  
[Invite as User App](https://discord.com/oauth2/authorize?client_id=1379696768765132872&integration_type=1&scope=applications.commands)

## Setup

### Prerequisites
- Python 3.8+
- A Discord bot token
- A GitHub account (for GitHub Gist database)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Atom
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with the following variables:

```env
# Discord Bot Token (required)
TOKEN=your_discord_bot_token_here

# GitHub Token with gist scope (required)
# Create a personal access token at: https://github.com/settings/tokens
# Make sure to select the "gist" scope
GITHUB_TOKEN=your_github_token_here

# GitHub Gist ID (optional - will be auto-created if not set)
# If you want to use an existing gist, put its ID here
# Otherwise, leave it blank or set GIST_AUTO_CREATE=true
GIST_ID=

# Auto-create gist if it doesn't exist (default: true)
GIST_AUTO_CREATE=true
```

### GitHub Token Setup

1. Go to [GitHub Personal Access Tokens](https://github.com/settings/tokens)
2. Click "Generate new token" (or "Generate new token (classic)")
3. Give it a descriptive name (e.g., "Atom Discord Bot")
4. Select the **gist** scope
5. Click "Generate token" and copy the token
6. Add it to your `.env` file as `GITHUB_TOKEN`

### Running the Bot

```bash
python main.py
```

## Database

Atom uses GitHub Gists as its database backend. This provides:
- **Cloud Storage** — Your data is stored in your GitHub account
- **Version History** — All changes are tracked by GitHub
- **Easy Backup** — Data is automatically backed up to GitHub
- **Portability** — Access your bot data from anywhere

The bot will automatically create a private gist on first run if `GIST_AUTO_CREATE=true`. You can also manually create a gist and set its ID in the `GIST_ID` environment variable, or point to an existing gist.

### Data Files

The bot stores the following data files in the gist:
- `cats.json` — Cat channel settings per guild
- `qotd.json` — Question of the Day data (questions, channels, settings)
- `sticky.json` — Sticky message configurations
- `trap.json` — Trap channel settings

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TOKEN` | Yes | Discord bot token |
| `GITHUB_TOKEN` | Yes | GitHub personal access token with gist scope |
| `GIST_ID` | No | ID of an existing gist (auto-created if not set) |
| `GIST_AUTO_CREATE` | No | Auto-create gist if it doesn't exist (default: true) |