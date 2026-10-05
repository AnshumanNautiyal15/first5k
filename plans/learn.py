"""
"Running word" and "what today does for you" content, one per level, plus rest days.
Pure data. Every term is explained in plain language: the goal is teaching, not jargon.
Keep benefit claims honest and general; no promises about specific numbers.
"""

LEVEL_LESSONS: dict[int, dict] = {
    1: {
        "term": "Run-walk method",
        "meaning": "Mixing short jogs with walking breaks. It's how many coaches start beginners, and plenty of experienced runners use it too.",
        "benefit": "Short jogs get your heart, lungs, legs and joints used to running a little at a time, without overloading any of them.",
    },
    2: {
        "term": "Aerobic base",
        "meaning": "Your endurance foundation: how well your heart and lungs deliver oxygen to your muscles during easy effort.",
        "benefit": "Every easy minute today adds a little to your aerobic base. Everything else you'll do is built on top of it.",
    },
    3: {
        "term": "Conversational pace",
        "meaning": "A pace slow enough that you could chat in full sentences. It's the same idea as the talk test.",
        "benefit": "Running at conversational pace trains your endurance while keeping strain low, so you recover quickly and want to go again.",
    },
    4: {
        "term": "Recovery interval",
        "meaning": "The walk between jogs. It isn't a break from training, it's part of the training.",
        "benefit": "Each walk lets your breathing settle so the next jog feels doable. Over time, you'll need less recovery to bounce back.",
    },
    5: {
        "term": "Cadence",
        "meaning": "How many steps you take per minute. Short, light, quick steps tend to feel easier than long, heavy strides.",
        "benefit": "Today is a good day to try shorter steps. It can make jogging feel smoother and gentler on your knees.",
    },
    6: {
        "term": "Time on feet",
        "meaning": "Measuring your runs in minutes instead of distance. For beginners, time matters more than kilometres.",
        "benefit": "Five-minute jogs add real time on feet. Your muscles, tendons and bones are adapting to the rhythm of running.",
    },
    7: {
        "term": "Easy run (Zone 2)",
        "meaning": "Runners split effort into zones. Zone 2 is gentle and comfortable, where most of a runner's training happens.",
        "benefit": "Longer easy jogs like today's are classic Zone 2 work: the kind of effort that steadily builds stamina.",
    },
    8: {
        "term": "Capillaries & mitochondria",
        "meaning": "Capillaries are tiny blood vessels and mitochondria are the energy factories in your cells. Regular easy running helps your body build more of both.",
        "benefit": "Ten-minute jogs give your muscles a steady reason to get better at using oxygen. That's why the same pace slowly feels easier.",
    },
    9: {
        "term": "Running economy",
        "meaning": "How much energy you use to run at a given pace. Relaxed shoulders, loose hands and an upright posture all help.",
        "benefit": "Longer jogs give you time to notice and relax tension. A relaxed runner wastes less energy.",
    },
    10: {
        "term": "Steady state",
        "meaning": "Holding one comfortable effort for a long stretch, without stopping and starting.",
        "benefit": "Twenty minutes of steady running teaches your body, and your mind, that you can keep going.",
    },
    11: {
        "term": "Progressive overload",
        "meaning": "Increasing your training little by little so your body adapts without getting hurt. It's exactly what your plan has been doing.",
        "benefit": "Twenty-five minutes is the result of many small steps. One more small step and you're at your 5K.",
    },
    12: {
        "term": "PB (personal best)",
        "meaning": "Your fastest time for a distance. Your first 5K is automatically a PB, however long it takes!",
        "benefit": "Today you put everything together. Whatever your time, it's your benchmark for the future.",
    },
}

REST_LESSON = {
    "term": "Recovery & adaptation",
    "meaning": "Your body gets fitter while it rests after training, not during the run itself.",
    "benefit": "Resting lets your muscles repair and come back a little stronger. Rest days are part of the plan, not a break from it.",
}


def lesson_for(kind: str, level: int) -> dict:
    if kind == "rest":
        return REST_LESSON
    return LEVEL_LESSONS[max(1, min(12, level))]
