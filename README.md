# ShoulderCoach

**Live:** [shoulder-coach-1.vercel.app](https://shoulder-coach-1.vercel.app)

A basketball decision assistant and shooting form analyzer built on NBA historical data.

---

## What it does

**In-game decisions** — Answer questions like "should I shoot this three?" or "should I drive or pass?" using stats from 160,000+ NBA play records. Each answer comes with sample size, confidence context, and a short coaching note from GPT-4o.

**Shot Form Analyzer** — Upload a short shooting clip (phone video works). The app runs MediaPipe Pose on each frame to extract body landmarks, measures 5 biomechanical metrics (elbow angle, knee bend, wrist follow-through, shoulder level, body tilt), and returns a coaching note alongside an annotated video with skeleton overlay, angle arcs, and phase banners.

---

## Stack

- **Backend:** FastAPI, SQLite, MediaPipe Pose, OpenCV, ffmpeg, nba_api, GPT-4o
- **Frontend:** Next.js 16 (App Router), TypeScript
- **Deploy:** Railway (backend), Vercel (frontend)

---

## Running locally

**Backend**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app
```

**Frontend**
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

The decision engines use a pre-seeded SQLite database (`data/shouldercoach_deploy.db`). To rebuild it from scratch with full NBA data (takes 1-2 hours due to API rate limits):
```bash
cd backend
python -m app.data.seed
```

---

## Decision engines

| Engine | What it answers |
|---|---|
| Shot selection | Should I take this shot given location and defender distance? |
| Drive vs pass | Is driving or passing the better play here? |
| Pick and roll | How often does this play work in this situation? |
| Fastbreak | Should we push in transition or set up? |
| Foul trouble | How should minutes change based on foul count? |
| Clutch time | Who are the best closers in these situations? |
| Lineup optimizer | Which 5-man unit fits this matchup? |
| Defensive assignment | Who should guard who? |
