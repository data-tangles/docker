from flask import Flask, redirect, request, session, url_for, render_template
import requests
import os

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your_secret_key_here")

# GitHub App Credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_USER_URL = "https://api.github.com/user"
GITHUB_API_REPOS_URL = "https://api.github.com/user/repos"
GITHUB_API_ORGS_URL = "https://api.github.com/user/orgs"


def exchange_code_for_token(code):
    """Exchange GitHub OAuth code for an access token."""
    params = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
    }
    headers = {"Accept": "application/json"}
    response = requests.post(GITHUB_ACCESS_TOKEN_URL, data=params, headers=headers)
    return response.json()


def get_user_info(access_token):
    """Fetch user info from GitHub API."""
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    response = requests.get(GITHUB_API_USER_URL, headers=headers)
    return response.json()


def get_workflow_runs(repo_name, access_token):
    """Fetch latest workflow runs for a given repository."""
    url = f"https://api.github.com/repos/{repo_name}/actions/runs?per_page=5"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json().get("workflow_runs", [])
    return []


@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/github-login")
def github_login():
    return redirect(f"https://github.com/login/oauth/authorize?client_id={CLIENT_ID}")

@app.route("/callback")
def callback():
    """Handles GitHub OAuth callback and gets user access token."""
    code = request.args.get("code")
    token_data = exchange_code_for_token(code)

    if "access_token" in token_data:
        session["user_token"] = token_data["access_token"]
        return redirect(url_for("workflows"))

    return f"Authorization failed: {token_data}", 403


@app.route("/workflows")
def workflows():
    """Fetches workflow runs from user's repositories and organizations."""
    if "user_token" not in session:
        return redirect(url_for("index"))

    headers = {
        "Authorization": f"Bearer {session['user_token']}",
        "Accept": "application/vnd.github+json",
    }

    # Fetch user info to separate personal repos from org repos
    user_response = requests.get(GITHUB_API_USER_URL, headers=headers)
    if user_response.status_code != 200:
        return f"Failed to fetch user info: {user_response.json()}", 500
    user_info = user_response.json()
    user_login = user_info["login"]

    # Fetch all repos user has access to
    response = requests.get(GITHUB_API_REPOS_URL, headers=headers)
    all_repos = response.json() if response.status_code == 200 else []

    # Separate personal and organization repositories
    personal_repos = [repo for repo in all_repos if repo["owner"]["login"] == user_login]
    org_repos = [repo for repo in all_repos if repo["owner"]["login"] != user_login]

    # Fetch workflow runs
    workflow_data = {
        "personal_repos": {repo["full_name"]: get_workflow_runs(repo["full_name"], session["user_token"]) for repo in personal_repos},
        "org_repos": {repo["full_name"]: get_workflow_runs(repo["full_name"], session["user_token"]) for repo in org_repos},
    }

    return render_template("workflows.html", workflow_data=workflow_data)

@app.route("/logout")
def logout():
    """Logs the user out by clearing the session."""
    session.clear()
    return redirect(url_for("login_page"))

if __name__ == "__main__":
    app.run()
