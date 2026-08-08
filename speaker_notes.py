"""
The spoken script for the final presentation, and the time budget it fits.

Five speakers, landing at about ten minutes with a two-minute demo. TIMING is
measured from the script at 140 words a minute, not aspirational — the numbers
printed on the slides are what these blocks actually take to say.

build_final_deck.py stamps both onto the slides and build_speech_doc.py prints
them as cue cards, so the deck and the script cannot drift apart.

    python3 speaker_notes.py       # script length vs. budget, and the total
"""

WPM = 140

DEMO_SECONDS = 120          # slide 5 is performed, not read

SPEAKERS = {1: "Helen", 2: "Helen", 3: "Helen", 4: "Yun", 5: "Yun", 6: "Cindy",
            7: "Nathanael", 8: "Nathanael", 9: "Alfreda", 10: "Alfreda", 11: "Yun"}

SCRIPT = {

1: """Good afternoon — we're the AI Analytics Aces.

An operations manager sees an unexplained spike on the electricity meter. One
question follows: do I send a technician? Today that answer takes one to three
days. We built something that answers it in ten seconds — and we'll show you
where it still fails.""",

2: """Our stakeholder is one named role: the operations manager at a distribution
center over a hundred thousand square feet.

Diagnosing a single spike takes one to three business days, because it takes a
facilities engineer, at five hundred to two thousand dollars a call. They get
three to five a month per facility — thirty to fifty open events across ten
facilities.

The third number shaped everything we built. A needless dispatch costs three
hundred dollars; a missed refrigeration fault runs into five figures once you
count spoiled inventory. A hundred-and-sixty-seven-to-one ratio. Missing a fault
is far worse than over-reacting.

Add it up: sixty to two hundred forty thousand dollars a year, avoidable.

And the decision is narrow — dispatch, monitor, or dismiss, inside the same
shift, without calling an engineer.""",

3: """Before we built anything we wrote down two rival explanations and the
evidence that would separate them.

Theory A: spikes carry real diagnostic signal — timing against the shift,
magnitude against the facility's own history, duration. If A holds, the product
works.

Theory B: operational variation is indistinguishable from faults on
kilowatt-hours alone. A busy day, an overtime shift, a hot afternoon — all of
them just look like more electricity. If B holds, the product displaces
judgment it can't replicate and makes decisions worse.

So we fixed a bar in advance: precision at least seventy-five percent, recall at
least seventy, against held-out labels. Everything after this reports against
that bar.""",

4: """Here's the whole product.

Hourly kilowatt-hours come in — the file the manager already has. We pair it
with real hourly temperature from a free weather API, so nobody installs a
sensor.

A detector flags spikes, and it's deliberately weather-blind: it stands in for
the threshold alarm the manager already gets.

Then an agent runs four real tools — pulls the window around the spike, builds a
baseline from hours at a similar temperature, runs a significance test, finds
comparable past events.

Claude turns that into one of fourteen causes, locked to a schema. Seven fields
come back, every one actionable. Let me show you.""",

5: """[THE DEMO — play the recording. These are the beats it contains, so you can
introduce it and pick it up cleanly at the end. Full script in DEMO_SCRIPT.md.]

Say first: "This is a recording, made on this machine."

  0:15  Orientation. 12 months hourly, 3 facilities, 9 sub-systems, red dots.

  0:45  ANO-2000 — it works. Refrigeration Zone A, 4am, 122.5 kWh against a 61.1
        baseline, double for three hours at 48 degrees. Compressor fault, 0.78,
        dispatch — with a symptom a refrigeration tech can act on.

  0:35  ANO-2012 — it saves the trip. Lighting Grid South at 3.75x normal, the
        scariest number in the set. The hour before recorded almost nothing, so
        the meter dropped out and caught up. Meter dropout, 0.88, dismiss.

  0:30  ANO-2009 — it fails. Compressor Bank, eight hours at 1.15x. Called a
        compressor fault at 0.78; it was a peak throughput day.

  0:25  Guardrails. A file in watts instead of kilowatts caught on upload, and an
        exception recorded when none of the three actions fit.

HAND OFF: "That's the product working, and one case it gets wrong. Cindy will tell
you how we decided whether it works well."\
""",

6: """This is the slide audiences skip, and it's where most AI projects fail —
the output is fluent, nobody defined "good," and the audience finds the error.

One output equals one classified spike. Five criteria, every threshold fixed
before we saw a result. The one to notice is Calibration: commit when right,
hedge when wrong — and a wrong label at high confidence fails the case outright.

The question you should ask is whether we're using a model to grade a model. For
four of the five, no — string matches against labels the classifier never sees,
field checks, and a timer. Usability is the one real judgment call, so two of us
score it blind. An LLM judge says thirteen of fourteen; we won't quote that
until the human scores land.""",

7: """Results — and I'll spend most of my time on the failures.

The top row answers Helen's test. Precision eighty-two percent against a
seventy-five percent bar. Recall one hundred percent against seventy — we missed
no real fault. Ten seconds a case. By the standard we set in advance, Theory A
cleared its bar.

And three criteria still failed.

Correctness. Right class on twelve of fourteen, right subtype on only seven.
Both class errors are the same shape — a peak throughput day and a rented
equipment fleet, each read as a fault. That isn't a bad prompt: shift schedules
and rental logs aren't inputs we receive, so nothing separates a busy shift from
a stuck compressor on kilowatt-hours alone. A specification failure — Theory B,
exactly where it said it would be.

Calibration. Confidence averages point-seven-zero when right and
point-seven-five when wrong. Inverted, not just noisy — that's the model, not
our data.

The third one is worth your attention.""",

8: """We didn't stop at precision and recall. We priced the tool against two
policies you could follow with no AI at all — three hundred dollars a dispatch,
two thousand for a fault you miss, across twenty-five anomalies.

Follow our tool: four technicians sent, three of twenty faults caught,
thirty-five thousand two hundred dollars. Dispatch on every spike — no model, no
judgment — seven thousand five hundred.

We are four-point-seven times worse than the dumbest possible policy.

Ninety-seven percent of that isn't money spent, it's exposure — twelve hundred
dollars out the door and thirty-four thousand of faults left uninvestigated.
Only four of twenty-five spikes clear the point-seven-five gate, so seventeen of
twenty real faults get told to "monitor" and nobody goes.

The lesson: we built for "what is this spike?" The decision needs "should I
dispatch?" A rubric that stopped at precision and recall would have let us stand
here and call this a success.""",

9: """Two of us audited this independently. These are the limits, said out loud.

One. It cannot tell a busy day from a broken compressor. Shift schedules,
throughput and rentals all move electricity, and none is an input. That's Theory
B, and it's real.

Two — the one I'd want to know if I were you. Our own specification said that if
this appeared, the fix was to require shift schedule data. We built it, and
precision fell from eighty-two to sixty-four percent. A busy day adds seven to
ten kilowatt-hours; the alarm doesn't fire until twenty, so it never reaches the
detector. A second fix cost us recall. We merged neither.

Three. Don't trust the confidence as a probability — it's inverted. And don't
build a dispatch gate on it, which is exactly what we did.

Four. Everything is synthetic: real temperature, generated consumption, no
maintenance logs.

Five. Our classifier has never faced a false alarm. The detector raises five
hundred sixty-two a year and only twenty-five are scored — so precision says
nothing about telling a real event from a false one, and that's the harder
job.""",

10: """If this shipped Monday, here's how we'd watch it.

The best signal is the one the product generates about itself — the exception
notes. Every time a manager says none of these three fit, we capture why. A
reason that recurs is a missing fifteenth cause, and both misclassifications
would have surfaced that way. Alongside it: dispatch outcomes, how many spikes
clear the gate, and input-guard findings per upload.

We also wrote down what would make us pull it — precision under sixty percent
over thirty days, exceptions over twenty percent, or any month the tool costs
more than dispatching on everything.

And what we'd build first isn't a better prompt. It's the dispatch rule: replace
the fixed gate with an expected-cost rule using that
hundred-and-sixty-seven-to-one ratio. The labels are already good enough — the
decision layer on top of them is losing the money.""",

11: """Where we landed.

Theory A cleared the bar we set in advance. Theory B was right about where the
confusion lives — and we can say exactly where, because we tried the fix our own
specification prescribed and measured it failing.

We built a good classifier. We have not yet built a good product. The gap
between those is a dispatch rule, and it's the first thing we'd build.

Questions — especially about the failures.""",
}


def timing():
    """(speaker, seconds) per slide, measured from the script itself."""
    return {n: (who, DEMO_SECONDS if n == 5
                else max(10, round(len(SCRIPT[n].split()) / WPM * 60)))
            for n, who in SPEAKERS.items()}


def check():
    total = 0
    print("  #   speaker      time")
    for n, (who, secs) in sorted(timing().items()):
        words = len(SCRIPT[n].split())
        spoken = secs
        total += secs
        note = "  (demo, not read aloud)" if n == 5 else f"({words:3} w)"
        print(f"  {n:2}  {who:11} {secs:4}s  {note}")
    print(f"\n  TOTAL {total // 60}:{total % 60:02d}  across "
          f"{len(set(SPEAKERS.values()) - {'All'})} speakers")


if __name__ == "__main__":
    check()


TIMING = timing()
