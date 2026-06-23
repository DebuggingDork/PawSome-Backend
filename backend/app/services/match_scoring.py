"""
Match scoring service for PawMeet.

Calculates a compatibility score (0–100) between two pet profiles based on
breed similarity, geographic distance, age compatibility, and gender preference.
"""

# Mapping of common dog breeds to their AKC breed groups.
# At least 20 breeds are included to support breed-group scoring.
BREED_GROUPS: dict[str, str] = {
    # Sporting
    "golden retriever": "sporting",
    "labrador retriever": "sporting",
    "labrador": "sporting",
    "cocker spaniel": "sporting",
    "english springer spaniel": "sporting",
    "german shorthaired pointer": "sporting",
    "vizsla": "sporting",
    "weimaraner": "sporting",
    # Hound
    "beagle": "hound",
    "dachshund": "hound",
    "greyhound": "hound",
    "basset hound": "hound",
    "bloodhound": "hound",
    "whippet": "hound",
    # Working
    "rottweiler": "working",
    "doberman pinscher": "working",
    "doberman": "working",
    "great dane": "working",
    "boxer": "working",
    "siberian husky": "working",
    "alaskan malamute": "working",
    "bernese mountain dog": "working",
    # Terrier
    "yorkshire terrier": "terrier",
    "bull terrier": "terrier",
    "boston terrier": "terrier",
    "scottish terrier": "terrier",
    "west highland white terrier": "terrier",
    "jack russell terrier": "terrier",
    # Toy
    "chihuahua": "toy",
    "pomeranian": "toy",
    "shih tzu": "toy",
    "maltese": "toy",
    "pug": "toy",
    "cavalier king charles spaniel": "toy",
    # Non-Sporting
    "bulldog": "non-sporting",
    "french bulldog": "non-sporting",
    "poodle": "non-sporting",
    "dalmatian": "non-sporting",
    "chow chow": "non-sporting",
    "bichon frise": "non-sporting",
    # Herding
    "german shepherd": "herding",
    "border collie": "herding",
    "australian shepherd": "herding",
    "shetland sheepdog": "herding",
    "pembroke welsh corgi": "herding",
    "cardigan welsh corgi": "herding",
    "collie": "herding",
}


def _breed_score(user_breed: str, target_breed: str) -> int:
    """
    Return breed compatibility points.

    - Exact match (case-insensitive): 40 points
    - Same breed group: 20 points
    - No match: 0 points
    """
    user_breed_normalized = user_breed.strip().lower()
    target_breed_normalized = target_breed.strip().lower()

    if user_breed_normalized == target_breed_normalized:
        return 40

    user_group = BREED_GROUPS.get(user_breed_normalized)
    target_group = BREED_GROUPS.get(target_breed_normalized)

    if user_group and target_group and user_group == target_group:
        return 20

    return 0


def _distance_score(distance_km: float) -> int:
    """
    Return distance compatibility points.

    - distance_km <= 5:  30 points
    - distance_km <= 15: 20 points
    - distance_km <= 30: 10 points
    - else:               0 points
    """
    if distance_km <= 5:
        return 30
    if distance_km <= 15:
        return 20
    if distance_km <= 30:
        return 10
    return 0


def _age_score(user_age_months: int, target_age_months: int) -> int:
    """
    Return age compatibility points based on the absolute age difference.

    - |diff| <= 12 months: 20 points
    - |diff| <= 24 months: 10 points
    - else:                 0 points
    """
    diff = abs(user_age_months - target_age_months)
    if diff <= 12:
        return 20
    if diff <= 24:
        return 10
    return 0


def _gender_score(target_gender: str, user_preferences: dict | None) -> int:
    """
    Return gender preference compatibility points.

    - user_preferences["preferred_gender"] matches target_pet.gender
      (case-insensitive): 10 points
    - No preference set or mismatch: 0 points
    """
    if not user_preferences:
        return 0

    preferred = user_preferences.get("preferred_gender")
    if not preferred:
        return 0

    if preferred.strip().lower() == target_gender.strip().lower():
        return 10

    return 0


def calculate_match_score(
    user_pet,
    target_pet,
    distance_km: float,
    user_preferences: dict | None = None,
) -> tuple[int, dict]:
    """
    Calculate the compatibility score between two pet profiles.

    Scoring breakdown (max 100 points total):

    1. **Breed Match** (max 40 pts):
       - Exact breed match (case-insensitive): 40 pts
       - Same breed group (from BREED_GROUPS): 20 pts
       - No match: 0 pts

    2. **Distance Match** (max 30 pts):
       - distance_km <= 5:  30 pts
       - distance_km <= 15: 20 pts
       - distance_km <= 30: 10 pts
       - else: 0 pts

    3. **Age Compatibility** (max 20 pts):
       - |user_pet.age_months - target_pet.age_months| <= 12: 20 pts
       - |user_pet.age_months - target_pet.age_months| <= 24: 10 pts
       - else: 0 pts

    4. **Gender Preference** (max 10 pts):
       - user_preferences.get("preferred_gender") matches target_pet.gender
         (case-insensitive): 10 pts
       - else: 0 pts

    Parameters
    ----------
    user_pet:
        The authenticated user's pet profile. Must expose ``breed``
        (str) and ``age_months`` (int) attributes.
    target_pet:
        The candidate pet profile. Must expose ``breed`` (str),
        ``age_months`` (int), and ``gender`` (str) attributes.
    distance_km:
        Haversine distance in kilometres between the two pets' locations.
    user_preferences:
        Optional dict with the user's match preferences.  The key
        ``"preferred_gender"`` (str) is used for gender scoring.

    Returns
    -------
    tuple[int, dict]
        A tuple of:
        - ``total_score`` (int 0-100): weighted compatibility score.
        - ``breakdown`` (dict): per-category scores with keys
          ``"breed"``, ``"distance"``, ``"age"``, ``"gender"``.

    Examples
    --------
    >>> # Perfect match
    >>> score, breakdown = calculate_match_score(
    ...     user_pet=mock_pet(breed="Golden Retriever", age_months=24),
    ...     target_pet=mock_pet(breed="Golden Retriever", age_months=30, gender="female"),
    ...     distance_km=4.5,
    ...     user_preferences={"preferred_gender": "female"},
    ... )
    >>> assert score == 100
    """
    breed = _breed_score(user_pet.breed, target_pet.breed)
    distance = _distance_score(distance_km)
    age = _age_score(user_pet.age_months, target_pet.age_months)
    gender = _gender_score(target_pet.gender, user_preferences)

    total_score = breed + distance + age + gender

    breakdown = {
        "breed": breed,
        "distance": distance,
        "age": age,
        "gender": gender,
    }

    return total_score, breakdown
