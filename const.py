PAYMENT_RETURN_ROUTE = '/payment/paytr/return'
WEBHOOK_ROUTE = '/payment/paytr/webhook'

PAYTR_API_BASE_URL = 'https://www.paytr.com'
PAYTR_IFRAME_TOKEN_ENDPOINT = 'odeme/api/get-token'
PAYTR_IFRAME_CHECKOUT_URL = 'https://www.paytr.com/odeme/guvenli'

# See https://dev.paytr.com/direkt-api/direkt-api-1-adim
SUPPORTED_CURRENCY_CODE = 'TRY'
SUPPORTED_PAYTR_CURRENCY = 'TL'
DEFAULT_PAYMENT_METHOD_CODES = {
    'card',
    'mastercard',
    'visa',
    'amex',
    'troy',
}

SENSITIVE_LOG_KEYS = {
    'paytr_merchant_key',
    'paytr_merchant_salt',
    'paytr_token',
    'hash',
}
