import random
from datetime import datetime, timedelta

def generate_otp():
    return str(random.randint(1000, 9999))

def expiry_time(minutes=10):
    return datetime.utcnow() + timedelta(minutes=minutes)
