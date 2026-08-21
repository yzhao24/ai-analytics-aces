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

4: """Here's the whole product in one line.

Two things go in. The hourly meter file the manager already has — and real
temperature, pulled from a free weather API. Nobody installs a sensor.

Then two baselines. The detector's is deliberately weather-blind — it stands in
for the threshold alarm the manager already gets today. The agent's is
weather-matched: it rebuilds the comparison from hours at the same temperature,
then runs a significance test on the difference.

And one record out. Claude names one of fourteen causes, and seven fields come
back — the explanation, the next step, and the symptom for the technician.
Dispatch, monitor, or dismiss.

The gap between those two baselines is the entire product. Let me show you.""",

5: "",

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

Correctness. Right class on twelve of fourteen, subtype on only seven. Both class
errors are the same shape — a busy day and a rented fleet, each read as a fault.
That isn't a bad prompt: shift schedules aren't an input we receive, so nothing
separates a busy shift from a stuck compressor on kilowatt-hours alone.

Calibration. Confidence averages point-seven-zero when right, point-seven-five
when wrong — though that second figure is the mean of two cases. The honest
reading is the distributions overlap, so confidence tells you nothing.

And the third — decision value — turned out not to be about the tool at all.""",

8: """We priced the tool against dispatching to every spike — three hundred
dollars a visit, two thousand for a fault you miss.

Follow our tool: thirty-five thousand two hundred. Dispatch on everything: seven
and a half. We are four point seven times worse than the dumbest possible policy,
and that is what this deck said until four days ago.

Then we asked where those twenty-five alarms came from. Our detector raises five
hundred and sixty-two a year. Only the twenty-five matching a planted anomaly were
ever scored — we deleted ninety-six percent of the problem before measuring. And
triaging five hundred alarms down to the twenty worth acting on is the entire job.

That deletion is what makes blanket dispatch look cheap. On twenty-five alarms it
costs seven and a half thousand. On five hundred and sixty-two, a hundred and
sixty-eight thousand.

So we classified a hundred of the alarms we had been throwing away, for two
dollars forty. Against the population this product would really face, following it
saves about a hundred and thirty-four thousand dollars a year.

The number on the left is real. It is just not a measurement of the product.""",

9: """Two of us audited this independently. These are the limits, said out loud.

One. It cannot tell a busy day from a broken compressor. Shift schedules,
throughput and rentals all move electricity, and none is an input. That's Theory
B, and it's real.

Two — the one I'd want to know if I were you. Our own specification said that if
this appeared, the fix was to require shift schedule data. We built it, and
precision fell from eighty-two to sixty-four percent. A busy day adds seven to
ten kilowatt-hours; the alarm doesn't fire until twenty, so it never reaches the
detector. A second fix cost us recall. We merged neither.

Three. Don't trust the confidence as a probability. It carries no usable signal
about correctness — and don't build a dispatch gate on it, which is exactly what
we did.

Four. Everything is synthetic: real temperature, generated consumption, no
maintenance logs.

Five. Our classifier has never faced a false alarm. The detector raises five
hundred sixty-two a year and only twenty-five are scored — so precision says
nothing about telling a real event from a false one, and that's the harder
job.""",

10: """If this shipped Monday, here is how we would watch it.

The best signal is the one the product generates about itself — the exception
notes. Every time a manager says none of these three fit, we capture why. A reason
that recurs is a missing fifteenth cause. Alongside it: dispatch outcomes, how
many spikes clear the gate, and input-guard findings per upload.

We also wrote down what would make us pull it — precision under sixty percent over
thirty days, exceptions over twenty percent, or any month the tool costs more than
dispatching on everything.

And what we would build first is not a better prompt. It is to finish the
measurement we started four days ago: score the other four hundred and
thirty-seven alarms, then tune the dispatch threshold on that population. Worth
noting — the break-even our own cost model implies is zero point one five, and it
is worse than the threshold we ship, because confidence is not a calibrated
probability and cannot be dropped into that formula.""",

11: """Where we landed.

The classifier works. Our measurement of it nearly did not.

Eighty-two percent precision was measured on planted events. Against the alarms
this product would really face it is nearer ten percent — a much less flattering
number, and the true one. And it is still worth deploying: following it saves
roughly a hundred and thirty-four thousand a year against dispatching on
everything.

We found that four days ago, by testing it on the alarms we had spent the whole
project discarding. We very nearly stood here and told you the opposite.

Questions — especially about the failures."""
}


def timing():
    """(speaker, seconds) per slide, measured from the script itself."""
    return {n: (who, DEMO_SECONDS if n == 5
                else max(10, round(len(SCRIPT[n].split()) / WPM * 60)))
            for n, who in SPEAKERS.items()}


def notes_for(n):
    """What goes in the slide's notes pane: how to deliver it, then what to say."""
    parts = []
    if COACHING.get(n):
        parts.append(COACHING[n].strip())
    if SCRIPT.get(n, "").strip():
        parts.append("─" * 74)
        parts.append(SCRIPT[n].strip())
    return "\n\n".join(parts)


# How to deliver it. Never counted toward the time budget — SCRIPT is the clock.
COACHING = {

4: """THE SPINE — memorise these four lines and you cannot get lost:

      Two things in.
      Two baselines.
      One record out.
      The gap between the two baselines is the product.

Walk the boxes left to right; the slide is your prompt. If you blank, say the
spine and move on — the detail is decoration.

THE TWO WORDS THAT DO THE WORK: weather-BLIND and weather-MATCHED. They are on
the slide, they are the whole contrast, and they set up ANO-2010 in the demo,
where the blind baseline alarms and the matched one scores z = minus 0.04.

RUNNING LONG? Cut to 30 seconds:
  "Two things go in — the meter file the manager already has, and real
   temperature from a free API. Then two baselines: the detector's is
   deliberately blind to weather, the agent's is matched to it. One record comes
   out — one of fourteen causes, seven fields, dispatch, monitor or dismiss. The
   gap between those two baselines is the entire product."
""",

5: """[THE DEMO — play the recording. These are the beats it contains, so you can
introduce it and pick it up cleanly. Full script in DEMO_SCRIPT.md.]

Say first, out loud: "What you are about to see is a screen recording, made on this
machine. It is not a live run." The assignment requires you to label it.

  0:15  Orientation. 12 months hourly, 3 facilities, 9 sub-systems, 25 flagged hours.

  0:40  ANO-2000 — it works. Refrigeration Zone A at 4am, 122.5 kWh above a 61.1
        baseline, three times normal for three hours at 48 degrees, z = 29.5.
        Compressor fault, 0.78, dispatch — with a symptom for the technician.

  0:45  ANO-2010 — the agent earns its keep. Midnight HVAC, 21.4 above baseline, and
        the building system flags it. The agent rebuilds the baseline from hours at
        the same temperature and scores it z = minus 0.04 — not significant. It was a
        warm July night. This is the only case where the agent overturns the detector;
        everything else scores above 20.

  0:30  ANO-2009 — it fails. Compressor Bank, eight hours at 2.1x, called a compressor
        fault at 0.78. It was a peak throughput day.

  0:25  Guardrails. A file in watts instead of kilowatts caught on upload, and an
        exception recorded when none of the three actions fit.

HAND OFF: "That's the product working, and one case it gets wrong. Cindy will tell
you how we decided whether it works well."\
"""
}


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
