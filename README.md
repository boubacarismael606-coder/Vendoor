# Vendoor

Vendoor is a Flask-based campus marketplace web app built with SQLite and simple user authentication.

## Local setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   python app.py
   ```
4. Open the app in your browser at `http://127.0.0.1:5000`.

## Deployment

To make Vendoor public, host it on a cloud platform and point your domain to the service.

### Recommended host: Render

Render is the best choice for this Flask app because it supports Python services directly and is easy to connect to GitHub.

### What is already ready

- `requirements.txt` for dependencies
- `Procfile` for process startup
- `runtime.txt` for Python version
- `render.yaml` for Render service configuration

### Deploy on Render

1. Create a GitHub repository and push this project.
2. Create a Render account at `https://render.com`.
3. In Render, choose "New +" → "Web Service".
4. Connect your GitHub account and select the repo.
5. Set the build command to:
   ```bash
   pip install -r requirements.txt
   ```
6. Set the start command to:
   ```bash
   python app.py
   ```
7. Deploy the service.

Render will give you a public URL once deployment succeeds.

### Domain setup on Render

1. Register a domain such as `vendoor.com`.
2. In Render, open your service settings and add the custom domain.
3. Configure the DNS records as Render instructs.
4. Render will automatically provision HTTPS.

### If you want a test deployment now

If you already have a GitHub account, the fastest path is:
- create a GitHub repo for this project
- push the files
- connect the repo in Render

If you want, I can give you the exact Git commands to run next, or I can guide you through the GitHub repo creation step by step.

## Notes

- The app currently uses SQLite (`instance/vendoor.db`). For a production-ready deployment, consider using a hosted database service such as PostgreSQL.
- If you want a temporary public URL while developing locally, use a tunneling service like ngrok.

## Next step

If you want, I can help you deploy this app to a specific platform such as Railway or Render and configure the domain routing too.
