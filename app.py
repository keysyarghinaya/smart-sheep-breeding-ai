from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/history")
def history():
    return render_template("history.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/camera")
def camera():
    return render_template("camera.html")

@app.route("/popup-test")
def popup_test():
    return render_template("popup_test.html")

@app.route("/loading")
def loading():
    return render_template("loading.html")

@app.route("/error-limit")
def error_limit():
    return render_template("error_limit.html")

@app.route("/error-general")
def error_general():
    return render_template("error_general.html")

@app.errorhandler(404)
def page_not_found(e):
    return render_template("not_found.html"),404

if __name__ == "__main__":
    app.run(debug=True)