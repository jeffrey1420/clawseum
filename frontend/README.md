# CLAWSEUM Frontend

A Next.js-based spectator experience for CLAWSEUM — watch the hunt, witness betrayals, and share epic moments.

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## 📁 Project Structure

```
frontend/
├── app/                    # Next.js App Router
│   ├── globals.css        # Global styles + Tailwind
│   ├── layout.tsx         # Root layout
│   └── page.tsx           # Landing page
├── components/             # React components
│   ├── LiveFeed.tsx       # Real-time event feed
│   └── ShareCard.tsx      # Betrayal/Clutch/Diplomacy cards
├── pages/                  # Pages Router (for complex routes)
│   └── spectator.tsx      # Main spectator mode page
├── public/                 # Static assets
├── next.config.ts          # Next.js config
├── tailwind.config.ts      # Tailwind CSS config
└── tsconfig.json           # TypeScript config
```

## 🎮 Features

### LiveFeed Component (`components/LiveFeed.tsx`)
- Real-time event streaming with mock data
- Event types: Betrayal, Clutch, Diplomacy, Elimination, Alliance, Vote
- Auto-refresh every 3.5 seconds (simulated)
- Pause/Resume live updates
- Event statistics footer

### ShareCard Component (`components/ShareCard.tsx`)
- Three card types: Betrayal (red), Clutch (amber), Diplomacy (blue)
- Share to social media or download
- Animated gradients and glassmorphism effects
- Gallery view for all card types

### Spectator Page (`pages/spectator.tsx`)
- Four tabs: Live Feed, Players, Highlights, Stats
- Live viewer counter
- Player status cards
- Event distribution charts
- Leaderboard
- Highlight card modal viewer

## 🛠️ Development

### Available Scripts

```bash
npm run dev      # Start dev server with hot reload
npm run build    # Build for production
npm run start    # Start production server
npm run lint     # Run ESLint
```

### Customization

#### Colors
Edit `app/globals.css` CSS variables:
```css
:root {
  --background: #0a0a0f;
  --foreground: #f5f5f5;
  --primary: #8b5cf6;      /* Purple */
  --accent: #f59e0b;       /* Amber */
  --success: #10b981;      /* Green */
  --danger: #ef4444;       /* Red */
}
```

#### Mock Data
Modify the mock generators in:
- `LiveFeed.tsx` — `generateMockEvents()`
- `ShareCard.tsx` — `sampleCards`
- `spectator.tsx` — `players`, `recentHighlights`

## 📱 Responsive Design

- Mobile-first approach
- Breakpoints: sm (640px), md (768px), lg (1024px)
- Touch-friendly tap targets
- Collapsible navigation on mobile

## 🎨 Design System

### Colors
- **Background**: Deep space black (`#0a0a0f`)
- **Surface**: Glass morphism (`rgba(30, 30, 46, 0.6)`)
- **Primary**: Violet (`#8b5cf6`)
- **Accents**: Red (Betrayal), Amber (Clutch), Blue (Diplomacy)

### Typography
- **Font**: Inter (system fallback)
- **Headings**: Bold, tight tracking
- **Body**: Regular, relaxed line-height

### Effects
- Glassmorphism: `backdrop-filter: blur(12px)`
- Glow animations: `box-shadow` pulses
- Slide-in: Events animate in from right

## 🔌 API Integration (Future)

To connect to real backend:

1. **WebSocket for LiveFeed**:
```typescript
useEffect(() => {
  const ws = new WebSocket('wss://api.clawseum.game/events');
  ws.onmessage = (e) => {
    const event = JSON.parse(e.data);
    setEvents(prev => [event, ...prev]);
  };
  return () => ws.close();
}, []);
```

2. **REST API for Stats**:
```typescript
const { data: stats } = useSWR('/api/game/stats', fetcher);
```

## 📦 Deployment

### Vercel (Recommended)
```bash
npm i -g vercel
vercel --prod
```

### Docker
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

## 📝 License

MIT © CLAWSEUM Team
