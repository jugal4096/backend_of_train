from flask import Flask, request, redirect, url_for, session
import os
from jalna_to_awb import TRAINS_JALNA_TO_AURANGABAD
from awb_to_jalna import TRAINS_AURANGABAD_TO_JALNA

app = Flask(__name__)
app.secret_key = "your_super_secret_key"  # for sessions
PASSWORD = "4096"  # set your password here

MID_STATION = ["Dinagaoun", "Badnapur", "Karmad", "Chikhalthana"]
TRAIN_TYPE_PRIORITY = {"VB":6, "JShtb":5, "SF":4, "Exp":3, "DEMU":2, "Pass":1}

# ------------------ UTILITY FUNCTIONS ------------------

def hhmm_to_minutes(t):
    h, m = map(int, t.split(":"))
    return h*60 + m

def minutes_to_hhmm(m):
    m = m % (24*60)
    h = m//60
    mm = m%60
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
        return [], f"{selected_train['name']} will arrive on time.", selected_train["arr"]

    halted_trains = []
    halt_duration = 10
    selected_score = train_priority(selected_train)

    for opp in conflicts:
        opp_score = train_priority(opp)
        if selected_score >= opp_score:
            new_arr = add_minutes_to_hhmm(opp["arr"], halt_duration)
            station = MID_STATION[0]
            halted_trains.append({
                "halted": opp,
                "halt_minutes": halt_duration,
                "new_arrival": new_arr,
                "station": station
            })
        else:
            new_arr = add_minutes_to_hhmm(selected_train["arr"], halt_duration)
            station = MID_STATION[0]
            return [], f"{selected_train['name']} will halt at {station} for {opp['name']} (10 min delay). New arrival: {new_arr}", new_arr

    lines = []
    for h in halted_trains:
        lines.append(
            f"{h['halted']['name']} will halt at {h['station']} for {selected_train['name']} "
            f"({h['halt_minutes']} min). New arrival: {h['new_arrival']}"
        )

    return halted_trains, "<br>".join(lines), selected_train["arr"]

# ------------------ ROUTES ------------------

@app.route("/", methods=["GET","POST"])
def password_page():
    if "authenticated" in session and session["authenticated"]:
        return redirect(url_for("index_page"))
    
    if request.method=="POST":
        user_pass = request.form.get("password")
        if user_pass == PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("index_page"))
        else:
            return """
            <html><body style='text-align:center; font-family:Arial;'>
            <h2 style='color:red; margin-top:50px;'>Incorrect password!</h2>
            <a href='/'>Try Again</a>
            </body></html>
            """

    # Password page with background, gradient, and animations
    return """
    <html>
    <head>
        <title>Login</title>
        <style>
            body {
                margin:0; padding:0;
                font-family: Arial, sans-serif;
                height:100vh;
                background: url('https://pic.jpg') no-repeat center center fixed;
                background-size: cover;
                display:flex;
                justify-content:center;
                align-items:center;
            }
            .login-box {
                background: rgba(0,0,0,0.6);
                padding: 50px;
                border-radius: 15px;
                text-align:center;
                color:white;
                box-shadow: 0 0 20px rgba(0,0,0,0.5);
                animation: fadeIn 1.2s ease-in-out;
            }
            input[type="password"] {
                padding:12px;
                width:80%;
                border-radius:5px;
                border:none;
                margin-bottom:20px;
            }
            input[type="submit"] {
                padding:12px 25px;
                border:none;
                border-radius:5px;
                background: #ff6600;
                color:white;
                font-weight:bold;
                cursor:pointer;
                transition: 0.3s;
            }
            input[type="submit"]:hover {
                background:#ff9900;
            }
            h1 {
                margin-bottom:30px;
                animation: fadeDown 1s ease;
            }
            @keyframes fadeIn {
                from {opacity:0;}
                to {opacity:1;}
            }
            @keyframes fadeDown {
                from {opacity:0; transform: translateY(-20px);}
                to {opacity:1; transform: translateY(0);}
            }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h1>Enter Password</h1>
            <form method="POST">
                <input type="password" name="password" placeholder="Password" required><br>
                <input type="submit" value="Enter">
            </form>
        </div>
    </body>
    </html>
    """

