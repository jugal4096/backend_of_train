from flask import Flask, request, redirect, url_for, session, send_file
import os
from jalna_to_awb import TRAINS_JALNA_TO_AURANGABAD
from awb_to_jalna import TRAINS_AURANGABAD_TO_JALNA
from functools import wraps

app = Flask(__name__)
app.secret_key = "your_super_secret_key"  # for sessions
PASSWORD = "4096"  # set your password here

MID_STATION = ["Dinagaoun", "Badnapur", "Karmad", "Chikhalthana"]
TRAIN_TYPE_PRIORITY = {"VB": 6, "JShtb": 5, "SF": 4, "Exp": 3, "DEMU": 2, "Pass": 1}

# ------------------ IMAGE ROUTE ------------------
@app.route("/pic.jpg")
def serve_pic():
    """Serve your local pic.jpg without using static folder"""
    return send_file("pics.jpg", mimetype="image/jpeg")

# ------------------ CACHE PREVENTION ------------------
@app.after_request
def add_header(response):
    """Prevent browser caching to enforce session check"""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "-1"
    return response

# ------------------ UTILITY FUNCTIONS ------------------
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
            f"{selected_train['name']} will HALT at {station} for {opp_names} "
            f"({halt_duration} min delay). New expected arrival: {new_arrival}."
        )
        return [], decision, new_arrival
    else:
        return [], f"{selected_train['name']} gets clear passage with no halts. On-time arrival.", selected_train["arr"]

# ------------------ AUTH DECORATOR ------------------
def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "authenticated" not in session or not session["authenticated"]:
            return redirect(url_for("password_page"))
        return func(*args, **kwargs)
    return wrapper

# ------------------ ROUTES ------------------
@app.route("/", methods=["GET", "POST"])
def password_page():
    if session.get("authenticated"):
        return redirect(url_for("index_page"))

    if request.method == "POST":
        user_pass = request.form.get("password")
        if user_pass == PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("index_page"))
        else:
            return """
            <html><body style='text-align:center; font-family:Poppins,Arial; background:#001F3F; color:white;'>
            <h2 style='margin-top:50px;'>❌ Incorrect password!</h2>
            <a href='/' style='color:#ff6600; text-decoration:none;'>Try Again</a>
            </body></html>
            """

    return """
    <html>
    <head>
        <title>Login</title>
        <style>
            body {
                margin: 0;
                padding: 0;
                height: 100vh;
                background: linear-gradient(135deg, #001F3F, #003366);
                font-family: 'Poppins', sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                overflow: hidden;
            }
            .login-box {
                background: rgba(255, 255, 255, 0.1);
                padding: 50px;
                border-radius: 20px;
                text-align: center;
                color: white;
                box-shadow: 0 0 25px rgba(0,0,0,0.5);
                backdrop-filter: blur(8px);
                animation: fadeIn 1.2s ease-in-out;
            }
            input[type="password"] {
                padding: 12px;
                width: 80%;
                border-radius: 8px;
                border: none;
                outline: none;
                margin-bottom: 20px;
                background: rgba(255,255,255,0.2);
                color: white;
                text-align: center;
                transition: 0.3s;
            }
            input[type="password"]:focus {
                background: rgba(255,255,255,0.3);
            }
            input[type="submit"] {
                padding: 12px 25px;
                border: none;
                border-radius: 8px;
                background: linear-gradient(135deg, #ff6600, #ff9900);
                color: white;
                font-weight: bold;
                cursor: pointer;
                transition: transform 0.2s ease, box-shadow 0.2s ease;
            }
            input[type="submit"]:hover {
                transform: scale(1.05);
                box-shadow: 0 0 15px #ff9900;
            }
            h1 {
                margin-bottom: 25px;
                animation: slideDown 1s ease;
            }
            @keyframes fadeIn { from {opacity:0;} to {opacity:1;} }
            @keyframes slideDown { from {opacity:0; transform:translateY(-20px);} to {opacity:1; transform:translateY(0);} }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h1>🔒 Secure Access</h1>
            <form method="POST">
                <input type="password" name="password" placeholder="Enter Password" required><br>
                <input type="submit" value="Login">
            </form>
        </div>
    </body>
    </html>
    """

