# Deployment Guide

## Important: GitHub Pages Limitation

**GitHub Pages only hosts static files (HTML, CSS, JavaScript).** It cannot run the Python Flask backend required for this application.

You have several deployment options:

---

## Option 1: Frontend on GitHub Pages + Backend Elsewhere (Recommended)

### Frontend (GitHub Pages)
1. Push your code to GitHub
2. Enable GitHub Pages in repository settings
3. Set source to `main` branch, `/` (root)

### Backend Options:

#### A. **Heroku** (Free tier available)
```bash
# Install Heroku CLI
brew install heroku/brew/heroku

# Login and create app
heroku login
heroku create your-app-name

# Add environment variable
heroku config:set GOOGLE_MAPS_API_KEY=your_key_here

# Deploy
git push heroku main
```

Then update `index.html` line 453:
```javascript
const response = await fetch('https://your-app-name.herokuapp.com/random-destination');
```

#### B. **Railway** (Easy deployment)
1. Go to [railway.app](https://railway.app)
2. Connect your GitHub repository
3. Add environment variable: `GOOGLE_MAPS_API_KEY`
4. Railway automatically detects Flask and deploys
5. Update frontend URL to Railway URL

#### C. **PythonAnywhere** (Free tier)
1. Create account at [pythonanywhere.com](https://www.pythonanywhere.com)
2. Upload your Flask app
3. Configure web app with WSGI
4. Add API key to environment
5. Update frontend URL

---

## Option 2: Full Stack on Cloud Platform

### Vercel (Recommended)
Supports both static frontend and serverless Python backend.

1. Install Vercel CLI:
```bash
npm install -g vercel
```

2. Create `vercel.json`:
```json
{
  "builds": [
    { "src": "app.py", "use": "@vercel/python" },
    { "src": "index.html", "use": "@vercel/static" }
  ],
  "routes": [
    { "src": "/random-destination", "dest": "app.py" },
    { "src": "/(.*)", "dest": "index.html" }
  ],
  "env": {
    "GOOGLE_MAPS_API_KEY": "@google-maps-api-key"
  }
}
```

3. Deploy:
```bash
vercel --prod
```

4. Add secret:
```bash
vercel secrets add google-maps-api-key your_key_here
```

---

## Option 3: Full Stack on Your Own Server

### VPS (DigitalOcean, AWS, etc.)

1. Set up a VPS with Ubuntu
2. Install Python, Nginx, and Gunicorn:
```bash
sudo apt update
sudo apt install python3-pip nginx
pip3 install gunicorn
```

3. Clone your repository
4. Install dependencies:
```bash
pip3 install -r requirements.txt
```

5. Configure environment:
```bash
echo "GOOGLE_MAPS_API_KEY=your_key_here" > .env
```

6. Run with Gunicorn:
```bash
gunicorn -w 4 -b 127.0.0.1:5001 app:app
```

7. Configure Nginx as reverse proxy

---

## Current Setup (Local Development)

This is what you're using now:
- Frontend: `python3 -m http.server 8000`
- Backend: `python3 app.py` (Flask on port 5001)
- Works great for development but requires both servers running

---

## Quick Deployment Comparison

| Platform | Frontend | Backend | Free Tier | Difficulty |
|----------|----------|---------|-----------|------------|
| GitHub Pages + Heroku | ✅ | ✅ | ✅ | Medium |
| Vercel | ✅ | ✅ | ✅ | Easy |
| Railway | ✅ | ✅ | ✅ | Easy |
| PythonAnywhere | ✅ | ✅ | ✅ | Medium |
| Own VPS | ✅ | ✅ | ❌ | Hard |

---

## Next Steps

1. **Choose a deployment option** from above
2. **Hide your API key** (already done with .env and config.js)
3. **Initialize git** (see below)
4. **Deploy**

### Initialize Git Repository

```bash
cd /Users/json/etaGuessr
git init
git add .
git commit -m "Initial commit: ETA Guesser game with traffic/transit overlays"
```

### Create GitHub Repository

```bash
# Create new repo on GitHub, then:
git remote add origin https://github.com/jasonliu-json/etaGuessr.git
git branch -M main
git push -u origin main
```

### Important Files

- `.gitignore` - Prevents committing sensitive files
- `.env.example` - Template for backend API key
- `config.example.js` - Template for frontend API key
- `.env` - Your actual backend API key (IGNORED by git)
- `config.js` - Your actual frontend API key (IGNORED by git)

---

## Security Notes

1. ✅ API keys are now in `.env` and `config.js` (both gitignored)
2. ✅ Example files provided for others to set up their own keys
3. ⚠️ **Never commit `.env` or `config.js` files**
4. ⚠️ Consider restricting your API key to specific domains in Google Cloud Console
