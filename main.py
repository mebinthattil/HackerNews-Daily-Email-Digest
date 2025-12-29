from flask import Flask, request, render_template
from src import tools

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
	return render_template("index.html")


@app.route("/subscribe", methods=["POST"])
def subscribe():
    email = request.form.get("email")
    subscriber_added, err_msg = tools.add_subscriber(email)

    if subscriber_added:
        return render_template("confirm.html")
    else:
        return render_template("error.html", error=err_msg), 400



if __name__ == "__main__":
	app.run(debug=True)

