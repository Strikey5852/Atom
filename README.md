# Atom

Atom is a personal Discord bot for my own server. This repository is public for reference and experimentation, but the bot itself is intended for private use only.

## Features

- Action GIF commands for fun server interactions
- Question of the Day posting and scheduling
- Hourly cat image posts
- Sticky message reposting for important announcements
- Dice rolling commands for casual use
- Personal bot logic and settings stored in GitHub Gists

## Local setup

### Requirements

- Python 3.8+
- A Discord bot token
- A GitHub account with a personal access token that has `gist` access

### Installation

```bash
git clone <repository-url>
cd Atom
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a local `.env` file from the example template:

```bash
cp .env.example .env
```

Then fill in your own values:

```env
TOKEN=your_discord_bot_token_here
GITHUB_TOKEN=your_github_token_here
GIST_ID=
GIST_AUTO_CREATE=true
```

### Notes

- Keep the real `.env` file local only. It is ignored by Git.
- The project includes `.env.example` so the required variables are easy to copy.
- If `GIST_ID` is empty, the bot will create a private gist automatically when it starts.

## Database

Atom stores its bot settings and guild data in a private GitHub Gist. This keeps configuration portable while avoiding a traditional database service.

The bot will create a private gist on first run when `GIST_AUTO_CREATE=true`. You can also point to an existing gist by setting `GIST_ID`.

## Running the bot

```bash
python main.py
```