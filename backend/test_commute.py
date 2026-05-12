"""Quick manual test for the Maps scraper. Run from backend/ dir:
    python test_commute.py
"""
import sys
sys.path.insert(0, '.')

# Taipei 101 → Zhongshan MRT station
from app.services.commute import get_commute

result = get_commute(
    origin_lat=25.0339,   # Taipei 101
    origin_lng=121.5645,
    dest_lat=25.0524,     # Zhongshan MRT
    dest_lng=121.5200,
)

print("Result:", result)
