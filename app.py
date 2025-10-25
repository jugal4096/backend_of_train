from flask import Flask, request, redirect, url_for, session, send_file
import os
from functools import wraps
from jalna_to_awb import TRAINS_JALNA_TO_AURANGABAD
from awb_to_jalna import TRAINS_AURANGABAD_TO_JALNA

app = Flask(__name__)
app.secret_key = "your_super_secret_key"
PASSWORD = "4096"

MID_STATION = ["Dinagaoun", "Badnapur", "Karmad", "Chikhalthana"]
TRAIN_TYPE_PRIORITY = {"VB": 6, "JShtb": 5, "SF": 4, "Exp": 3, "DEMU": 2, "Pass": 1}

# ---------------- Serve Background ----------------
@app.route("/pics.jpg")
def serve_pic():
    return send_file("pics.jpg", mimetype="image/jpeg")

# ---------------- Cache Prevention ----------------
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "-1"
    return response

# ---------------- Utility ----------------
def hhmm_to_minutes(t):
    h, m = map(int, t.split(":"))
    return h * 60 + m

def minutes_to_hhmm(m):
    m = m % (24 * 60)
    h = m // 60
    mm = m % 60
    return f"{h:02d}:{mm:02d}"

def add_minutes_to_hhmm(time_str, add_min):
    return minutes_to_hhmm(hhmm_to_minutes(time_str) + add_min)

def train_priority(train):
    return TRAIN_TYPE_PRIORITY.get(train["type"], 0)

def find_conflicts(selected_train, opposing_trains, window_before=60):
    selected_time = hhmm_to_minutes(selected_train["dep"])
    results = []
    for opp in opposing_trains:
        opp_time = hhmm_to_minutes(opp["dep"])
        if selected_time - window_before <= opp_time <= selected_time + window_before:
            results.append(opp)
    return results

def simulate_conflicts(selected_train, opposing_trains):
    conflicts = find_conflicts(selected_train, opposing_trains)
    if not conflicts:
        return [], f"{selected_train['name']} runs clear with no conflicts. It will arrive on time.", selected_train["arr"]

    selected_score = train_priority(selected_train)
    halt_duration = 10
    station_index = 0

    higher_priority_trains = []
    for opp in conflicts:
        opp_score = train_priority(opp)
        if opp_score >= selected_score:
            higher_priority_trains.append(opp)

    if higher_priority_trains:
        station = MID_STATION[station_index]
        new_arrival = add_minutes_to_hhmm(selected_train["arr"], halt_duration)
        opp_names = ", ".join([t["name"] for t in higher_priority_trains])
        decision = (
            f"<b>{selected_train['name']}</b> will HALT at <b>{station}</b> for {opp_names} "
            f"(<b>{halt_duration} min delay</b>)."
        )
        return [], decision, new_arrival
    else:
        return [], f"<b>{selected_train['name']}</b> gets clear passage. On-time arrival.", selected_train["arr"]

# ---------------- Authentication ----------------
def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("password_page"))
        return func(*args, **kwargs)
    return wrapper

# ---------------- Login Page ----------------
@app.route("/", methods=["GET", "POST"])
def password_page():
    if session.get("authenticated"):
        return redirect(url_for("index_page"))

    if request.method == "POST":
        if request.form.get("password") == PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("index_page"))
        return "<script>alert('Incorrect Password'); window.location='/'</script>"

    return """
    <html>
    <head><title>Login</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background: url('/pics.jpg') no-repeat center center fixed;
            background-size: cover;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            font-family: 'Poppins', sans-serif;
        }
        .login-box {
            background: rgba(0, 0, 0, 0.5);
            border-radius: 20px;
            padding: 50px;
            text-align: center;
            color: #fff;
            box-shadow: 0 0 30px rgba(0,0,0,0.5);
            backdrop-filter: blur(10px);
        }
        input[type=password] {
            padding: 12px;
            width: 80%;
            border-radius: 10px;
            border: none;
            outline: none;
            margin-bottom: 20px;
            background: rgba(255,255,255,0.2);
            color: #fff;
            text-align: center;
        }
        input[type=submit] {
            padding: 12px 25px;
            border: none;
            border-radius: 8px;
            background: linear-gradient(135deg, #ff6600, #ff9900);
            color: white;
            font-weight: bold;
            cursor: pointer;
            transition: 0.3s;
        }
        input[type=submit]:hover {
            transform: scale(1.05);
            box-shadow: 0 0 15px #ff9900;
        }
        h1 { margin-bottom: 25px; color: #ffd700; }
    </style></head>
    <body>
        <div class="login-box">
            <h1>🚦 AI Railway Access</h1>
            <form method="POST">
                <input type="password" name="password" placeholder="Enter Access Password" required><br>
                <input type="submit" value="Login">
            </form>
        </div>
    </body></html>
    """

