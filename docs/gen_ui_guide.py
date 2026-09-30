"""
Generates  docs/03_USER_INTERFACE_GUIDE.pdf

A plain-language walkthrough of every screen, written for a reader with
no engineering background. Every technical word is defined the first
time it appears, and each screen is shown zoomed into its individual
panels rather than as one shrunken page.
"""

from __future__ import annotations

import json
from pathlib import Path

from pdf_kit import (
    ACCENT, CONTENT_W, CRIT, H1, H2, H3, MUTED, OK, P, Report, STYLES, WARN,
    bullets, callout, code, cover, esc, figure, kpi_row, rule, spacer,
    table, toc,
)
from reportlab.platypus import KeepTogether, PageBreak, Paragraph

ROOT = Path(__file__).resolve().parents[1]
EV = json.loads((ROOT / "docs" / "evidence.json").read_text(encoding="utf-8"))
EW = EV["api"]["metrics"]["early_warning"]
MS = EV.get("machine_shots", {})


def _h(v):
    """Health as the ring prints it - whole numbers."""
    return "-" if v is None else f"{float(v):.0f}"


def _r(v):
    """Remaining life as the screen prints it - one decimal."""
    return "-" if v is None else f"{float(v):.1f}"

PRED_SHOT = MS.get("predicted", {})
BRCH_SHOT = MS.get("breached", {})

OUT = ROOT / "docs" / "03_USER_INTERFACE_GUIDE.pdf"


def whatyousee(rows):
    """A 'what you are looking at' table: element -> plain meaning."""
    return table([["What you see", "What it means"]] + rows,
                 widths=[152, CONTENT_W - 152])


