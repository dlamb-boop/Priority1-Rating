"""Enums taken from the Priority1 v2 OpenAPI spec."""

FREIGHT_CLASSES = [
    "50",
    "55",
    "60",
    "65",
    "70",
    "77.5",
    "85",
    "92.5",
    "100",
    "110",
    "125",
    "150",
    "175",
    "200",
    "250",
    "300",
    "400",
    "500",
]

PACKAGING_TYPES = [
    "Bag",
    "Bale",
    "Box",
    "Bucket",
    "Bundle",
    "Can",
    "Carton",
    "Case",
    "Coil",
    "Crate",
    "Cylinder",
    "Drums",
    "Pail",
    "Pieces",
    "Pallet",
    "Reel",
    "Roll",
    "Skid",
    "Tube",
    "Tote",
]

COUNTRY_CODES = ["US", "CA", "MX", "PR"]

EQUIPMENT_TYPES = [
    "53_Foot_Dry_Van",
    "Sprinter_Van",
    "Straight_Truck",
    "Large_Straight_Truck",
    "Small_Straight_Truck",
    "53_Foot_Flatbed",
    "48_Foot_Flatbed",
    "53_Foot_Step_Deck",
    "48_Foot_Step_Deck",
]

EQUIPMENT_LABELS = {
    "53_Foot_Dry_Van": "53' dry van",
    "Sprinter_Van": "Sprinter van",
    "Straight_Truck": "Straight truck",
    "Large_Straight_Truck": "Large straight truck",
    "Small_Straight_Truck": "Small straight truck",
    "53_Foot_Flatbed": "53' flatbed",
    "48_Foot_Flatbed": "48' flatbed",
    "53_Foot_Step_Deck": "53' step deck",
    "48_Foot_Step_Deck": "48' step deck",
}

TL_SERVICE_TYPES = ["Full", "Team"]
WEIGHT_UNITS = ["lbs", "kg"]

ZIP_HINTS = {
    "02101": ("Boston", "MA"),
    "10001": ("New York", "NY"),
    "19103": ("Philadelphia", "PA"),
    "30303": ("Atlanta", "GA"),
    "33101": ("Miami", "FL"),
    "60606": ("Chicago", "IL"),
    "64101": ("Kansas City", "MO"),
    "72205": ("Little Rock", "AR"),
    "75201": ("Dallas", "TX"),
    "77002": ("Houston", "TX"),
    "80202": ("Denver", "CO"),
    "85001": ("Phoenix", "AZ"),
    "90221": ("Los Angeles", "CA"),
    "94105": ("San Francisco", "CA"),
    "98101": ("Seattle", "WA"),
}