@app.route("/index", methods=["GET", "POST"])
@login_required
def index_page():
    if request.method == "POST":
        direction = request.form["direction"]
        return redirect(url_for("show_trains", direction=direction))

    return """
    <html>
    <head>
        <title>Railway Delay Predictor</title>
        <style>
            body {
                font-family: 'Poppins', sans-serif;
                background: linear-gradient(135deg, #003366, #001F3F);
                color: white;
                text-align: center;
                margin: 0;
                height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            .container {
                background: rgba(255,255,255,0.1);
                padding: 40px 60px;
                border-radius: 20px;
                box-shadow: 0 0 20px rgba(0,0,0,0.4);
                backdrop-filter: blur(8px);
            }
            h1 { margin-bottom: 25px; color: #ffcc66; }
            input[type="radio"] {
                margin: 10px;
                transform: scale(1.2);
            }
            label {
                font-size: 18px;
            }
            input[type="submit"] {
                margin-top: 25px;
                padding: 12px 30px;
                border-radius: 10px;
                border: none;
                background: linear-gradient(135deg, #ff6600, #ff9900);
                color: white;
                font-weight: bold;
                cursor: pointer;
                transition: transform 0.3s ease, box-shadow 0.3s ease;
            }
            input[type="submit"]:hover {
                transform: translateY(-3px);
                box-shadow: 0 0 15px #ff9900;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚆 Railway Delay Predictor</h1>
            <form method="POST">
                <label>Select direction:</label><br><br>
                <input type="radio" name="direction" value="jalna_to_aurangabad" required> Jalna → Aurangabad<br>
                <input type="radio" name="direction" value="aurangabad_to_jalna" required> Aurangabad → Jalna<br><br>
                <input type="submit" value="Show Trains">
            </form>
        </div>
    </body>
    </html>
    """

@app.route("/trains/<direction>")
@login_required
def show_trains(direction):
    trains = TRAINS_JALNA_TO_AURANGABAD if direction == "jalna_to_aurangabad" else TRAINS_AURANGABAD_TO_JALNA
    html = f"""
    <html><head><title>Trains</title>
    <style>
        body {{
            font-family: 'Poppins', sans-serif;
            background: linear-gradient(135deg, #001F3F, #003366);
            color: white;
            text-align: center;
            margin: 0;
            padding: 30px;
        }}
        h1 {{ color: #ffcc66; margin-bottom: 30px; }}
        ul {{ list-style: none; padding: 0; }}
        li {{
            margin: 10px auto;
            background: rgba(255,255,255,0.1);
            width: 60%;
            padding: 15px;
            border-radius: 10px;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        li:hover {{
            transform: translateY(-5px);
            box-shadow: 0 0 10px #ff9900;
        }}
        a {{ color: #ff9900; text-decoration: none; font-weight: bold; }}
        a:hover {{ color: #ffd480; }}
        .back {{
            display: inline-block;
            margin-top: 30px;
            padding: 10px 20px;
            border-radius: 10px;
            background: linear-gradient(135deg, #ff6600, #ff9900);
            color: white;
            text-decoration: none;
            transition: 0.3s;
        }}
        .back:hover {{ box-shadow: 0 0 10px #ff9900; }}
    </style></head><body>
    <h1>🚉 Trains ({direction.replace('_',' ').title()})</h1><ul>
    """
    for t in trains:
        html += f"<li>{t['name']} ({t['number']}) — <a href='/conflict/{direction}/{t['number']}'>Predict Delay</a></li>"
    html += "</ul><a href='/index' class='back'>⬅ Go Back</a></body></html>"
    return html

@app.route("/conflict/<direction>/<train_number>")
@login_required
def conflict(direction, train_number):
    if direction == "jalna_to_aurangabad":
        selected = next((t for t in TRAINS_JALNA_TO_AURANGABAD if t["number"] == train_number), None)
        opposing = TRAINS_AURANGABAD_TO_JALNA
    else:
        selected = next((t for t in TRAINS_AURANGABAD_TO_JALNA if t["number"] == train_number), None)
        opposing = TRAINS_JALNA_TO_AURANGABAD

    if not selected:
        return "Train not found", 404

    halted_trains, decision, new_arrival = simulate_conflicts(selected, opposing)

    html = f"""
    <html>
    <head><title>Prediction</title>
    <style>
        body {{
            font-family: 'Poppins', sans-serif;
            background: linear-gradient(135deg, #001F3F, #003366);
            color: white;
            text-align: center;
            margin: 0;
            padding: 40px;
        }}
        h1 {{ color: #ffcc66; margin-bottom: 20px; }}
        p {{ background: rgba(255,255,255,0.1); padding: 20px; border-radius: 15px; width: 60%; margin: auto; }}
        ul {{ list-style: none; padding: 0; margin-top: 20px; }}
        li {{ margin: 10px auto; background: rgba(255,255,255,0.05); padding: 10px; width: 50%; border-radius: 10px; }}
        a {{
            display: inline-block;
            margin: 20px 10px;
            padding: 10px 20px;
            border-radius: 10px;
            background: linear-gradient(135deg, #ff6600, #ff9900);
            color: white;
            text-decoration: none;
            transition: 0.3s;
        }}
        a:hover {{ box-shadow: 0 0 10px #ff9900; }}
    </style>
    </head>
    <body>
        <h1>🚆 Prediction for {selected['name']} ({selected['number']})</h1>
        <p>{decision}</p>
        <ul>
    """
    for h in halted_trains:
        html += f"<li>{h['halted']['name']} halted at {h['station']} for {h['halt_minutes']} min. New arrival: {h['new_arrival']}</li>"
    html += f"</ul><a href='/trains/{direction}'>⬅ Back to Trains</a><a href='/index'>🏠 Home</a></body></html>"
    return html

@app.route("/logout")
def logout():
    session.pop("authenticated", None)
    return redirect(url_for("password_page"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