def build():
    story = []

    # ============================================================ COVER
    story += cover(
        "A Visitor's Guide to the Screens",
        "Everything on the Predictive Maintenance display, explained in plain English",
        "Document 3 of 3  -  User Interface Guide",
        [
            ("Project", "AI-Based Predictive Maintenance for CNC Milling Machines"),
            ("Document", "User Interface Guide (non-technical)"),
            ("Written for", "Anyone - no engineering or computing background needed"),
            ("Version", "1.0"),
            ("Date", "10 September 2026"),
        ],
        tagline="If you have never seen a factory control screen before, start at page 1 "
                "and read straight through. Every word that appears on the display is "
                "explained here before you are asked to look at it.",
    )

    # ============================================================ TOC
    story += toc([
        (1, "Part 1  -  Understanding the idea"),
        (2, "1.1  What problem does this solve?"),
        (2, "1.2  How the system works, in one page"),
        (2, "1.3  The words you will see on screen"),
        (2, "1.4  The colour code"),
        (1, "Part 2  -  Getting started"),
        (2, "2.1  Starting the program"),
        (2, "2.2  The bar across the top of every screen"),
        (1, "Part 3  -  The six screens"),
        (2, "3.1  Screen 1  -  Plant Overview"),
        (2, "3.2  Screen 2  -  Machine HMI"),
        (2, "3.3  Screen 3  -  Manual Input"),
        (2, "3.4  Screen 4  -  Batch Analysis"),
        (2, "3.5  Screen 5  -  Alarms"),
        (2, "3.6  Screen 6  -  Model Insights"),
        (1, "Part 4  -  Reference"),
        (2, "4.1  A five-minute tour to show someone else"),
        (2, "4.2  Questions people usually ask"),
        (2, "4.3  Glossary"),
    ])

    # ============================================================ PART 1
    story += [H1("Part 1  -  Understanding the idea")]

    story += [H2("1.1  What problem does this solve?")]
    story += [P(
        "Machine shops run CNC milling machines all day. A milling machine spins a cutting "
        "tool (an end mill) at high speed to carve metal parts out of a solid block. "
        "Sooner or later a machine breaks. When it breaks "
        "without warning, everything stops: production halts, people stand idle, the repair "
        "is rushed and expensive, and sometimes it is dangerous.")]
    story += [P("Traditionally there are only two ways to deal with this, and neither is good:")]
    story += [table([
        ["Approach", "What it means", "The problem with it"],
        ["Fix it when it breaks",
         "Wait for the machine to fail, then repair it.",
         "The failure happens at the worst possible moment, and the damage is often worse "
         "than it needed to be."],
        ["Service it on a calendar",
         "Service every machine every three months whether it needs it or not.",
         "You replace healthy parts for no reason, and a machine can still break in "
         "week two."],
    ], widths=[104, 150, CONTENT_W - 254])]

    story += [P(
        "This project does something different. It watches the machine's own measurements "
        "and learns to recognise the pattern that appears <b>shortly before</b> a "
        "particular kind of breakdown. Then it says so, while the machine is still running "
        "and there is still time to act.")]

    story += [callout(
        "The everyday comparison",
        "Think of a doctor. Waiting for a heart attack and then treating it is the first "
        "approach. A yearly check-up whether you need one or not is the second. This system "
        "is the third: continuous monitoring that notices your blood pressure climbing "
        "week after week and tells you <i>before</i> anything happens - and tells you "
        "<i>which</i> problem is developing, not just that something is wrong.", "info")]

    story += [H3("How much warning does it actually give?")]
    story += [kpi_row([
        ("Average warning", f"{EW['mean_lead_hours']} hours", "before the breakdown"),
        ("Machines warned in time", f"{EW['warned_before_failure_pct']}%",
         f"of {EW['machines_evaluated']} tested"),
        ("Kinds of failure it names", "4", "and it says which one"),
    ])]
    story += [spacer(8)]
    story += [P(
        "That is close to a full working shift of notice. Enough to finish the current "
        "batch, order the part, and schedule the repair for a planned stop instead of an "
        "emergency one.")]

    story += [H2("1.2  How the system works, in one page")]
    story += [P("There are three steps, and you can see all three on the screens.")]

    story += [table([
        ["Step", "What happens", "Where you see it"],
        ["1. Measure",
         "Five things are measured on the milling machine: how hot the surrounding air is, "
         "how hot the cutting process is, how fast the spindle is spinning, how hard it is "
         "twisting (torque), and how worn the end mill is.",
         "The five round dials on the Machine screen"],
        ["2. Judge",
         "Three separate judgements are made about those five numbers, and the most serious "
         "one wins. One judgement is made by the trained computer model; the other two are "
         "straightforward engineering checks that cannot be fooled even if the model is "
         "wrong.",
         "The alarm banner and the coloured bars"],
        ["3. Report",
         "The result is shown as a health score out of 100, an estimate of how long the "
         "machine has left, a colour-coded alarm, a plain-English instruction for the "
         "technician, and an explanation of why.",
         "Everything else on the screen"],
    ], widths=[62, CONTENT_W - 232, 170])]

    story += [callout(
        "Why three judgements instead of one?",
        "The computer model is the clever part, but it learned from examples and could in "
        "principle be wrong about an unusual machine. So it is never allowed to be the only "
        "thing standing between a fault and the operator. Two of the three checks are plain "
        "arithmetic on the measurements themselves - the kind of check an experienced "
        "engineer would do on paper - and they keep working no matter what the model says. "
        "The system always acts on whichever of the three is most worried.", "ok")]

    story += [H2("1.3  The words you will see on screen")]
    story += [P(
        "These are the only technical terms in the whole interface. Everything else is "
        "ordinary English.")]

    story += [table([
        ["Word on screen", "What it means, plainly"],
        ["Reading",
         "One complete set of the five measurements, taken at one moment. In this system a "
         "reading is taken every 10 minutes, so 6 readings = 1 hour of machine time."],
        ["Health index",
         "A score out of 100 describing the condition of the machine right now. 100 is "
         "perfect; 0 means it has failed. It is shown as a coloured ring."],
        ["Remaining Useful Life (RUL)",
         "An estimate of how much longer the machine can keep working before it fails, in "
         "hours. The screen always prints underneath how confident that estimate is."],
        ["Prediction",
         "The kind of breakdown the machine appears to be heading towards. It is one of "
         "five answers: Normal (nothing coming), or one of the four failure types below."],
        ["Confidence",
         "How sure the system is about its prediction, as a percentage."],
        ["Alarm band",
         "How serious the situation is, in four steps: Normal, Advisory, Warning, Critical."],
        ["Stress",
         "How close the machine is to a particular limit, as a percentage. 0% means "
         "comfortable; 100% means sitting exactly on the limit."],
        ["Machine variant (L / M / H)",
         "Three grades of the product being made - Low, Medium and High quality. Each grade "
         "tolerates a different amount of strain, so the system takes it into account."],
    ], widths=[122, CONTENT_W - 122])]

    story += [H3("The four kinds of failure")]
    story += [P(
        "The system does not just say “something is wrong”. It names which of four "
        "specific mechanical problems is developing, because each needs a different repair.")]
    story += [table([
        ["Short name", "Full name", "In plain English", "What a technician does"],
        ["TWF", "Tool Wear Failure",
         "The milling cutter (end mill) has been used so long it has gone blunt.",
         "Change the end mill at the next convenient stop."],
        ["HDF", "Heat Dissipation Failure",
         "The milling machine cannot get rid of its spindle and cutting heat fast enough "
         "- like a car radiator clogging up.",
         "Check the coolant supply, clean the spindle-chiller fins, verify the fan."],
        ["PWF", "Power Failure",
         "The spindle motor is drawing too much or too little power - it is being "
         "strained or is not pulling properly.",
         "Check the spindle drive, the feed rate and depth of cut, and whether something is jammed."],
        ["OSF", "Overstrain Failure",
         "The combination of a worn tool and heavy load is putting too much force through "
         "the spindle.",
         "Reduce the feed rate immediately, change the worn end mill, inspect the spindle."],
    ], widths=[52, 92, CONTENT_W - 300, 156])]

    story += [H2("1.4  The colour code")]
    story += [P(
        "Colour carries meaning consistently on every screen. If you learn only one thing "
        "from this guide, learn this table.")]
    story += [table([
        ["Colour", "Band", "Health score", "What it means", "What to do"],
        ["Green", "NORMAL", "85 - 100", "Everything is fine.", "Nothing."],
        ["Blue", "ADVISORY", "65 - 85", "Slight wear is beginning to show. Perfectly normal "
         "for a machine in use.", "Nothing yet. Keep an eye on it."],
        ["Amber", "WARNING", "40 - 65", "Something is genuinely developing.",
         "Plan a repair. Read the recommended action."],
        ["Red", "CRITICAL", "0 - 40", "Failure is close, or has happened.",
         "Act now. The screen tells you exactly what to check."],
    ], widths=[46, 62, 62, CONTENT_W - 340, 170])]

    story += [callout(
        "The single most important distinction in the whole interface",
        "When the alarm banner shows a small blue badge saying <b>PREDICTED</b>, it means: "
        "<i>the machine is still running normally, but it is heading for this failure - you "
        "have time to act.</i><br/><br/>"
        "When it shows a red badge saying <b>LIMIT BREACHED</b>, it means: <i>a physical "
        "limit has already been crossed. This has happened.</i><br/><br/>"
        "The entire value of this project lies in the gap between those two badges - "
        "on average about nine hours.", "warn")]
    story += [PageBreak()]

    # ============================================================ PART 2
    story += [H1("Part 2  -  Getting started")]

    story += [H2("2.1  Starting the program")]
    story += [P("Open a command window in the project folder and type this one line:")]
    story += [code('.\\.venv\\Scripts\\python.exe -m backend.app')]
    story += [P(
        "Wait a few seconds. When you see <font face='Courier'>Uvicorn running on "
        "http://127.0.0.1:8000</font>, open a web browser and go to:")]
    story += [code("http://127.0.0.1:8000/")]
    story += [P(
        "Leave the command window open - that is the program itself running. Closing it "
        "stops the system.")]
    story += [callout(
        "Nothing needs to be installed and there is no internet required",
        "The display does not download anything from the web. Every dial, chart and colour "
        "is drawn by the program itself. It will work exactly the same on a laptop with the "
        "network cable unplugged - which is deliberate, so a demonstration can never fail "
        "because the room has no Wi-Fi.", "ok")]

    story += [H3("The very first thing to do")]
    story += [P(
        "The system starts empty, because no machines are being watched yet. Press the "
        "<b>Start Demo Plant</b> button on the first screen. Four machines will appear and "
        "begin running - each one replaying the real recorded life of an actual machine, "
        "right through to its breakdown. Then just watch.")]

    story += [H2("2.2  The bar across the top of every screen")]
    story += figure("03_overview_running",
                    "The top bar. It never changes and is present on all six screens.",
                    crop=(0, 0, 1, 0.055))
    story += [whatyousee([
        ["The blue gear symbol and title on the far left",
         "The name of the system. Clicking it does nothing - it is just a label."],
        ["Six words in the middle: Plant Overview, Machine HMI, Manual Input, "
         "Batch Analysis, Alarms, Model Insights",
         "These are the six screens. Click any one to go to it. The screen you are "
         "currently on is highlighted in blue."],
        ["A small round lamp and the word “online”, on the right",
         "Green means the program is running properly. Red would mean the display has lost "
         "contact with the program. Beside it are the number of machines being watched and "
         "the total number of readings taken so far."],
        ["The blue clock on the far right",
         "The current time. It ticks every second, which is a simple way to confirm the "
         "display is live and not frozen."],
    ])]
    story += [PageBreak()]

    # ============================================================ SCREEN 1
    story += [H1("Part 3  -  The six screens")]
    story += [H2("3.1  Screen 1  -  Plant Overview")]
    story += [P(
        "<b>Think of this as the wall display in a control room.</b> It shows every machine "
        "at once, so a supervisor can glance at it and know instantly whether anything needs "
        "attention.")]
    story += figure("03_overview_running",
                    "Figure 1 - The Plant Overview screen with four machines running.")

    story += [H3("The five boxes across the top")]
    story += figure("03_overview_running", "The summary strip.", crop=(0, 0.14, 1, 0.252))
    story += [whatyousee([
        ["MACHINES", "How many machines are being watched."],
        ["MEAN HEALTH", "The average health score across all of them. A quick sense of how "
         "the whole factory is doing."],
        ["AT RISK", "How many machines are currently heading for a breakdown. If this reads "
         "0, nothing is developing anywhere."],
        ["CRITICAL", "How many machines are in the most serious alarm state."],
        ["OPEN ALARMS", "How many alarms nobody has ticked off yet. This is the supervisor's "
         "to-do count."],
    ])]

    story += [H3("The machine cards")]
    story += figure("03_overview_running", "One machine card, enlarged.",
                    crop=(0.005, 0.255, 0.255, 0.50), width_frac=0.52)
    story += [whatyousee([
        ["MACHINE-01 in large letters", "The name of the machine."],
        ["“Variant M · 44 readings”",
         "The product grade this machine makes, and how many measurements have been taken "
         "from it so far."],
        ["The small glowing lamp, top right",
         "The machine's status colour at a glance - green, blue, amber or red. A red lamp "
         "blinks."],
        ["The big number and the word “health”",
         "The health score out of 100. The coloured bar underneath is the same number drawn "
         "as a bar - as the machine wears out, the bar shrinks and changes colour."],
        ["Prediction",
         "Either “Normal”, or the three-letter name of the failure it is heading "
         "towards."],
        ["Remaining life",
         "How long before it is expected to fail. If the machine is not degrading at all, "
         "this says STABLE rather than inventing a number."],
        ["Tool wear",
         "How many minutes the cutting tool has been in use. Tools are changed at about "
         "200 minutes."],
        ["Last seen", "The time of the most recent measurement."],
        ["An amber “1 OPEN ALARM” tag at the bottom",
         "This machine has raised an alarm that nobody has acknowledged yet."],
    ])]

    story += [H3("Things you can do here")]
    story += [table([
        ["Action", "What happens"],
        ["Click anywhere on a machine card", "Opens the detailed screen for that machine."],
        ["Press Start Demo Plant", "Starts four machines, deliberately chosen to be heading "
         "for four different kinds of breakdown, so you can see the whole range."],
        ["Press Stop All", "Pauses every machine. The history stays."],
        ["Press Reset Plant", "Deletes everything and returns to an empty display. You will "
         "be asked to confirm."],
    ], widths=[142, CONTENT_W - 142])]

    story += [callout(
        "The cards reorder themselves",
        "The machine in the worst condition is always moved to the top-left position. You "
        "never have to hunt for the problem - if there is one, it is where your eye lands "
        "first.", "info")]
    story += [PageBreak()]

    # ============================================================ SCREEN 2
    story += [H2("3.2  Screen 2  -  Machine HMI")]
    story += [P(
        "<b>This is the main screen, and the one worth spending time on.</b> It shows "
        "everything about one machine. “HMI” simply stands for Human-Machine Interface - "
        "the industry’s term for an operator’s screen.")]

    pv, bv = PRED_SHOT, BRCH_SHOT
    story += [P(
        "We will look at the same machine, {mid}, twice: first while it is being warned "
        "about but still running, and then later at the moment a physical limit is actually "
        "crossed. The difference between those two pictures is the whole point of the "
        "project.".format(mid=pv.get("machine_id", "MACHINE-03")))]

    story += figure("06_machine_predicted",
                    "Figure 2 - Reading {p} of {t}. The system is warning about a coming "
                    "{m}, but nothing has happened yet: health {h}, about {r} hours of life "
                    "left.".format(p=pv.get("position"), t=pv.get("total"),
                                   m=pv.get("alarm_mode_name", "failure"),
                                   h=_h(pv.get("health")), r=_r(pv.get("rul_hours"))))
    story += figure("07_machine_breached",
                    "Figure 3 - The same machine at reading {p}. The limit has now been "
                    "crossed: health {h}, no life left. The status line records that the "
                    "system first warned about this {L} readings - {H} hours - "
                    "earlier.".format(p=bv.get("position"), h=_h(bv.get("health")),
                                      L=bv.get("lead_time_readings"),
                                      H=bv.get("lead_time_hours")))

    story += [H3("The line under the machine name")]
    story += figure("07_machine_breached", "The status line.", crop=(0, 0.068, 0.72, 0.14))
    story += [whatyousee([
        ["“reading {p}/{t}”".format(p=bv.get("position"), t=bv.get("total")),
         "This machine is at measurement number {p} out of the {t} that exist in its "
         "recorded life.".format(p=bv.get("position"), t=bv.get("total"))],
        ["“RUNNING” in green, or “stopped”",
         "Whether the recording is currently playing. It reads “stopped” in this "
         "picture because the replay was paused to take the screenshot."],
        ["“true failure {m} at cycle {c}”".format(m=bv.get("eventual_failure_mode"),
                                                    c=bv.get("fails_at_cycle")),
         "Because this is a recording of a real machine, we already know how it ended. This "
         "tells you the truth in advance, so you can judge whether the system’s prediction "
         "was right. That is unusual honesty - most systems only show you their own answer."],
        ["“first warned {L} readings ({H} h) ahead” in green".format(
            L=bv.get("lead_time_readings"), H=bv.get("lead_time_hours")),
         "<b>This is the headline result.</b> The system raised its first warning {L} "
         "measurements - about {H} hours of machine time - before this machine actually "
         "failed.".format(L=bv.get("lead_time_readings"), H=bv.get("lead_time_hours"))],
    ])]

    story += [H3("The alarm banner - and the two badges that matter")]
    story += figure("06_machine_predicted",
                    "Earlier: a warning, but nothing has actually happened.",
                    crop=(0, 0.148, 1, 0.250))
    story += figure("07_machine_breached",
                    "Later: a physical limit has been crossed.",
                    crop=(0, 0.148, 1, 0.250))
    story += [whatyousee([
        ["The large coloured word",
         "How serious it is. The whole banner is tinted to match, and a critical banner "
         "pulses gently so it catches your eye."],
        ["The failure name beside it - “{m}”".format(m=bv.get("alarm_mode_name")),
         "Which of the four problems is developing."],
        ["The blue PREDICTED badge",
         "The system is forecasting this failure. The machine is <b>still running</b> and "
         "there is time to act. In the first picture the message reads: “" +
         (pv.get("alarm_message") or "").split(" [")[0] + "”"],
        ["The red LIMIT BREACHED badge",
         "A physical limit has <b>already</b> been crossed. In the second picture the "
         "message becomes a measured fact rather than a forecast: “" +
         (bv.get("alarm_message") or "").split(" [")[0] + "”"],
        ["“Action:” and the text after it",
         "A specific instruction for the technician. Not “something is wrong”, but which "
         "parts to check and what to do: “" + (bv.get("alarm_action") or "") + "”"],
    ])]
    story += [callout(
        "This is the gap the project exists to create",
        "In the first picture the machine is running and has roughly {r} hours of estimated "
        "life left. In the second it has failed. Everything in this system - the choice of "
        "what to train the model on, the way health is calculated, the alarm rules - exists "
        "to make that first picture appear as early as possible. Here it appeared "
        "<b>{H} hours</b> before the breakdown.".format(
            r=_r(pv.get("rul_hours")), H=bv.get("lead_time_hours")), "ok")]

    story += [H3("The health ring and the countdown")]
    story += figure("06_machine_predicted",
                    "Health and remaining life while the machine is still running.",
                    crop=(0.010, 0.262, 0.200, 0.570), width_frac=0.40)
    story += [whatyousee([
        ["The big coloured ring with a number in it",
         "The health score out of 100 - {h} here. The ring fills up in proportion, and its "
         "colour follows the standard code. Under the number is the name of the band it is "
         "in: {b}.".format(h=_h(pv.get("health")), b=(pv.get("health_label") or "").upper())],
        ["REMAINING USEFUL LIFE and a time",
         "How long the machine is expected to keep working - {r} hours here. In the second "
         "picture it reads 0.0 h.".format(r=_r(pv.get("rul_hours")))],
        ["The small grey line under the time",
         "<b>How much to trust that number.</b> It says either “trend fit” with a quality "
         "score - meaning the system has watched this machine long enough to measure how "
         "fast it is degrading - or “nominal estimate, low confidence”, meaning this is a "
         "single snapshot and the figure is only a rough guide. The system never presents a "
         "guess as though it were a measurement."],
    ])]

    story += [H3("The five dials")]
    story += figure("07_machine_breached", "The live sensor dials.",
                    crop=(0.206, 0.268, 0.992, 0.480))
    story += [P(
        "These are the raw measurements from the machine, drawn as old-fashioned panel "
        "instruments because a moving needle is easier to read at a glance than a number. "
        "Each dial has a gap at the bottom, tick marks around the edge, and a coloured arc "
        "that grows as the value rises.")]
    story += [whatyousee([
        ["AIR TEMPERATURE (K)",
         "How hot the air around the machine is. K stands for Kelvin, a temperature scale "
         "used in engineering; 300 K is about 27 degrees Celsius, roughly a warm room."],
        ["PROCESS TEMPERATURE (K)",
         "How hot the machine itself is. What matters is the difference between this and "
         "the air temperature - if the gap gets too small, the machine has stopped shedding "
         "heat properly. That is exactly what went wrong in this example."],
        ["ROTATIONAL SPEED (rpm)",
         "How fast the machine is spinning, in revolutions per minute."],
        ["TO”UE (Nm)",
         "How hard the machine is having to work - the twisting force it is applying."],
        ["TOOL WEAR (min)",
         "How many minutes the cutting tool has been in use. This one only ever goes up, "
         "until the tool is changed."],
        ["“READING {p} / {t}” in the corner".format(p=bv.get("position"),
                                                       t=bv.get("total")),
         "Which measurement you are currently looking at."],
    ])]

    story += [H3("Mechanism stress - the four bars")]
    story += figure("06_machine_predicted",
                    "Earlier: the dominant concern is already visible.",
                    crop=(0.010, 0.592, 0.200, 0.818), width_frac=0.40)
    story += figure("07_machine_breached",
                    "Later: it has reached 100% - the machine is on its limit.",
                    crop=(0.010, 0.595, 0.200, 0.820), width_frac=0.40)
    story += [P(
        "Each bar shows how close the machine is to one of the four failure limits, as a "
        "percentage. The bar labelled <b>DOMINANT</b> is the one nearest its limit - the "
        "problem to worry about first. Bars change colour as they climb, from green through "
        "blue and amber to red.")]
    story += [P(
        "Comparing the two pictures tells the whole story without reading a single word. "
        "The {d} bar climbs to 100% while the other three barely move. This machine had one "
        "specific problem, and the screen says which.".format(
            d=bv.get("dominant_mode", "dominant")))]

    story += [H3("The two charts")]
    story += figure("07_machine_breached", "The trend charts.",
                    crop=(0.206, 0.482, 0.992, 0.775))
    story += [whatyousee([
        ["Left chart - HEALTH & FAILURE PROBABILITY",
         "The blue line is the health score over recent history; the dashed red line is how "
         "likely a failure is. As the machine degrades the blue line falls and the red line "
         "rises, and they cross over. The faint horizontal bands are the colour zones - "
         "green near the top, red at the bottom."],
        ["Right chart - GOVERNING PHYSICS",
         "The underlying physical quantities, each drawn as a percentage of its own limit "
         "so that four different kinds of measurement can share one chart honestly. The red "
         "strip across the top is the danger zone above 100%."],
        ["The numbers along the bottom, e.g. -89 ... -44 ... 0",
         "How many readings ago. 0 is now; -89 is eighty-nine readings ago."],
    ])]

    story += [H3("Ground truth - the honesty panel")]
    story += figure("07_machine_breached", "The ground-truth panel.",
                    crop=(0.206, 0.795, 0.992, 0.915))
    story += [callout(
        "Why this panel is unusual",
        "Because these machines are recordings of real ones, the system already knows how "
        "each story ends - and it shows you, side by side with its own prediction. Most "
        "demonstrations only show you the answer they produced. This one hands you the mark "
        "scheme so you can grade it yourself.", "ok")]
    story += [whatyousee([
        ["Model says", "What the system predicts - {m} here.".format(
            m=bv.get("predicted_class"))],
        ["Actual state now", "What is genuinely happening at this moment."],
        ["Will fail by",
         "How this machine really does end - known in advance from the recording."],
        ["Time to failure",
         "How many readings remain until the real breakdown, and how many hours that is. It "
         "reads FAILED once that moment has passed."],
        ["The line at the bottom",
         "A tick if the prediction matches, or a note explaining that a mismatch is usually "
         "the system warning <i>even earlier</i> than the recording’s own labels expected - "
         "which is a good thing, not a mistake."],
    ])]

    story += [H3("The two buttons")]
    story += [table([
        ["Button", "What it does"],
        ["START (green)",
         "Runs the machine’s recorded life from the beginning. Clears its previous history."],
        ["STOP (red)", "Pauses it. Everything recorded so far stays on screen."],
        ["Back to All Machines", "Goes back to the list of machines."],
    ], widths=[122, CONTENT_W - 122])]
    story += [PageBreak()]

    story += [H2("3.3  Screen 3  -  Manual Input")]
    story += [P(
        "<b>This screen answers “what if?”</b> You type in five measurements by hand "
        "and the system tells you everything it can about that machine. It is the best "
        "screen for showing somebody how the system thinks, because you control the input "
        "and can watch the answer change.")]
    story += figure("09_manual_hdf", "Figure 3 - The Manual Input screen.")

    story += [H3("The panel on the left - where you type")]
    story += figure("09_manual_hdf", "The entry panel.",
                    crop=(0.005, 0.145, 0.23, 1.0), width_frac=0.30)
    story += [whatyousee([
        ["Machine Variant - a drop-down with L, M and H",
         "Which grade of product this machine makes. It matters because the three grades "
         "tolerate different amounts of strain."],
        ["Five boxes, each with a slider underneath",
         "The five measurements. Type a number or drag the slider - they stay in step with "
         "each other."],
        ["The small grey range beside each label, e.g. “290-315 K”",
         "The values you would normally expect to see. If you type something outside it, the "
         "box outlines in amber - but the system still accepts it and gives you an answer, "
         "because an unusual value may be exactly the fault you are looking for."],
        ["Machine ID (optional)",
         "Give a name here if you want the reading saved and added to the Plant Overview."],
        ["ANALYSE / Analyse & Save",
         "ANALYSE just shows the answer. Analyse & Save also records it against the machine "
         "name you typed."],
        ["The PRESETS buttons at the bottom",
         "<b>Start here.</b> Five ready-made examples - one healthy machine and one heading "
         "for each of the four failures. One click fills in all five boxes with real "
         "measurements taken from an actual machine on its way to that breakdown."],
    ])]

    story += [H3("The health ring, probabilities and stress")]
    story += figure("09_manual_hdf", "The three summary panels.",
                    crop=(0.23, 0.245, 1.0, 0.54))
    story += [whatyousee([
        ["The ring on the left", "The health score, exactly as on the machine screen."],
        ["CLASS PROBABILITIES",
         "The system's full opinion, not just its final answer. Each of the five possible "
         "outcomes gets a percentage, and the one it settled on is tagged PREDICTED. Here it "
         "is 92.2% sure the problem is heat, and only 6.3% sure the machine is fine."],
        ["MECHANISM STRESS",
         "How close this reading is to each of the four physical limits, with the nearest "
         "tagged DOMINANT."],
    ])]

    story += [H3("The verdict")]
    story += figure("09_manual_hdf", "The verdict panel.",
                    crop=(0.23, 0.55, 0.615, 0.90), width_frac=0.62)
    story += [P(
        "A plain summary: the prediction, how confident, the health score, the remaining "
        "life and what that estimate is based on, and which mechanism dominates. Underneath, "
        "in sentences:")]
    story += bullets([
        "<b>What this means</b> - the prediction written out in words.",
        "<b>Cause</b> - the physical reason this failure happens.",
        "<b>Action</b> - what a technician should actually do.",
    ])

    story += [H3("“Why” - the explanation panel")]
    story += figure("09_manual_hdf", "The explanation panel.",
                    crop=(0.61, 0.55, 1.0, 0.98), width_frac=0.62)
    story += [P(
        "This is the part people find most interesting, because computer predictions are "
        "usually a black box. This panel opens the box.")]
    story += [whatyousee([
        ["The sentence at the top",
         "Names the measurements that pushed the answer, with their values. For example: "
         "“Thermal Gradient at 9.12 K, Tool Wear at 101.2 min and Tool Strain at 4726 "
         "raised the likelihood of HDF from a baseline 20% to 92%.”"],
        ["The bars underneath",
         "One per measurement, ranked by how much it mattered. A bar growing to the right "
         "in red pushed the answer <i>towards</i> this failure; a bar to the left in green "
         "pushed it <i>away</i>. The number on the right is that measurement's exact "
         "contribution."],
        ["The line at the very bottom",
         "States that the contributions add up <b>exactly</b> to the system's answer. This "
         "is not a simplified summary of the reasoning - it <i>is</i> the reasoning, "
         "arithmetic to fifteen decimal places."],
    ])]
    story += [PageBreak()]

    # ============================================================ SCREEN 4
    story += [H2("3.4  Screen 4  -  Batch Analysis")]
    story += [P(
        "<b>For checking a whole file at once.</b> If you have a spreadsheet with hundreds "
        "or thousands of past measurements, drop it here and every row is analysed.")]
    story += figure("14_batch_results", "Figure 4 - Batch Analysis after checking 300 readings.")

    story += [H3("How to use it")]
    story += [table([
        ["Step", "What to do"],
        ["Easiest way to try it",
         "Press <b>Use dataset sample</b>. It fetches a real machine's complete life - 300 "
         "readings ending in a genuine breakdown - and analyses the lot. Watch the health "
         "line fall from 99.9 to 0.3."],
        ["Your own file",
         "Drag a CSV or Excel file onto the dotted box, or click it to browse."],
        ["Don't have a file?",
         "Press <b>CSV Template</b> to download a blank one with the right column headings."],
    ], widths=[122, CONTENT_W - 122])]

    story += [H3("What you get back")]
    story += [whatyousee([
        ["The five boxes across the top",
         "How many rows were checked, how many predicted a failure, the average health, how "
         "many were critical, and how many different machines were in the file."],
        ["PREDICTED CLASS DISTRIBUTION",
         "A bar per outcome showing how many rows fell into each - usually mostly Normal "
         "with a minority of one failure type."],
        ["HEALTH ACROSS THE FILE",
         "The health score plotted for every row in order. On a machine that fails, this is "
         "a line sliding from the top of the chart to the bottom."],
        ["The table at the bottom",
         "Every row with its own verdict. The filter buttons above it (All, CRITICAL, "
         "WARNING, ADVISORY, NORMAL) narrow it down."],
        ["Annotated CSV button",
         "Downloads your original file with all the results added as extra columns, ready "
         "to open in Excel."],
    ])]
    story += [callout(
        "One row with a typo will not ruin your upload",
        "If a row has a missing or nonsensical value, the system scores all the other rows "
        "normally and lists the bad ones separately - telling you the row number as it "
        "appears in Excel, so you can go and fix it. It also understands several different "
        "spellings of the column headings, so you usually do not need to rename anything.",
        "info")]
    story += [PageBreak()]

    # ============================================================ SCREEN 5
    story += [H2("3.5  Screen 5  -  Alarms")]
    story += [P(
        "<b>The to-do list.</b> Every alarm the system has raised, newest first, with what "
        "should be done about it and a way to tick it off.")]
    story += figure("15_alarms", "Figure 5 - The alarm and maintenance log.")

    story += [whatyousee([
        ["Time", "When the alarm was raised."],
        ["Machine", "Which machine. Click the name to jump straight to its screen."],
        ["Level", "How serious - the usual four colours."],
        ["Mechanism", "Which of the four failures."],
        ["Message & Action",
         "What happened, and underneath in grey, what the technician should do about it."],
        ["Health / RUL", "The machine's condition at the moment the alarm was raised."],
        ["The Acknowledge button",
         "Ticks the alarm off. The row fades and records who acknowledged it. "
         "<b>Acknowledge All</b> clears the whole list at once."],
    ])]

    story += [callout(
        "Why the list is short",
        "A machine sitting in a critical state for four hours could easily generate 24 "
        "identical alarm entries. This system writes one entry per <b>event</b> - it only "
        "adds a new line when the situation actually changes. That is what keeps the list "
        "readable and makes the “open alarms” count mean something.", "ok")]
    story += [PageBreak()]

    # ============================================================ SCREEN 6
    story += [H2("3.6  Screen 6  -  Model Insights")]
    story += [P(
        "<b>The evidence screen.</b> Everything on the other screens is the system telling "
        "you what it thinks. This screen is the system showing you why you should believe "
        "it. You do not need to understand the statistics to get the point of it.")]
    story += figure("16_model_insights", "Figure 6 - The Model Insights screen.")

    story += [H3("The first panel is the one that matters")]
    story += figure("16_model_insights", "The early-warning panel.",
                    crop=(0, 0.11, 1, 0.32))
    story += [P(
        "Most systems of this kind lead with their accuracy score. This one deliberately "
        "leads with <b>how much warning it gives</b>, because that is the thing the project "
        "exists to provide.")]
    story += [whatyousee([
        ["Mean lead time",
         f"On average it warns {EW['mean_lead_readings']} readings - "
         f"{EW['mean_lead_hours']} hours of machine time - before the failure."],
        ["Machines warned before failure",
         f"{EW['warned_before_failure_pct']}% of the {EW['machines_evaluated']} test "
         "machines got a warning in time. These were machines the system had never seen "
         "while it was learning."],
        ["Prediction horizon",
         "The size of the window it was trained to look ahead over."],
        ["The four bars underneath",
         "How much warning it gives for each of the four failure types separately."],
        ["The paragraph at the bottom",
         "An honest note explaining that an earlier version of this system scored a higher "
         "accuracy of 98.99% and was <b>useless</b>, because it only noticed the fault "
         "37 minutes <i>after</i> it happened."],
    ])]

    story += [H3("The rest of the screen")]
    story += [table([
        ["Panel", "What it is telling you, plainly"],
        ["Four metric boxes",
         "Standard scores out of 1. Higher is better. “Balanced accuracy” is the "
         "fairest one here, because breakdowns are rare and a system that simply said "
         "“fine” every time would still score well on plain accuracy."],
        ["Per-class performance",
         "How well it does on each failure type. The column to watch is <b>Recall</b> - the "
         "share of real problems it catches. Missing a breakdown is far more costly than "
         "investigating one that turns out to be fine."],
        ["Confusion matrix",
         "A grid of what it predicted against what was true. Green squares down the diagonal "
         "are correct answers; red squares off it are confusions. You want a strong green "
         "diagonal."],
        ["Feature importance",
         "Which of the measurements the system found most useful. The ones tagged PHYSICS "
         "are quantities calculated from the raw readings - and the fact that they dominate "
         "means the system worked out the underlying engineering by itself."],
        ["Learning curve",
         "Shows whether giving it more data would help. The two lines flattening and coming "
         "together means it has enough."],
        ["Explainability self-check",
         "This one runs live the moment you open the screen. It re-checks that the "
         "explanations on the Manual Input screen genuinely reproduce the system's own "
         "reasoning. A green YES means they can be trusted; the error figure is essentially "
         "zero."],
        ["The grid of pictures at the bottom",
         "Nine analysis charts produced while the system was being built. Click any one to "
         "see it full size."],
    ], widths=[112, CONTENT_W - 112])]
    story += [PageBreak()]

    # ============================================================ PART 4
    story += [H1("Part 4  -  Reference")]

    story += [H2("4.1  A five-minute tour to show someone else")]
    story += [P("If you have five minutes and someone to impress, do exactly this.")]
    story += [table([
        ["", "Do this", "Say this"],
        ["1", "Plant Overview → press <b>Start Demo Plant</b>",
         "“Four machines have just started. Each is replaying the real recorded life "
         "of an actual machine, right up to the moment it broke.”"],
        ["2", "Wait about a minute and watch the cards",
         "“Nothing to do yet. Everything is green because these machines are early in "
         "their life.”"],
        ["3", "Click the machine that turns amber or red first",
         "“That one is developing a fault. The cards sort themselves so the worst is "
         "always top-left.”"],
        ["4", "Point at the status line, then the alarm banner",
         "“It says the machine will fail from overheating - and that it first warned us "
         "78 readings, about 13 hours, before it actually did.”"],
        ["5", "Point at the PREDICTED badge",
         "“That badge is the whole point. The machine is still running fine. This is a "
         "forecast, not a report of damage.”"],
        ["6", "Scroll to the Ground Truth panel",
         "“And here it shows us the real answer next to its own prediction, so we can "
         "check its work rather than take its word.”"],
        ["7", "Go to Manual Input → press <b>Approaching heat failure</b>",
         "“I can also type in readings by hand. One click, and it is 92% sure this "
         "machine is heading for a cooling problem.”"],
        ["8", "Point at the “Why” panel on the right",
         "“And it tells us why: the temperature gap is the main reason. Those numbers "
         "add up exactly to its answer - it is not guessing at an explanation "
         "afterwards.”"],
        ["9", "Go to Model Insights, top panel",
         "“Across 42 machines it had never seen before, it gave an average of 8.7 hours "
         "of warning and caught 97.6% of them in time.”"],
    ], widths=[16, 152, CONTENT_W - 168])]

    story += [H2("4.2  Questions people usually ask")]

    qa = [
        ("Is it actually connected to a real machine?",
         "No, and the project is explicit about that. It runs on real recorded measurements "
         "from a published industrial dataset - 10,000 genuine records of machines that "
         "really did fail. Building it this way means the results can be measured and "
         "checked. The system is designed so that a real sensor could be plugged in later "
         "without changing anything else."),
        ("What does a “reading” actually correspond to in real time?",
         "One reading is one set of measurements taken every 10 minutes. So 6 readings is an "
         "hour of machine time. When the screen says it warned 78 readings ahead, that is "
         "13 hours of real machine operation."),
        ("Why is the accuracy only 90%? That sounds low.",
         "Because it was deliberately traded away for something more valuable. An earlier "
         "version scored 98.99% - and was worthless, because it only recognised a fault "
         "after it had happened. Asking the harder question, “is this machine on its way "
         "to failing?”, is genuinely more difficult and scores lower, but it is the "
         "question worth answering."),
        ("It sometimes warns when nothing is wrong. Isn't that a problem?",
         "It was investigated carefully. Of the readings that look like false alarms, 84% "
         "turned out to be on machines that genuinely did fail later - the system had simply "
         "spotted the problem even earlier than expected. Only about one in ten is a true "
         "nuisance. In maintenance, an unnecessary inspection is far cheaper than a missed "
         "breakdown."),
        ("Can I trust the explanations, or are they made up afterwards?",
         "They are mathematically exact, and the system proves it to you. Open Model "
         "Insights and look at the self-check panel: it re-derives every prediction from its "
         "explanation and compares. The disagreement is about 0.0000000000000004."),
        ("Does it need the internet?",
         "No. Nothing is downloaded and nothing is sent anywhere. It runs entirely on the "
         "computer in front of you."),
        ("What happens if the computer model is wrong?",
         "Two independent checks run alongside it that are pure arithmetic on the "
         "measurements, not learned from data. If a physical limit is crossed, they raise "
         "the alarm regardless of what the model believes."),
        ("Why is one machine's remaining life shown as STABLE instead of a number?",
         "Because it is not degrading. Rather than print a large invented figure, the system "
         "says plainly that it can see no downward trend."),
    ]
    for q, a in qa:
        story += [KeepTogether([
            Paragraph(f"<b>{esc(q)}</b>", STYLES["body_left"]),
            Paragraph(esc(a), STYLES["body"]),
            spacer(3),
        ])]

    story += [H2("4.3  Glossary")]
    story += [table([
        ["Term", "Meaning"],
        ["Alarm band", "One of four seriousness levels: Normal, Advisory, Warning, Critical."],
        ["Confidence", "How sure the system is, as a percentage."],
        ["Cycle", "The count of readings since a machine started its life."],
        ["Ground truth", "What really happened, known from the recording - used to check "
         "the system's answer."],
        ["Health index", "Condition score out of 100. 100 is perfect, 0 has failed."],
        ["HDF", "Heat Dissipation Failure - the machine cannot shed its heat."],
        ["HMI", "Human-Machine Interface - the industry term for an operator's screen."],
        ["Kelvin (K)", "A temperature scale used in engineering. 300 K is about 27 °C."],
        ["Lead time", "How far in advance the warning arrives."],
        ["Nm (newton-metre)", "The unit of torque - twisting force."],
        ["OSF", "Overstrain Failure - too much force through a worn tool."],
        ["Prediction horizon", "The window of time the system was trained to look ahead over "
         "- 15 readings, about 2.5 hours."],
        ["PWF", "Power Failure - the spindle motor is drawing too much or too little power."],
        ["Reading", "One complete set of the five measurements, taken every 10 minutes."],
        ["Recall", "The share of real problems the system catches."],
        ["rpm", "Revolutions per minute - how fast something spins."],
        ["RUL", "Remaining Useful Life - how long before failure is expected."],
        ["Stress", "How close a machine is to a particular limit, as a percentage."],
        ["Tool wear", "Minutes of use on the cutting tool. Tools are changed near 200 min."],
        ["TWF", "Tool Wear Failure - the milling cutter (end mill) has gone blunt."],
        ["Variant (L/M/H)", "The grade of product being made: Low, Medium or High quality."],
    ], widths=[112, CONTENT_W - 112])]

    story += [spacer(14)]
    story += [callout(
        "If you remember only one thing",
        "A <b>PREDICTED</b> badge means the machine is still running and you have time to "
        "act. A <b>LIMIT BREACHED</b> badge means it has already happened. On average there "
        f"are about <b>{EW['mean_lead_hours']} hours</b> between the two - and that gap is "
        "what this entire project was built to create.", "ok")]

    doc = Report(OUT, "User Interface Guide", "Document 3 - User Interface Guide")
    doc.build(story)
    print(f"written: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    build()
