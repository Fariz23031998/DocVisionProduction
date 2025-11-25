from dotenv import load_dotenv
import os

load_dotenv()

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM =  os.getenv("ALGORITHM")
SESSION_EXPIRE_DAYS = int(os.getenv("SESSION_EXPIRE_DAYS"))
DATABASE_URL =  os.getenv("DATABASE_URL")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM")
APP_NAME=os.getenv("APP_NAME")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")
SMTP_EMAIL_PASSWORD = os.getenv("SMTP_EMAIL_PASSWORD")
SMTP_EMAIL_FROM = os.getenv("SMTP_EMAIL_FROM")
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL")
BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME")
BREVO_BASE_URL = os.getenv("BREVO_BASE_URL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_EMAIL_FROM = os.getenv("RESEND_EMAIL_FROM")
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID")
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID")
CLICK_MERCHANT_USER_ID = os.getenv("CLICK_MERCHANT_USER_ID")
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY")
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic', '.heif', ".mpo", ".pdf"}
ENVIRONMENT = os.getenv("ENVIRONMENT")
ADMIN_CODE = os.getenv("ADMIN_CODE")

MAX_FILE_SIZE = 5 * 1024 * 1024
# Order expiration (unpaid orders expire after this time)
ORDER_EXPIRATION_HOURS = 24
# Webhook secret key (for validating webhook requests)
WEBHOOK_SECRET = "your-secret-key-here"  # Change this in production!
CLICK_PAYMENT_BASE_URL = "https://my.click.uz/services/pay"
HOME_URL = "https://docvision.uz"

PRICING = {
    'standard': 1000,
    'pro': 1500
}

# Define plan limits and features
PLANS_CONFIG = {
    'free-trial': {
        'monthly_regeneration': 30,
        'daily_regeneration': 0,  # No daily regeneration for free trial
        'features': [
            'plans.features.productManagement',
            'plans.features.OnlineSupport'
        ],
    },
    'standard': {
        'monthly_regeneration': 200,
        'daily_regeneration': 5,  # Regenerate 5 files per day
        'features': [
            'plans.features.productManagement',
            'plans.features.PriorityOnlineSupport'
        ],
        "pricing": {
            "price_per_month": PRICING["standard"],
            "discounts": [
                {"months": 1, "discount": 0},
                {"months": 3, "discount": 0.05},
                {"months": 6, "discount": 0.10},
                {"months": 12, "discount": 0.20}
            ]
        }
    },
    'pro': {
        'monthly_regeneration': 300,
        'daily_regeneration': 10,  # Regenerate 10 files per day
        'features': [
            'plans.features.productManagement',
            'plans.features.PriorityOnlineSupport'
        ],
        "pricing": {
            "price_per_month": PRICING["pro"],
            "discounts": [
                {"months": 1, "discount": 0},
                {"months": 3, "discount": 0.05},
                {"months": 6, "discount": 0.10},
                {"months": 12, "discount": 0.20}
            ]
        }
    }
}

def format_click_url(
        transaction_param: str,
        amount: float,
        return_url: str = HOME_URL,
        merchant_id: str = CLICK_MERCHANT_ID,
        service_id: str = CLICK_SERVICE_ID,
        merchant_user_id: str = CLICK_MERCHANT_USER_ID
    ):
    full_url = CLICK_PAYMENT_BASE_URL + (f"?service_id={service_id}&merchant_id={merchant_id}&merchant_user_id="
                                         f"{merchant_user_id}&amount={int(amount)}&transaction_param={transaction_param}&"
                                         F"return_url={return_url}")
    return full_url

