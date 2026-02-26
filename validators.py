"""
Security validators va sanitizers
"""

def validate_user_id(user_id):
    """User ID validation"""
    if not isinstance(user_id, int):
        try:
            user_id = int(user_id)
        except:
            return False, "Noto'g'ri user ID"
    
    if user_id <= 0:
        return False, "Noto'g'ri user ID"
    
    return True, user_id

def validate_card_number(card_number):
    """Karta raqami validation (Luhn algorithm)"""
    if not isinstance(card_number, str):
        return False, "Karta raqami text bo'lishi kerak"
    
    # Faqat raqamlar
    if not card_number.isdigit():
        return False, "Karta raqamida faqat raqamlar bo'lishi kerak"
    
    # 12-19 ta raqam
    if len(card_number) < 12 or len(card_number) > 19:
        return False, f"Karta raqamida {len(card_number)} ta raqam, 12-19 ta bo'lishi kerak"
    
    # Luhn algorithm
    total = 0
    reverse = card_number[::-1]
    
    for i, digit in enumerate(reverse):
        n = int(digit)
        if i % 2 == 1:  # Every second digit from right
            n *= 2
            if n > 9:
                n -= 9
        total += n
    
    if total % 10 != 0:
        return False, "Karta raqami noto'g'ri"
    
    return True, card_number

def validate_phone_number(phone_number):
    """Telefon raqami validation"""
    if not isinstance(phone_number, str):
        return False, "Telefon raqami text bo'lishi kerak"
    
    # Clean va format
    phone = phone_number.replace(" ", "").replace("-", "").replace("+", "")
    
    if not phone.isdigit():
        return False, "Telefon raqamida faqat raqamlar bo'lishi kerak"
    
    if len(phone) < 10:
        return False, "Telefon raqami juda qisqa"
    
    if len(phone) > 15:
        return False, "Telefon raqami juda uzun"
    
    return True, phone

def validate_amount(amount):
    """Pul miqdori validation"""
    try:
        amount = int(amount)
    except:
        return False, "Miqdor faqat raqam bo'lishi kerak"
    
    if amount <= 0:
        return False, "Miqdor musbat bo'lishi kerak"
    
    if amount > 100000000:  # Max 100 million
        return False, "Miqdor juda katta"
    
    return True, amount

def validate_text_input(text, min_length=1, max_length=1000):
    """Umumiy text input validation"""
    if not isinstance(text, str):
        return False, "Text bo'lishi kerak"
    
    text = text.strip()
    
    if len(text) < min_length:
        return False, f"Minimal {min_length} ta belgi kerak"
    
    if len(text) > max_length:
        return False, f"Maksimal {max_length} ta belgi"
    
    return True, text

def sanitize_text(text):
    """SQL injection'dan himoya qilish uchun text cleaning"""
    # Unicode characters filtering
    text = str(text)
    # Remove potentially dangerous characters
    dangerous_chars = ['\\', '"', "'"]
    for char in dangerous_chars:
        text = text.replace(char, "")
    return text.strip()
