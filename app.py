from flask import Flask, render_template

app = Flask(__name__)

@app.route("/search")
def search():
    return render_template("search.html")

@app.route("/camera")
def camera():
    return render_template("camera.html")

@app.route("/result")
def result():
    return render_template("result.html")

if __name__ == "__main__":
    app.run(debug=True)