@app.route("/index", methods=["GET","POST"])
def index_page():
    if "authenticated" not in session or not session["authenticated"]:
        return redirect(url_for("password_page"))

    if request.method=="POST":
        direction = request.form["direction"]
        return redirect(url_for("show_trains", direction=direction))
    
    return """
    <html>
    <head>
        <title>Railway Delay Predictor</title>
        <style>
            body {font-family:Arial; margin:20px; background:#f5f5f5; text-align:center;}
            h1 {color:#333;}
            input[type="radio"] {margin:10px;}
            input[type="submit"] {padding:10px 20px; border-radius:5px; border:none; background:#ff6600; color:white; cursor:pointer; transition:0.3s;}
            input[type="submit"]:hover {background:#ff9900;}
        </style>
    </head>
    <body>
        <h1>Railway Delay Predictor</h1>
        <form method="POST">
            <label>Select direction:</label><br>
            <input type="radio" name="direction" value="jalna_to_aurangabad" required> Jalna → Aurangabad<br>
            <input type="radio" name="direction" value="aurangabad_to_jalna" required> Aurangabad → Jalna<br><br>
            <input type="submit" value="Show Trains">
        </form>
    </body>
    </html>
    """

@app.route("/trains/<direction>")
def show_trains(direction):
    if "authenticated" not in session or not session["authenticated"]:
        return redirect(url_for("password_page"))

    trains = TRAINS_JALNA_TO_AURANGABAD if direction=="jalna_to_aurangabad" else TRAINS_AURANGABAD_TO_JALNA
    html = f"""
    <html><head><title>Trains</title>
    <style>
        body{{font-family:Arial; text-align:center; margin:20px; background:#f0f0f0;}}
        a{{color:#ff6600; text-decoration:none;}}
        a:hover{{color:#ff9900;}}
        ul{{list-style:none; padding:0;}}
        li{{margin:10px 0;}}
    </style></head><body>
    <h1>Trains ({direction})</h1><ul>
    """
    for t in trains:
        html += f"<li>{t['name']} ({t['number']}) - <a href='/conflict/{direction}/{t['number']}'>Predict Delay</a></li>"
    html += "</ul><a href='/index'>Go Back</a></body></html>"
    return html

@app.route("/conflict/<direction>/<train_number>")
def conflict(direction, train_number):
    if "authenticated" not in session or not session["authenticated"]:
        return redirect(url_for("password_page"))

    if direction=="jalna_to_aurangabad":
        selected = next((t for t in TRAINS_JALNA_TO_AURANGABAD if t["number"]==train_number), None)
        opposing = TRAINS_AURANGABAD_TO_JALNA
    else:
        selected = next((t for t in TRAINS_AURANGABAD_TO_JALNA if t["number"]==train_number), None)
        opposing = TRAINS_JALNA_TO_AURANGABAD

    if not selected:
        return "Train not found", 404

    halted_trains, decision, new_arrival = simulate_conflicts(selected, opposing)

    html = f"""
    <html>
    <head><title>Prediction</title>
    <style>
        body{{font-family:Arial; margin:20px; background:#f0f0f0; text-align:center;}}
        ul{{list-style:none; padding:0;}}
        li{{margin:10px 0;}}
        a{{color:#ff6600; text-decoration:none;}}
        a:hover{{color:#ff9900;}}
    </style>
    </head>
    <body>
        <h1>Prediction for {selected['name']} ({selected['number']})</h1>
        <p>{decision}</p>
        <ul>
    """
    for h in halted_trains:
        html += f"<li>{h['halted']['name']} halted at {h['station']} for {h['halt_minutes']} min. New arrival: {h['new_arrival']}</li>"
    html += f"</ul><a href='/trains/{direction}'>Go Back to Trains</a><br><a href='/index'>Home</a></body></html>"

    return html

# ------------------ RUN APP ------------------
if __name__=="__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)



