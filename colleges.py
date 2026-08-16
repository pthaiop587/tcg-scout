"""School names, for reading a college team out of a listing title.

A college football card says "Colorado" on the front and "Colorado Buffaloes"
in the eBay title people actually search. Nobody types "Buffaloes" into the
workbook sixty times, and no price guide carries the school as a field, so it
has to be read out of how sellers describe the card.

Matching is longest-first, which is the whole trick. "Texas" is a substring of
"Texas A&M" and "Texas Tech", "Miami" is two different schools, and "Washington"
is inside "Washington State" -- shortest-first gets every one of those wrong,
quietly, in the direction of the more famous school.
"""

# search token -> what goes in the Team column
SCHOOLS = {
    "texas a&m": "Texas A&M Aggies", "texas a and m": "Texas A&M Aggies",
    "texas tech": "Texas Tech Red Raiders",
    "texas": "Texas Longhorns",
    "washington state": "Washington State Cougars",
    "washington": "Washington Huskies",
    "michigan state": "Michigan State Spartans",
    "michigan": "Michigan Wolverines",
    "ohio state": "Ohio State Buckeyes",
    "oklahoma state": "Oklahoma State Cowboys",
    "oklahoma": "Oklahoma Sooners",
    "oregon state": "Oregon State Beavers",
    "oregon": "Oregon Ducks",
    "arizona state": "Arizona State Sun Devils",
    "arizona": "Arizona Wildcats",
    "colorado state": "Colorado State Rams",
    "colorado": "Colorado Buffaloes",
    "florida state": "Florida State Seminoles",
    "florida": "Florida Gators",
    "iowa state": "Iowa State Cyclones",
    "iowa": "Iowa Hawkeyes",
    "kansas state": "Kansas State Wildcats",
    "kansas": "Kansas Jayhawks",
    "mississippi state": "Mississippi State Bulldogs",
    "ole miss": "Ole Miss Rebels", "mississippi": "Ole Miss Rebels",
    "penn state": "Penn State Nittany Lions",
    "boise state": "Boise State Broncos",
    "fresno state": "Fresno State Bulldogs",
    "san diego state": "San Diego State Aztecs",
    "north carolina state": "NC State Wolfpack",
    "nc state": "NC State Wolfpack",
    "north carolina": "North Carolina Tar Heels",
    "south carolina": "South Carolina Gamecocks",
    "notre dame": "Notre Dame Fighting Irish",
    "georgia tech": "Georgia Tech Yellow Jackets",
    "georgia": "Georgia Bulldogs",
    "virginia tech": "Virginia Tech Hokies",
    "virginia": "Virginia Cavaliers",
    "west virginia": "West Virginia Mountaineers",
    "boston college": "Boston College Eagles",
    "wake forest": "Wake Forest Demon Deacons",
    "alabama": "Alabama Crimson Tide",
    "auburn": "Auburn Tigers",
    "arkansas": "Arkansas Razorbacks",
    "lsu": "LSU Tigers",
    "tennessee": "Tennessee Volunteers",
    "kentucky": "Kentucky Wildcats",
    "vanderbilt": "Vanderbilt Commodores",
    "missouri": "Missouri Tigers",
    "clemson": "Clemson Tigers",
    "louisville": "Louisville Cardinals",
    "duke": "Duke Blue Devils",
    "syracuse": "Syracuse Orange",
    "pittsburgh": "Pittsburgh Panthers", "pitt": "Pittsburgh Panthers",
    "miami": "Miami Hurricanes",
    "nebraska": "Nebraska Cornhuskers",
    "wisconsin": "Wisconsin Badgers",
    "minnesota": "Minnesota Golden Gophers",
    "illinois": "Illinois Fighting Illini",
    "indiana": "Indiana Hoosiers",
    "purdue": "Purdue Boilermakers",
    "northwestern": "Northwestern Wildcats",
    "maryland": "Maryland Terrapins",
    "rutgers": "Rutgers Scarlet Knights",
    "ucla": "UCLA Bruins",
    "usc": "USC Trojans",
    "utah": "Utah Utes",
    "byu": "BYU Cougars",
    "stanford": "Stanford Cardinal",
    "california": "California Golden Bears",
    "tcu": "TCU Horned Frogs",
    "baylor": "Baylor Bears",
    "houston": "Houston Cougars",
    "cincinnati": "Cincinnati Bearcats",
    "ucf": "UCF Knights",
    "smu": "SMU Mustangs",
    "tulane": "Tulane Green Wave",
    "memphis": "Memphis Tigers",
    "liberty": "Liberty Flames",
    "marshall": "Marshall Thundering Herd",
    "toledo": "Toledo Rockets",
    "army": "Army Black Knights",
    "navy": "Navy Midshipmen",
    "air force": "Air Force Falcons",
    "nevada": "Nevada Wolf Pack",
    "unlv": "UNLV Rebels",
    "wyoming": "Wyoming Cowboys",
    "louisiana tech": "Louisiana Tech Bulldogs",
    "south alabama": "South Alabama Jaguars",
    "james madison": "James Madison Dukes",
    "app state": "Appalachian State Mountaineers",
    "appalachian state": "Appalachian State Mountaineers",
    "sam houston": "Sam Houston Bearkats",
    "east carolina": "East Carolina Pirates",
    "bowling green": "Bowling Green Falcons",
    "western michigan": "Western Michigan Broncos",
    "central michigan": "Central Michigan Chippewas",
    "utsa": "UTSA Roadrunners",
    "temple": "Temple Owls",
    "rice": "Rice Owls",
    "tulsa": "Tulsa Golden Hurricane",
}

# longest first, so "texas tech" is tried before "texas"
ORDER = sorted(SCHOOLS, key=len, reverse=True)


def team_in(text):
    """The school a listing title names, or None."""
    t = " " + " ".join(str(text or "").lower().split()) + " "
    for token in ORDER:
        if token in t:
            return SCHOOLS[token]
    return None


def vote(titles):
    """The school named most often across a card's listings.

    One seller mistyping, or naming the opponent, should not decide it."""
    tally = {}
    for title in titles:
        s = team_in(title)
        if s:
            tally[s] = tally.get(s, 0) + 1
    if not tally:
        return None, 0
    best = max(tally, key=lambda k: (tally[k], k))
    return best, tally[best]
