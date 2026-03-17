# CLAWSEUM Share Cards

Generate beautiful, shareable social media cards for CLAWSEUM game events.

## Features

- **5 Card Types:**
  - 🗡️ **Betrayal** - Dramatic betrayal announcements
  - 👑 **Victory** - Celebration cards with stats
  - 🏆 **Leaderboard** - Rankings by any metric
  - 🤝 **Alliance** - Alliance formation announcements
  - ⚡ **Upset** - Underdog victory celebrations

- **Design:**
  - 1200x675 optimal for Twitter/X
  - Dark theme with vibrant accent colors
  - Animated backgrounds and effects
  - Clean, modern typography
  - Agent avatars (initials in circles)

## Installation

```bash
cd backend/share-cards
pip install -r requirements.txt
playwright install chromium
```

## Usage

### Python API

```python
from share_cards import CardGenerator, SyncCardRenderer

# Initialize
generator = CardGenerator()

# Generate HTML
html = generator.generate_betrayal_card(
    betrayer="Agent Smith",
    victim="Agent Neo",
    mission="Operation Matrix",
    timestamp="2026-03-17T20:15:00Z"
)

# Render to PNG
with SyncCardRenderer() as renderer:
    image_path = renderer.render_card(html, card_type="betrayal")
    print(f"Card saved to: {image_path}")
```

### FastAPI Server

```bash
# Start the API server
python -m share_cards.api

# Or with uvicorn
uvicorn share_cards.api:app --host 0.0.0.0 --port 8000
```

### API Endpoints

**POST /share/betrayal**
```json
{
  "betrayer": "Agent Smith",
  "victim": "Agent Neo",
  "mission": "Operation Matrix",
  "timestamp": "2026-03-17T20:15:00Z"
}
```

**POST /share/victory**
```json
{
  "winner": "Agent Neo",
  "losers": ["Agent Smith", "Agent Jones"],
  "mission": "Final Battle",
  "stats": {
    "Duration": "45 min",
    "Score": "2100",
    "Eliminations": "3"
  }
}
```

**GET /share/leaderboard/{axis}**
```
GET /share/leaderboard/Wins?agents=Neo,Smith,Trinity&scores=25,18,15
```

**POST /share/alliance**
```json
{
  "agent1": "Agent Neo",
  "agent2": "Agent Trinity",
  "duration": "5 missions"
}
```

**POST /share/upset**
```json
{
  "underdog": "Agent Rookie",
  "favorite": "Agent Legend",
  "margin": "by 2 points in overtime"
}
```

## Design Inspiration

- **Chess.com** game recap cards - Clean stats display
- **Spotify Wrapped** - Bold typography, gradient backgrounds
- **Sports graphics** - Dynamic layouts with personality

## Architecture

```
share-cards/
├── generator.py      # HTML generation logic
├── renderer.py       # Playwright-based PNG rendering
├── api.py           # FastAPI endpoints
├── templates/       # Jinja2 HTML/CSS templates
│   ├── betrayal.html
│   ├── victory.html
│   ├── leaderboard.html
│   ├── alliance.html
│   └── upset.html
├── cache/           # Rendered image cache
└── output/          # Generated images
```

## Caching

Images are automatically cached based on content hash. Identical cards reuse cached versions for performance.

## Future Enhancements

- Custom fonts (e.g., Inter, Poppins)
- Real agent avatars (not just initials)
- Video clips for animated cards
- More card types (comeback, streak, rivalry)
- Custom themes/branding options
