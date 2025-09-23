import phonenumbers

def normalize_phone(raw: str, default_region: str = "IN") -> str:
    num = phonenumbers.parse(raw, default_region)
    if not phonenumbers.is_valid_number(num):
        raise ValueError("invalid_phone")
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)  # e.g., +9198XXXXXXXX