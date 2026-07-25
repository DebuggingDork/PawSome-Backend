"""The cast for scripts/seed_realistic_data.py — people, pets and conversations.

Pure data, no logic, so it can be edited without touching the seeding pipeline.

Everything is set in Hyderabad with real neighbourhood names and real
coordinates, so distance-based matching produces believable numbers instead of
the arbitrary ones you get from scattered test points.

Emails deliberately use @example.com (RFC 2606 reserved). The app sends
verification and password-reset mail, and pointing seed accounts at plausible
gmail.com addresses would mean mailing strangers.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Area:
    """A real Hyderabad locality. lat/lng are the actual coordinates."""

    label: str
    pincode: str
    lat: float
    lng: float


@dataclass(frozen=True)
class PhotoSource:
    """Where to pull breed-accurate photos from.

    kind 'dog'  -> dog.ceo, ref is the breed path e.g. 'retriever/golden'
    kind 'cat'  -> TheCatAPI, ref is the breed id e.g. 'pers'
    """

    kind: str
    ref: str


@dataclass(frozen=True)
class Pet:
    name: str
    species: str  # dog | cat
    breed: str
    source: PhotoSource
    age_months: int
    gender: str  # male | female
    bio: str
    photo_count: int = 3
    is_vaccinated: bool = True
    is_neutered: bool = False
    is_trained: bool = False


@dataclass(frozen=True)
class Person:
    full_name: str
    email: str
    occupation: str
    bio: str
    area: int  # index into AREAS
    avatar: int  # i.pravatar.cc image id, unique per person
    radius_km: float
    pets: list[Pet] = field(default_factory=list)


# ── Localities ────────────────────────────────────────────────────────────────
AREAS = [
    Area("Balaji Hills, Boduppal", "500092", 17.4021, 78.5977),
    Area("Brindavan Colony, Boduppal", "500092", 17.4055, 78.6012),
    Area("Street No. 8, Habsiguda", "500007", 17.4062, 78.5442),
    Area("Street No. 3, Habsiguda", "500007", 17.4041, 78.5478),
    Area("Road No. 36, Jubilee Hills", "500033", 17.4310, 78.4070),
    Area("Road No. 10, Jubilee Hills", "500033", 17.4239, 78.4138),
    Area("Sai Nagar, Vanasthalipuram", "500070", 17.3305, 78.5606),
    Area("BN Reddy Nagar, Vanasthalipuram", "500070", 17.3268, 78.5651),
    Area("Ayyappa Society, Madhapur", "500081", 17.4483, 78.3915),
    Area("Indira Nagar, Gachibowli", "500032", 17.4401, 78.3489),
    Area("Botanical Garden Road, Kondapur", "500084", 17.4640, 78.3620),
    Area("KPHB Phase 6, Kukatpally", "500072", 17.4948, 78.3996),
    Area("Road No. 12, Banjara Hills", "500034", 17.4126, 78.4482),
    Area("Prakash Nagar, Begumpet", "500016", 17.4400, 78.4600),
    Area("Ramanthapur Road, Uppal", "500039", 17.4058, 78.5590),
    Area("West Marredpally, Secunderabad", "500026", 17.4483, 78.5010),
    Area("Hafeezpet, Miyapur", "500049", 17.4924, 78.3520),
    Area("SR Nagar, Ameerpet", "500038", 17.4374, 78.4487),
    Area("Kothapet, LB Nagar", "500074", 17.3457, 78.5522),
    Area("Serilingampally, Nallagandla", "500019", 17.4665, 78.3120),
    Area("Puppalaguda, Manikonda", "500089", 17.4023, 78.3776),
    Area("Vidyanagar, Tarnaka", "500017", 17.4256, 78.5273),
    Area("Venkatapuram, Alwal", "500010", 17.5017, 78.5000),
    Area("Kapra, Sainikpuri", "500094", 17.4936, 78.5522),
    Area("Bachupally Road, Nizampet", "500090", 17.5100, 78.3900),
]


# ── The cast ──────────────────────────────────────────────────────────────────
# PEOPLE[0] is the demo account: three pets, the most matches, unread
# notifications and live chat threads. Sign in as this one to see everything.
PEOPLE = [
    Person(
        full_name="Arjun Reddy",
        email="arjun.reddy@example.com",
        occupation="Product Designer",
        bio="Design by day, dog park by evening. You'll usually find me at the "
        "Boduppal ground around 6pm with all three of mine in tow.",
        area=0,
        avatar=12,
        radius_km=25,
        pets=[
            Pet(
                "Simba", "dog", "Golden Retriever", PhotoSource("dog", "retriever/golden"),
                30, "male",
                "Certified good boy. Obsessed with tennis balls, terrified of the vacuum. "
                "Gets along with absolutely everyone.",
                photo_count=5, is_neutered=True, is_trained=True,
            ),
            Pet(
                "Kaju", "dog", "Beagle", PhotoSource("dog", "beagle"),
                18, "female",
                "Nose first, questions later. If there's a biscuit within 500 metres, "
                "she has already found it.",
                photo_count=4, is_trained=True,
            ),
            Pet(
                "Meesha", "cat", "Persian", PhotoSource("cat", "pers"),
                42, "female",
                "Runs the house. Tolerates the dogs on her own terms and naps in whichever "
                "sunbeam is currently best.",
                photo_count=3, is_neutered=True,
            ),
        ],
    ),
    Person(
        full_name="Sneha Iyer",
        email="sneha.iyer@example.com",
        occupation="Pediatric Dentist",
        bio="Long clinic hours, so weekends belong entirely to these two. Looking for "
        "calm playmates around Habsiguda.",
        area=2,
        avatar=5,
        radius_km=15,
        pets=[
            Pet(
                "Coco", "dog", "Pomeranian", PhotoSource("dog", "pomeranian"),
                24, "female",
                "Three kilos of pure opinion. Loves company, hates being picked up "
                "without asking first.",
                photo_count=4, is_neutered=True, is_trained=True,
            ),
            Pet(
                "Pista", "cat", "Bengal", PhotoSource("cat", "beng"),
                20, "male",
                "Climbs everything. Has never once used the floor when a bookshelf "
                "was available.",
                photo_count=3,
            ),
        ],
    ),
    Person(
        full_name="Rahul Verma",
        email="rahul.verma@example.com",
        occupation="Backend Engineer",
        bio="Work from home means these two supervise every standup. Happy to meet up "
        "around Jubilee Hills on weekends.",
        area=4,
        avatar=13,
        radius_km=30,
        pets=[
            Pet(
                "Bruno", "dog", "Labrador Retriever", PhotoSource("dog", "labrador"),
                36, "male",
                "Will trade his entire soul for a piece of roti. Swims in anything "
                "deeper than a puddle.",
                photo_count=4, is_neutered=True, is_trained=True,
            ),
            Pet(
                "Oreo", "cat", "British Shorthair", PhotoSource("cat", "bsho"),
                28, "male",
                "Professionally unimpressed. Will sit near you but never quite on you.",
                photo_count=3, is_neutered=True,
            ),
        ],
    ),
    Person(
        full_name="Ayesha Fatima",
        email="ayesha.fatima@example.com",
        occupation="Architect",
        bio="Sketching buildings all week, walking Sheru all evening. Vanasthalipuram "
        "regular at the park near BN Reddy Nagar.",
        area=6,
        avatar=9,
        radius_km=20,
        pets=[
            Pet(
                "Sheru", "dog", "German Shepherd", PhotoSource("dog", "german/shepherd"),
                48, "male",
                "Serious face, complete softie. Trained, calm, and very protective of "
                "the smaller dogs at the park.",
                photo_count=4, is_neutered=True, is_trained=True,
            )
        ],
    ),
    Person(
        full_name="Karthik Rao",
        email="karthik.rao@example.com",
        occupation="Data Analyst",
        bio="Numbers by day, zoomies by night. Milo has more energy than my entire team.",
        area=8,
        avatar=14,
        radius_km=25,
        pets=[
            Pet(
                "Milo", "dog", "Siberian Husky", PhotoSource("dog", "husky"),
                22, "male",
                "Talks back constantly. Needs a running partner who can actually keep up.",
                photo_count=4, is_trained=True,
            )
        ],
    ),
    Person(
        full_name="Divya Menon",
        email="divya.menon@example.com",
        occupation="Physiotherapist",
        bio="I fix people's backs and Laddu undoes all my work by sleeping on me. "
        "Worth it.",
        area=10,
        avatar=16,
        radius_km=18,
        pets=[
            Pet(
                "Laddu", "dog", "Pug", PhotoSource("dog", "pug"),
                33, "male",
                "Snores louder than a ceiling fan. Short walks, long naps, endless cuddles.",
                photo_count=3, is_neutered=True,
            )
        ],
    ),
    Person(
        full_name="Vikram Choudhary",
        email="vikram.choudhary@example.com",
        occupation="Civil Engineer",
        bio="On site most days. Rocky comes along whenever the crew allows it — he's "
        "basically the site mascot now.",
        area=12,
        avatar=15,
        radius_km=35,
        pets=[
            Pet(
                "Rocky", "dog", "Rottweiler", PhotoSource("dog", "rottweiler"),
                40, "male",
                "Big, gentle, and deeply committed to sitting on feet. Well socialised "
                "with other large dogs.",
                photo_count=4, is_neutered=True, is_trained=True,
            )
        ],
    ),
    Person(
        full_name="Meera Nair",
        email="meera.nair@example.com",
        occupation="Content Strategist",
        bio="Remote work, two coffees, one very demanding cat. Snowy decides when the "
        "workday ends.",
        area=14,
        avatar=20,
        radius_km=15,
        pets=[
            Pet(
                "Snowy", "cat", "Ragdoll", PhotoSource("cat", "ragd"),
                26, "female",
                "Goes completely limp when picked up. Would follow a stranger home if "
                "they scratched her chin.",
                photo_count=3, is_neutered=True,
            )
        ],
    ),
    Person(
        full_name="Siddharth Jain",
        email="siddharth.jain@example.com",
        occupation="Chartered Accountant",
        bio="Filing season is brutal, so Gattu gets me through it. Evening walks around "
        "Uppal are non-negotiable.",
        area=15,
        avatar=18,
        radius_km=22,
        pets=[
            Pet(
                "Gattu", "dog", "Indie", PhotoSource("dog", "mix"),
                30, "male",
                "Rescued from the lane behind my office and never looked back. Smartest "
                "dog I've ever met.",
                photo_count=3, is_neutered=True, is_trained=True,
            )
        ],
    ),
    Person(
        full_name="Pooja Agarwal",
        email="pooja.agarwal@example.com",
        occupation="Veterinary Surgeon",
        bio="I spend all day with other people's pets and still come home to two of my "
        "own. Happy to answer health questions.",
        area=16,
        avatar=25,
        radius_km=40,
        pets=[
            Pet(
                "Tiger", "dog", "Boxer", PhotoSource("dog", "boxer"),
                27, "male",
                "Springs like he has no bones. Fully vaccinated and neutered — "
                "occupational hazard of having a vet for a parent.",
                photo_count=4, is_neutered=True, is_trained=True,
            )
        ],
    ),
    Person(
        full_name="Imran Sheikh",
        email="imran.sheikh@example.com",
        occupation="Restaurant Owner",
        bio="Kitchen from noon to midnight. Chikoo keeps the accounts company in the "
        "back office.",
        area=17,
        avatar=33,
        radius_km=20,
        pets=[
            Pet(
                "Chikoo", "dog", "Dachshund", PhotoSource("dog", "dachshund"),
                21, "female",
                "Long dog, short legs, enormous personality. Excellent at stealing "
                "naan off low tables.",
                photo_count=3,
            )
        ],
    ),
    Person(
        full_name="Lakshmi Prasad",
        email="lakshmi.prasad@example.com",
        occupation="School Teacher",
        bio="Thirty children by day, one cat by night. Rani is the calmer of the two "
        "jobs by a distance.",
        area=18,
        avatar=26,
        radius_km=12,
        pets=[
            Pet(
                "Rani", "cat", "Siamese", PhotoSource("cat", "siam"),
                36, "female",
                "Vocal about everything — dinner, doors, the general state of the world. "
                "Very affectionate once she trusts you.",
                photo_count=3, is_neutered=True,
            )
        ],
    ),
    Person(
        full_name="Rohit Kulkarni",
        email="rohit.kulkarni@example.com",
        occupation="DevOps Engineer",
        bio="On call half the month. Bunty has learned to sleep through pager alerts, "
        "which is more than I can say for myself.",
        area=19,
        avatar=52,
        radius_km=28,
        pets=[
            Pet(
                "Bunty", "dog", "Beagle", PhotoSource("dog", "beagle"),
                15, "male",
                "Still a puppy in every way that matters. Needs a patient friend who "
                "won't mind being chewed on.",
                photo_count=4,
            )
        ],
    ),
    Person(
        full_name="Nandini Sharma",
        email="nandini.sharma@example.com",
        occupation="Interior Designer",
        bio="My house is a showroom and Pixie has redesigned every sofa in it. "
        "Manikonda based.",
        area=20,
        avatar=32,
        radius_km=18,
        pets=[
            Pet(
                "Pixie", "cat", "Abyssinian", PhotoSource("cat", "abys"),
                19, "female",
                "Never still. Treats curtains as infrastructure and shoulders as "
                "parking spots.",
                photo_count=3,
            )
        ],
    ),
    Person(
        full_name="Aditya Bose",
        email="aditya.bose@example.com",
        occupation="Music Producer",
        bio="Studio in the basement, Mowgli asleep under the desk through every "
        "session. He's heard more unreleased tracks than anyone.",
        area=21,
        avatar=51,
        radius_km=25,
        pets=[
            Pet(
                "Mowgli", "dog", "Dalmatian", PhotoSource("dog", "dalmatian"),
                29, "male",
                "Endless stamina and absolutely no volume control. Best walked before "
                "the sun gets serious.",
                # dog.ceo only carries two dalmatian photos upstream.
                photo_count=2, is_trained=True,
            )
        ],
    ),
    Person(
        full_name="Zoya Begum",
        email="zoya.begum@example.com",
        occupation="Boutique Owner",
        bio="Between fittings and fabric runs, Toffee naps on the good silk. I've "
        "stopped fighting it.",
        area=22,
        avatar=28,
        radius_km=16,
        pets=[
            Pet(
                "Toffee", "cat", "Maine Coon", PhotoSource("cat", "mcoo"),
                44, "male",
                "Enormous and entirely convinced he's a lapcat. Surprisingly good with "
                "dogs he's met before.",
                photo_count=3, is_neutered=True,
            )
        ],
    ),
    Person(
        full_name="Praveen Kumar",
        email="praveen.kumar@example.com",
        occupation="Bank Manager",
        bio="Numbers all day, then Moti resets my brain on the evening walk around "
        "Sainikpuri.",
        area=23,
        avatar=54,
        radius_km=20,
        pets=[
            Pet(
                "Moti", "dog", "Labrador Retriever", PhotoSource("dog", "labrador"),
                54, "male",
                "Senior gentleman. Slow walks, strong opinions about dinner time, "
                "infinitely patient with puppies.",
                photo_count=3, is_neutered=True, is_trained=True,
            )
        ],
    ),
    Person(
        full_name="Anjali Deshmukh",
        email="anjali.deshmukh@example.com",
        occupation="HR Consultant",
        bio="Back-to-back calls all week. Julie is the only colleague who never "
        "reschedules.",
        area=24,
        avatar=27,
        radius_km=22,
        pets=[
            Pet(
                "Julie", "dog", "Cocker Spaniel", PhotoSource("dog", "spaniel/cocker"),
                25, "female",
                "Ears like curtains and a tail that never stops. Loves water, hates "
                "being brushed afterwards.",
                photo_count=4, is_neutered=True,
            )
        ],
    ),
    Person(
        full_name="Sameer Qureshi",
        email="sameer.qureshi@example.com",
        occupation="Photographer",
        bio="Half my portfolio is just Scooby in different lighting. No regrets.",
        area=1,
        avatar=57,
        radius_km=30,
        pets=[
            Pet(
                "Scooby", "dog", "Great Dane", PhotoSource("dog", "dane/great"),
                34, "male",
                "Enormous, clumsy, convinced he's a lapdog. Needs friends who won't be "
                "intimidated by the size.",
                photo_count=4, is_neutered=True, is_trained=True,
            )
        ],
    ),
    Person(
        full_name="Harika Vemuri",
        email="harika.vemuri@example.com",
        occupation="UX Researcher",
        bio="I interview people for a living and Kiara interviews every dog at the "
        "park. We're similar that way.",
        area=3,
        avatar=29,
        radius_km=15,
        pets=[
            Pet(
                "Kiara", "dog", "Shih Tzu", PhotoSource("dog", "shihtzu"),
                23, "female",
                "Tiny, fluffy, and completely fearless. Introduces herself to dogs "
                "eight times her size.",
                photo_count=3, is_neutered=True,
            )
        ],
    ),
    Person(
        full_name="Naveen Chandra",
        email="naveen.chandra@example.com",
        occupation="Logistics Manager",
        bio="I move things across the country all day and Rusty moves exactly one "
        "thing: his ball, back to me, forever.",
        area=5,
        avatar=59,
        radius_km=26,
        pets=[
            Pet(
                "Rusty", "dog", "Doberman", PhotoSource("dog", "doberman"),
                31, "male",
                "Athletic and sharp. Trained on basic commands, loves structured play "
                "more than free-for-alls.",
                photo_count=4, is_neutered=True, is_trained=True,
            )
        ],
    ),
    Person(
        full_name="Ritu Malhotra",
        email="ritu.malhotra@example.com",
        occupation="Yoga Instructor",
        bio="Morning classes in Jubilee Hills. Cookie attends every single one and "
        "has mastered exactly zero poses.",
        area=7,
        avatar=31,
        radius_km=20,
        pets=[
            Pet(
                "Cookie", "dog", "Chow Chow", PhotoSource("dog", "chow"),
                38, "female",
                "Looks like a small bear, behaves like a cat. Affectionate strictly "
                "on her own schedule.",
                photo_count=3, is_neutered=True,
            )
        ],
    ),
    Person(
        full_name="Sandeep Goud",
        email="sandeep.goud@example.com",
        occupation="Real Estate Consultant",
        bio="Site visits all week around LB Nagar. Chhotu rides shotgun for most of them.",
        area=9,
        avatar=60,
        radius_km=32,
        pets=[
            Pet(
                "Chhotu", "dog", "Indie", PhotoSource("dog", "mix"),
                26, "male",
                "Street-smart and endlessly adaptable. Great with kids, wary of loud "
                "motorcycles.",
                photo_count=3, is_trained=True,
            )
        ],
    ),
    Person(
        full_name="Kavya Srinivasan",
        email="kavya.srinivasan@example.com",
        occupation="Software Tester",
        bio="I break software for a living. Motu breaks everything else.",
        area=11,
        avatar=45,
        radius_km=18,
        pets=[
            Pet(
                "Motu", "cat", "Sphynx", PhotoSource("cat", "sphy"),
                17, "male",
                "No fur, all personality. Runs warm, demands blankets, judges everyone "
                "equally.",
                photo_count=3,
            )
        ],
    ),
    Person(
        full_name="Tarun Bhatt",
        email="tarun.bhatt@example.com",
        occupation="Sales Lead",
        bio="On the road most weeks. When I'm home it's Bella's world and I just book "
        "the walks.",
        area=13,
        avatar=61,
        radius_km=24,
        pets=[
            Pet(
                "Bella", "dog", "Golden Retriever", PhotoSource("dog", "retriever/golden"),
                20, "female",
                "Gentle, patient and a little shy at first. Warms up fast once there's "
                "a ball involved.",
                photo_count=4, is_neutered=True,
            )
        ],
    ),
]


# ── Relationship graph ────────────────────────────────────────────────────────
# Referenced as (person_index, pet_index). Written out explicitly rather than
# generated randomly so a given seed run is reproducible and the demo account
# always lands in the same state.

# Mutual likes -> a Match, both NEW_MATCH notifications, and a chat thread.
MATCHES = [
    ((0, 0), (3, 0)),   # Simba  <-> Sheru
    ((0, 0), (4, 0)),   # Simba  <-> Milo
    ((0, 0), (9, 0)),   # Simba  <-> Tiger
    ((0, 0), (18, 0)),  # Simba  <-> Scooby
    ((0, 1), (12, 0)),  # Kaju   <-> Bunty
    ((0, 2), (7, 0)),   # Meesha <-> Snowy
    ((2, 0), (6, 0)),   # Bruno  <-> Rocky
    ((2, 0), (16, 0)),  # Bruno  <-> Moti
    ((1, 0), (19, 0)),  # Coco   <-> Kiara
    ((1, 1), (23, 0)),  # Pista  <-> Motu
    ((5, 0), (10, 0)),  # Laddu  <-> Chikoo
    ((14, 0), (20, 0)), # Mowgli <-> Rusty
]

# One-way likes that haven't been reciprocated: these become unread NEW_LIKE
# notifications the recipient can still accept, so the notifications panel has
# something actionable in it.
PENDING_LIKES = [
    ((21, 0), (0, 0)),  # Cookie  -> Simba
    ((24, 0), (0, 0)),  # Bella   -> Simba
    ((13, 0), (0, 2)),  # Pixie   -> Meesha
    ((22, 0), (0, 1)),  # Chhotu  -> Kaju
    ((8, 0), (2, 0)),   # Gattu   -> Bruno
    ((17, 0), (1, 0)),  # Julie   -> Coco
    ((15, 0), (11, 0)), # Toffee  -> Rani
]

# Super Woofs — same as a like but flagged, so the badge/sort path has data.
SUPER_LIKES = [
    ((11, 0), (0, 0)),  # Rani    -> Simba
    ((19, 0), (2, 0)),  # Kiara   -> Bruno
]

# Skips, so the swipe deck isn't a perfect record of mutual affection.
SKIPS = [
    ((0, 0), (5, 0)),
    ((0, 0), (13, 0)),
    ((0, 1), (21, 0)),
    ((2, 0), (23, 0)),
    ((4, 0), (10, 0)),
]

# Chat threads, keyed by the match they belong to. `who` is 0 for the first pet
# in the MATCHES pair and 1 for the second. Minutes are offsets back from now,
# so the timeline reads correctly however long after seeding you look at it.
CONVERSATIONS = {
    ((0, 0), (3, 0)): [
        (0, "Hey! Simba and Sheru matched — yours looks like a proper gentleman 😄", 2880),
        (1, "Ha, he tries. He's very calm with smaller dogs, is Simba ok with big ones?", 2875),
        (0, "Totally fine, he's the friendliest dog on the planet. Boduppal ground around 6?", 2870),
        (1, "That works. Saturday evening suits us — Sheru is much better once it cools down.", 2861),
        (0, "Saturday 6pm it is. He'll be thrilled, he's been staring at the door all week.", 2855),
    ],
    ((0, 0), (4, 0)): [
        (1, "Milo needs a running partner and yours looks like he can keep up 🐕", 1440),
        (0, "Simba can run all day. Fair warning though, he stops for every single person.", 1435),
        (1, "Milo will just yell at him until he moves. They'll figure it out.", 1430),
        (0, "Sounds about right 😂 Which park do you use around Madhapur?", 1425),
    ],
    ((0, 0), (9, 0)): [
        (1, "Hi! I'm a vet, so apologies in advance for asking — is Simba up to date on shots?", 720),
        (0, "All good, last round was in March. I'll bring the card along.", 715),
        (1, "Perfect, no need really, just habit at this point 😅 Tiger would love a playmate.", 710),
    ],
    ((0, 1), (12, 0)): [
        (1, "Two beagles in one park. This is either brilliant or a disaster.", 300),
        (0, "Kaju will find every dropped biscuit within a kilometre. Bunty's welcome to help.", 295),
        (1, "He's 15 months and chews everything, so consider yourself warned!", 290),
    ],
    ((2, 0), (6, 0)): [
        (0, "Rocky looks like a solid guy. Bruno's a lab, so he has zero sense of personal space.", 4320),
        (1, "Rocky's used to it, he's the calmest rottweiler you'll meet. Weekend at Banjara Hills?", 4310),
        (0, "Perfect. Sunday morning before it gets hot?", 4305),
    ],
    ((1, 0), (19, 0)): [
        (0, "Coco is small but she runs the house. Kiara looks like she'd get along fine 🐾", 180),
        (1, "Kiara introduces herself to great danes without blinking, so yes 😄", 175),
    ],
}

# Notifications older than this read as history rather than something new.
READ_NOTIFICATION_AGE_MINUTES = 2880
