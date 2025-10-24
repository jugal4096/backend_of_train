from flask import Flask, request, redirect, url_for
from datetime import datetime, timedelta
import os

from jalna_to_awb import TRAINS_JALNA_TO_AURANGABAD
from awb_to_jalna import TRAINS_AURANGABAD_TO_JALNA

app = Flask(__name__)

MID_STATION = ["Dinagaoun", "Badnapur", "Karmad", "Chikhalthana"]
TRAIN_TYPE_PRIORITY = {"VB":6, "JShtb":5, "SF":4, "Exp":3, "DEMU":2, "Pass":1}

# Utility functions
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

# ---------------- ROUTES ------------------

@app.route("/", methods=["GET","POST"])
def index():
    if request.method == "POST":
        direction = request.form["direction"]
        return redirect(url_for("show_trains", direction=direction))
    return """
    <html>
    <head><title>Railway Delay Predictor</title></head>
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
    trains = TRAINS_JALNA_TO_AURANGABAD if direction=="jalna_to_aurangabad" else TRAINS_AURANGABAD_TO_JALNA
    html = f"<html><head><title>Trains</title></head><body><h1>Trains ({direction})</h1><ul>"
    for t in trains:
        html += f"<li>{t['name']} ({t['number']}) - <a href='/conflict/{direction}/{t['number']}'>Predict Delay</a></li>"
    html += "</ul><a href='/'>Go Back</a></body></html>"
    return html

@app.route("/conflict/<direction>/<train_number>")
def conflict(direction, train_number):
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
    <head><title>Prediction</title></head>
    <body>
        <h1>Prediction for {selected['name']} ({selected['number']})</h1>
        <p>{decision}</p>
        <ul>
    """
    for h in halted_trains:
        html += f"<li>{h['halted']['name']} halted at {h['station']} for {h['halt_minutes']} min. New arrival: {h['new_arrival']}</li>"
    html += "</ul><a href='/trains/{direction}'>Go Back to Trains</a><br><a href='/'>Home</a></body></html>"

    return html

# ---------------- RUN APP ------------------
if __name__=="__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


