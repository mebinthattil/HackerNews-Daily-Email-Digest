from flask import Flask, request, render_template, abort
from src import tools
import os
import hmac
import hashlib
import subprocess
from datetime import datetime

app = Flask(__name__)

ARCHIVES_DIR = os.path.join(os.path.dirname(__file__), 'static', 'archives')
WEBHOOK_SECRET = os.environ.get('GITHUB_WEBHOOK_SECRET', '').encode()
LOG_FILE = os.path.join(os.path.dirname(__file__), 'webhook.log')


def write_log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")


def verify_github_signature(req) -> bool:
    """Verify the GitHub webhook signature."""
    signature = req.headers.get('X-Hub-Signature-256')
    if not signature:
        return False
    sha_name, signature = signature.split('=')
    if sha_name != 'sha256':
        return False
    mac = hmac.new(WEBHOOK_SECRET, msg=req.data, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)


@app.route("/", methods=["GET"])
def index():
	return render_template("index.html")


@app.route("/subscribe", methods=["POST"])
def subscribe():
    email = request.form.get("email", "")

    subscriber_added, result_msg = tools.add_subscriber(email)
    if subscriber_added:
        return render_template("confirm.html", message=result_msg)

    return render_template("error.html", error=result_msg), 400


@app.route("/archives", methods=["GET"])
def archives():
    archive_files = []
    
    if os.path.exists(ARCHIVES_DIR):
        for filename in os.listdir(ARCHIVES_DIR):
            if filename.endswith('.html'):
                # Parse date from filename (DD-MM-YYYY.html)
                try:
                    date_str = filename.replace('.html', '')
                    date_obj = datetime.strptime(date_str, "%d-%m-%Y")
                    archive_files.append({
                        'filename': filename,
                        'date': date_obj,
                        'display_date': date_obj.strftime("%B %d, %Y"),
                        'url': f"/static/archives/{filename}"
                    })
                except:
                    continue
    
    archive_files.sort(key=lambda x: x['date'], reverse=True) # sort, latest first
    
    return render_template("archives.html", archives=archive_files)


@app.route("/webhook", methods=["POST"])
def github_webhook():
    """GitHub webhook endpoint for auto-deployment."""
    if not verify_github_signature(request):
        write_log(f"WARNING: Signature verification failed from {request.remote_addr}")
        abort(403)
    
    data = request.json
    if data.get('ref') != 'refs/heads/main':
        write_log(f"Ignored push to branch: {data.get('ref')}")
        return 'Ignored: Not main branch.', 200
    
    write_log("\n" + "=" * 40)
    write_log("MAIN BRANCH PUSH - Starting Repository Update")
    write_log("=" * 40)
    
    repo_path = os.path.dirname(os.path.abspath(__file__))
    write_log(f"Repository path: {repo_path}")
    
    git_path = "/usr/bin/git"
    sudo_path = "/usr/bin/sudo"
    systemctl_path = "/usr/bin/systemctl"
    
    # Fetch latest changes
    try:
        write_log("Step 1: Fetching latest changes from origin...")
        fetch_result = subprocess.run(
            [git_path, "fetch", "origin"],
            cwd=repo_path, capture_output=True, text=True, check=True, timeout=60
        )
        write_log(f"  -> Fetch successful")
    except subprocess.TimeoutExpired:
        write_log("ERROR: Fetch timed out after 60 seconds")
        return 'Git fetch timed out', 500
    except subprocess.CalledProcessError as e:
        write_log(f"ERROR: Fetch failed: {e.stderr.strip()}")
        return 'Git fetch failed', 500
    
    # Hard reset to origin/main
    try:
        write_log("Step 2: Hard resetting to origin/main...")
        reset_result = subprocess.run(
            [git_path, "reset", "--hard", "origin/main"],
            cwd=repo_path, capture_output=True, text=True, check=True, timeout=30
        )
        write_log(f"  -> Reset successful: {reset_result.stdout.strip()}")
    except subprocess.TimeoutExpired:
        write_log("ERROR: Reset timed out after 30 seconds")
        return 'Git reset timed out', 500
    except subprocess.CalledProcessError as e:
        write_log(f"ERROR: Reset failed: {e.stderr.strip()}")
        return 'Git reset failed', 500
    
    # UV sync
    try:
        write_log("Step 3: Running uv sync...")
        sync_result = subprocess.run(
            ["/home/mebin/.local/bin/uv", "sync"],
            cwd=repo_path, capture_output=True, text=True, check=True
        )
        write_log(f"  -> UV sync successful")
    except subprocess.CalledProcessError as e:
        write_log(f"ERROR: UV sync failed: {e.stderr.strip()}")
        return 'UV sync failed', 500
    
    # Restart the gunicorn service
    try:
        write_log("Step 4: Restarting hackernews-digest service...")
        restart_command = f"{sudo_path} {systemctl_path} restart hackernews-digest"
        restart_result = os.system(restart_command)
        
        if restart_result == 0:
            write_log("  -> Service restarted successfully")
        else:
            write_log(f"WARNING: Service restart failed (exit code: {restart_result})")
            write_log("Deployment partially complete - service restart failed\n")
            return 'Repository updated, but service restart failed', 200
    except Exception as e:
        write_log(f"ERROR: Service restart error: {str(e)}")
        write_log("Deployment partially complete - service restart failed\n")
        return 'Repository updated, but service restart failed', 200
    
    write_log("Deployment completed successfully!\n")
    return 'Success: Repository updated and service restarted.', 200


if __name__ == "__main__":
	app.run(debug=True)
