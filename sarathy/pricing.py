# Pricing constants and lookups organized by vendor and model

CURRENCY_SYMBOLS = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}

PRICING = {
    "sarvam": {
        "sarvam-105b": {
            "input_rate": 4.0,       # per 1M tokens
            "output_rate": 16.0,     # per 1M tokens
            "cached_rate": 2.5,      # per 1M tokens
            "currency": "INR",
        }
    }
}

def get_model_details(model_name: str):
    """
    Returns (vendor, input_rate, output_rate, cached_rate, currency_symbol) for a given model.
    Defaults to sarvam/sarvam-105b if model is not recognized or not specified.
    """
    model_name = (model_name or "").lower().strip()
    
    # Try to find match across any vendor
    for vendor, models in PRICING.items():
        if model_name in models:
            rates = models[model_name]
            currency = rates.get("currency", "INR")
            symbol = CURRENCY_SYMBOLS.get(currency, "₹")
            return vendor, rates["input_rate"], rates["output_rate"], rates["cached_rate"], symbol
            
    # Default to sarvam-105b rates if not found
    default_rates = PRICING["sarvam"]["sarvam-105b"]
    currency = default_rates.get("currency", "INR")
    symbol = CURRENCY_SYMBOLS.get(currency, "₹")
    return "sarvam", default_rates["input_rate"], default_rates["output_rate"], default_rates["cached_rate"], symbol

def get_pricing_for_model(model_name: str):
    """
    Returns (input_rate, output_rate, cached_rate, currency_symbol) for a given model.
    Defaults to sarvam-105b pricing if model is not recognized or not specified.
    """
    _, input_rate, output_rate, cached_rate, symbol = get_model_details(model_name)
    return input_rate, output_rate, cached_rate, symbol
