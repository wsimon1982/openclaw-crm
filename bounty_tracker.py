import os
import requests

def track_bounties():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN not set!")
        return
    headers = {"Authorization": f"token {token}"}
    repos = ["wsimon1982/rustchain-prometheus-exporter", "wsimon1982/neo-agent"]
    
    for repo in repos:
        issues = requests.get(f"https://api.github.com/repos/{repo}/issues", headers=headers).json()
        print(f"Bounties in {repo}: {len(issues)}")

if __name__ == "__main__":
    track_bounties()
