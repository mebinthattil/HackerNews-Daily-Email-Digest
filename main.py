from flask import Flask, request, render_template
from src import tools
import os
from datetime import datetime

app = Flask(__name__)

ARCHIVES_DIR = os.path.join(os.path.dirname(__file__), 'static', 'archives')


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


if __name__ == "__main__":
	app.run(debug=True)