# ---------------- Direction Selection ----------------
@app.route("/index", methods=["GET", "POST"])
@login_required
def index_page():
    if request.method == "POST":
        direction = request.form["direction"]
        return redirect(url_for("show_trains", direction=direction))

    return """
    <html><head><title>Direction</title>
    <style>
        body {
            background: linear-gradient(135deg, #001F3F, #004080);
            color: white;
            text-align: center;
            font-family: 'Poppins', sans-serif;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .container {
            background: rgba(255,255,255,0.1);
            padding: 40px 60px;
            border-radius: 20px;
            box-shadow: 0 0 25px rgba(0,0,0,0.4);
            backdrop-filter: blur(8px);
        }
        input[type=radio] { margin: 10px; transform: scale(1.2); }
        input[type=submit] {
            margin-top: 20px; padding: 12px 25px;
            border-radius: 10px; border: none;
            background: linear-gradient(135deg, #ff6600, #ff9900);
            color: white; font-weight: bold; cursor: pointer;
        }
        input[type=submit]:hover { box-shadow: 0 0 10px #ff9900; }
        h1 { color: #00bfff; }
    </style></head>
    <body>
        <div class="container">
            <h1>🚆 Railway Delay Predictor</h1>
            <form method="POST">
                <label><input type="radio" name="direction" value="jalna_to_aurangabad" required> Jalna → Aurangabad</label><br>
                <label><input type="radio" name="direction" value="aurangabad_to_jalna" required> Aurangabad → Jalna</label><br>
                <input type="submit" value="Continue">
            </form>
        </div>
    </body></html>
    """

# ---------------- Train List ----------------
@app.route("/trains/<direction>")
@login_required
def show_trains(direction):
    trains = TRAINS_JALNA_TO_AURANGABAD if direction == "jalna_to_aurangabad" else TRAINS_AURANGABAD_TO_JALNA
    html = f"""
    <html><head><title>Trains</title>
    <style>
        body {{
            background: linear-gradient(135deg, #001F3F, #003366);
            color: white; text-align: center; font-family: 'Poppins', sans-serif;
        }}
        h1 {{ color: #00bfff; margin: 20px 0; }}
        ul {{ list-style: none; padding: 0; }}
        li {{
            background: rgba(255,255,255,0.1);
            width: 60%; margin: 10px auto; padding: 15px;
            border-radius: 10px; transition: 0.3s;
        }}
        li:hover {{ transform: translateY(-5px); box-shadow: 0 0 10px #ff9900; }}
        a {{ color: #ffd700; text-decoration: none; }}
        .back {{ color: #fff; background: linear-gradient(135deg, #ff6600, #ff9900);
            padding: 10px 20px; border-radius: 8px; text-decoration: none; }}
    </style></head><body>
    <h1>🚉 {direction.replace('_',' ').title()}</h1><ul>
    """
    for t in trains:
        html += f"<li><b>{t['name']}</b> ({t['number']})<br>Type: {t['type']}<br>Dep: {t['dep']} | Arr: {t['arr']}<br><a href='/conflict/{direction}/{t['number']}'>Predict Delay</a></li>"
    html += "</ul><a href='/index' class='back'>⬅ Back</a></body></html>"
    return html

# ---------------- Prediction ----------------
@app.route("/conflict/<direction>/<train_number>")
@login_required
def conflict(direction, train_number):
    selected = None
    opposing = []
    if direction == "jalna_to_aurangabad":
        selected = next((t for t in TRAINS_JALNA_TO_AURANGABAD if t["number"] == train_number), None)
        opposing = TRAINS_AURANGABAD_TO_JALNA
    else:
        selected = next((t for t in TRAINS_AURANGABAD_TO_JALNA if t["number"] == train_number), None)
        opposing = TRAINS_JALNA_TO_AURANGABAD

    if not selected:
        return "Train not found", 404

    halted_trains, decision, new_arrival = simulate_conflicts(selected, opposing)

    return f"""
    <html><head><title>Prediction</title>
    <style>
        body {{
            background: linear-gradient(135deg, #001F3F, #003366);
            color: white; font-family: 'Poppins', sans-serif; text-align: center;
            padding: 50px;
        }}
        .info {{
            background: rgba(255,255,255,0.1);
            padding: 20px; border-radius: 10px; margin-bottom: 20px;
        }}
        .info strong {{ color: #ffd700; }}
        .decision {{
            background: rgba(0,255,0,0.1); border-left: 4px solid #32cd32;
            padding: 15px; border-radius: 10px; margin-top: 15px;
        }}
        a {{
            display: inline-block; margin: 20px 10px;
            padding: 10px 20px; border-radius: 10px;
            background: linear-gradient(135deg, #ff6600, #ff9900);
            color: white; text-decoration: none;
        }}
        a:hover {{ box-shadow: 0 0 10px #ff9900; }}
    </style></head>
    <body>
        <h1>🚆 Prediction for {selected['name']} ({selected['number']})</h1>
        <div class='info'>
            <p><strong>Train Type:</strong> {selected['type']}</p>
            <p><strong>Scheduled Departure:</strong> {selected['dep']} | <strong>Scheduled Arrival:</strong> {selected['arr']}</p>
        </div>
        <div class='decision'>
            <p>{decision}</p>
            <p><strong>Predicted Arrival:</strong> {new_arrival}</p>
        </div>
        <a href='/trains/{direction}'>⬅ Back</a>
        <a href='/index'>🏠 Home</a>
    </body></html>
    """

@app.route("/logout")
def logout():
    session.pop("authenticated", None)
    return redirect(url_for("password_page"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
