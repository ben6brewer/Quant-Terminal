"""CPI services."""

# Component series (the 8 sub-categories)
COMPONENT_LABELS = [
    "Food & Beverages", "Energy", "Housing", "Transportation",
    "Medical Care", "Apparel", "Education", "Recreation",
]

# Approximate BLS relative importance weights (sum ~0.972).
COMPONENT_WEIGHTS = {
    "Food & Beverages": 0.143,
    "Energy": 0.070,
    "Housing": 0.404,
    "Transportation": 0.131,
    "Medical Care": 0.084,
    "Apparel": 0.025,
    "Education": 0.060,
    "Recreation": 0.055,
}
