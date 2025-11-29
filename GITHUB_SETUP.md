# GitHub Setup Guide

Your repository is ready to push to GitHub! ✅

## What's Protected

The following files containing your API keys are **gitignored** and will NOT be uploaded:
- `.env` (backend API key)
- `config.js` (frontend API key)

Instead, example files are included for others to set up their own keys:
- `.env.example`
- `config.example.js`

## Push to GitHub

### 1. Create a new repository on GitHub
1. Go to [github.com/new](https://github.com/new)
2. Name it `etaGuessr` (or whatever you prefer)
3. **Do NOT** initialize with README (we already have one)
4. Click "Create repository"

### 2. Push your code

Copy the commands GitHub shows you, or run:

```bash
git remote add origin https://github.com/YOUR_USERNAME/etaGuessr.git
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

## Enable GitHub Pages (Frontend Only)

⚠️ **Important:** GitHub Pages can only host the frontend (HTML/CSS/JS). You'll need to deploy the backend separately.

### To enable GitHub Pages:
1. Go to your repository on GitHub
2. Click "Settings" → "Pages"
3. Under "Source", select "main" branch and "/" (root)
4. Click "Save"
5. Your frontend will be live at: `https://YOUR_USERNAME.github.io/etaGuessr/`

### Deploy the Backend

Since GitHub Pages can't run Python, you need to deploy the backend elsewhere. See [DEPLOYMENT.md](DEPLOYMENT.md) for options:

**Recommended:** Use Heroku (free tier)
```bash
# Install Heroku CLI
brew install heroku/brew/heroku

# Login and deploy
heroku login
heroku create eta-guesser-backend
heroku config:set GOOGLE_MAPS_API_KEY=your_key_here
git push heroku main
```

Then update `index.html` line 453 to use your Heroku URL:
```javascript
const response = await fetch('https://eta-guesser-backend.herokuapp.com/random-destination');
```

## Security Checklist

✅ API keys are in `.gitignore` and won't be committed
✅ Example files provided for setup instructions
✅ README.md explains how to configure keys
✅ DEPLOYMENT.md explains hosting options

## Next Steps

1. **Push to GitHub** (see commands above)
2. **Deploy backend** to Heroku/Vercel/Railway (see [DEPLOYMENT.md](DEPLOYMENT.md))
3. **Update frontend URL** in `index.html` to point to deployed backend
4. **Enable GitHub Pages** for frontend (optional, since you need backend URL first)

## Verify Your Setup

Before pushing, verify API keys are hidden:
```bash
# This should NOT show .env or config.js
git status

# This should NOT include your actual API keys
git diff --cached
```

## Need Help?

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment guides for:
- Heroku
- Vercel
- Railway
- PythonAnywhere
- VPS

---

🎉 Your code is ready to share on GitHub!
