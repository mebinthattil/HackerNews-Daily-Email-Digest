from flask import Flask, request, render_template
from src import tools

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
	return render_template("index.html")


@app.route("/subscribe", methods=["POST"])
def subscribe():
	email = request.form.get("email")
	success, msg = tools.validate_email(email)
	if success:
		return render_template("confirm.html")
	else:
		return render_template("error.html", error=msg), 400


if __name__ == "__main__":
	app.run(debug=True)

