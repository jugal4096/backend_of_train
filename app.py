from flask import Flask, request, redirect, url_for, session, send_file
import os
from jalna_to_awb import TRAINS_JALNA_TO_AURANGABAD
from awb_to_jalna import TRAINS_AURANGABAD_TO_JALNA

app = Flask(__name__, static_folder="static")
app.secret_key = "your_super_secret_key"
PASSWORD = "4096"

MID_STATION = ["Dinagaoun", "Badnapur", "Karmad", "Chikhalthana"]
TRAIN_TYPE_PRIORITY = {"VB":6, "JShtb":5, "SF":4, "Exp":3, "DEMU":2, "Pass":1}

# ------------------ IMAGE ------------------
@app.route("/pic.jpg")
def serve_pic():
    return send_file("pics.jpg", mimetype="image/jpeg")

# ------------------ CACHE PREVENTION ------------------
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "-1"
    return response

# ------------------ UTILITIES ------------------
def hhmm_to_minutes(t): h, m = map(int, t.split(":")); return h*60 + m
def minutes_to_hhmm(m): m = m % (24*60); h = m//60; mm = m%60; return f"{h:02d}:{mm:02d}"
def add_minutes_to_hhmm(time_str, add_min): return minutes_to_hhmm(hhmm_to_minutes(time_str) + add_min)
def train_priority(train): return TRAIN_TYPE_PRIORITY.get(train["type"],0)

def find_conflicts(selected_train, opposing_trains, window_before=60):
    selected_time = hhmm_to_minutes(selected_train["dep"])
    return [opp for opp in opposing_trains if selected_time - window_before <= hhmm_to_minutes(opp["dep"]) <= selected_time + window_before]

def simulate_conflicts(selected_train, opposing_trains):
    conflicts = find_conflicts(selected_train, opposing_trains)
    if not conflicts: return [], f"{selected_train['name']} will arrive on time.", selected_train["arr"]

    halted_trains = []
    halt_duration = 10
    selected_score = train_priority(selected_train)

    for opp in conflicts:
        opp_score = train_priority(opp)
        if selected_score >= opp_score:
            new_arr = add_minutes_to_hhmm(opp["arr"], halt_duration)
            station = MID_STATION[0]
            halted_trains.append({"halted": opp, "halt_minutes": halt_duration, "new_arrival": new_arr, "station": station})
        else:
            new_arr = add_minutes_to_hhmm(selected_train["arr"], halt_duration)
            station = MID_STATION[0]
            return [], f"{selected_train['name']} will halt at {station} for {opp['name']} (10 min delay). New arrival: {new_arr}", new_arr

    lines = [f"{h['halted']['name']} will halt at {h['station']} for {selected_train['name']} ({h['halt_minutes']} min). New arrival: {h['new_arrival']}" for h in halted_trains]
    return halted_trains, "<br>".join(lines), selected_train["arr"]

# ------------------ AUTH ------------------
def login_required(func):
    def wrapper(*args, **kwargs):
        if "authenticated" not in session or not session["authenticated"]:
            return redirect(url_for("password_page"))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

# ------------------ ROUTES ------------------
@app.route("/", methods=["GET","POST"])
def password_page():
    if "authenticated" in session and session["authenticated"]:
        return redirect("/index.html")

    if request.method=="POST":
        if request.form.get("password") == PASSWORD:
            session["authenticated"] = True
            return redirect("/index.html")
        return "<h2 style='color:red;text-align:center;margin-top:50px;'>Incorrect password!</h2><a href='/'>Try Again</a>"

    return """
    <form method="POST" style="text-align:center;margin-top:50px;">
        <input type="password" name="password" placeholder="Password" required>
        <input type="submit" value="Enter">
    </form>
    """

# Serve the static index.html directly
@app.route("/index.html", methods=["GET","POST"])
@login_required
def index_page():
    if request.method=="POST":
        direction = request.form.get("direction")
        return redirect(url_for("show_trains", direction=direction))
    return app.send_static_file("index.html")

@app.route("/trains/<direction>")
@login_required
def show_trains(direction):
    trains = TRAINS_JALNA_TO_AURANGABAD if direction=="jalna_to_aurangabad" else TRAINS_AURANGABAD_TO_JALNA
    html = f"<h1>Trains ({direction})</h1><ul>"
    for t in trains:
        html += f"<li>{t['name']} ({t['number']}) - <a href='/conflict/{direction}/{t['number']}'>Predict Delay</a></li>"
    html += "</ul><a href='/index.html'>Go Back</a>"
    return html

@app.route("/conflict/<direction>/<train_number>")
@login_required
def conflict(direction, train_number):
    if direction=="jalna_to_aurangabad":
        selected = next((t for t in TRAINS_JALNA_TO_AURANGABAD if t["number"]==train_number), None)
        opposing = TRAINS_AURANGABAD_TO_JALNA
    else:
        selected = next((t for t in TRAINS_AURANGABAD_TO_JALNA if t["number"]==train_number), None)
        opposing = TRAINS_JALNA_TO_AURANGABAD

    if not selected: return "Train not found", 404

    halted_trains, decision, _ = simulate_conflicts(selected, opposing)
    html = f"<h1>Prediction for {selected['name']} ({selected['number']})</h1><p>{decision}</p><ul>"
    for h in halted_trains:
        html += f"<li>{h['halted']['name']} halted at {h['station']} for {h['halt_minutes']} min. New arrival: {h['new_arrival']}</li>"
    html += f"</ul><a href='/trains/{direction}'>Back to Trains</a><br><a href='/index.html'>Home</a>"
    return html

@app.route("/logout")
def logout():
    session.pop("authenticated", None)
    return redirect("/")

# ------------------ RUN ------------------
if __name__=="__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
