import os

ADMIN_ID = 7724497080 
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CURRENCY = "so'm"
MIN_WITHDRAWAL = 5000

INITIAL_SPINS = 2
REFERAL_SPINS = 1  # Har bir taklif qilingan do'st uchun ta aylantirish bonus

# Yangi xususiyat: Kanal obunasi penalty
REFERAL_CHANNEL_DEDUCTION = 10000  # Referalning referali kanaldan chiqib ketsa, ayrilishi kerak bo'lgan pul
CHANNEL_UNSUBSCRIBE_GRACE_PERIOD = 86400  # 1 kun (secondlarda) - bu vaqtdan keyin jarima qilish

PRIZES_LOW_BALANCE = [0, 0, 300, 350, 390, 400, 450, 460, 470, 480, 490, 500]

PRIZES_HIGH_BALANCE = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 300, 310, 320, 330, 340, 350, 360, 370, 380, 390, 400, 410, 420, 430, 440, 450, 460, 470, 480, 490, 500,]


PRIZES = PRIZES_LOW_BALANCE
