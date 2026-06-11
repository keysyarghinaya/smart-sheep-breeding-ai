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

if __name__ == "__main__":
    app.run(host="172.20.10.2", port=5000, debug=True)

# if __name__ == "__main__":
#     app.run(debug=True)