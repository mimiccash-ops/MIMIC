"""
Exchange Validator Service
Dynamic validation and connection testing for multiple exchanges using CCXT
"""

import logging
from typing import Optional, Dict, Any
import ccxt
from ccxt import ExchangeError, AuthenticationError, NetworkError

# Try to import Exchange base class for type hints (varies by ccxt version)
try:
    from ccxt.base.exchange import Exchange as BaseExchange
except ImportError:
    try:
        from ccxt import Exchange as BaseExchange
    except ImportError:
        # Fallback: BaseExchange is just for type hints, not critical
        BaseExchange = object

logger = logging.getLogger("ExchangeValidator")


class ExchangeValidationError(Exception):
    """Custom exception for exchange validation errors"""
    pass


class ExchangeConnectionError(Exception):
    """Custom exception for exchange connection errors"""
    pass


# Map of supported exchanges and their CCXT class names
# Top 20 exchanges by CoinMarketCap trading volume
SUPPORTED_EXCHANGES = {
    # Tier 1 - Major exchanges
    'binance': 'binance',
    'coinbase': 'coinbase',
    'bybit': 'bybit',
    'okx': 'okx',
    'upbit': 'upbit',
    
    # Tier 2 - Large exchanges
    'bitget': 'bitget',
    'gate': 'gateio',
    'kucoin': 'kucoin',
    'kraken': 'kraken',
    'htx': 'htx',
    
    # Tier 3 - Mid-size exchanges
    'mexc': 'mexc',
    'cryptocom': 'cryptocom',
    'bitstamp': 'bitstamp',
    'bitfinex': 'bitfinex',
    'bithumb': 'bithumb',
    
    # Tier 4 - Additional exchanges
    'whitebit': 'whitebit',
    'lbank': 'lbank',
    'poloniex': 'poloniex',
    'gemini': 'gemini',
    'bitmart': 'bitmart',
    
    # Tier 5 - More exchanges
    'xt': 'xt',
    'bingx': 'bingx',
    'phemex': 'phemex',
    'toobit': 'toobit',
    'kcex': 'kcex',
    'weex': 'weex',
    'bitunix': 'bitunix',
    'ourbit': 'ourbit',
    'cofinex': 'cofinex',
}

# Exchanges that require passphrase for API authentication
PASSPHRASE_EXCHANGES = {'okx', 'kucoin', 'cryptocom', 'bitget'}


def validate_and_connect(
    exchange_name: str,
    api_key: str,
    api_secret: str,
    passphrase: Optional[str] = None,
    sandbox: bool = False
) -> Dict[str, Any]:
    """
    Validate exchange credentials and test connection
    
    This function:
    1. Dynamically loads the exchange class from CCXT
    2. Configures it with provided credentials
    3. Performs a lightweight API call to verify authentication
    4. Returns connection status and exchange info
    
    Args:
        exchange_name: Exchange name (e.g., 'binance', 'bybit', 'okx')
        api_key: API key
        api_secret: API secret (encrypted or plain)
        passphrase: Optional passphrase (required for OKX/KuCoin)
        sandbox: Use sandbox/testnet mode
        
    Returns:
        Dict with:
            - success: bool
            - exchange_info: dict with exchange details
            - balance: dict with account balance (if available)
            
    Raises:
        ExchangeValidationError: If exchange is not supported or validation fails
        ExchangeConnectionError: If connection/authentication fails
    """
    # Normalize exchange name
    exchange_name_lower = exchange_name.lower().strip()
    
    # Check if exchange is supported
    if exchange_name_lower not in SUPPORTED_EXCHANGES:
        raise ExchangeValidationError(
            f"Exchange '{exchange_name}' is not supported. "
            f"Supported exchanges: {', '.join(SUPPORTED_EXCHANGES.keys())}"
        )
    
    # Get CCXT class name
    ccxt_class_name = SUPPORTED_EXCHANGES[exchange_name_lower]
    
    try:
        # Dynamically load exchange class
        exchange_class = getattr(ccxt, ccxt_class_name)
        if not exchange_class:
            raise ExchangeValidationError(f"Exchange class '{ccxt_class_name}' not found in CCXT")
        
        # Create exchange instance
        exchange_config = {
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # Use futures by default
            }
        }
        
        # Add passphrase if provided (required for OKX, KuCoin)
        if passphrase:
            exchange_config['password'] = passphrase
        
        # Enable sandbox/testnet if requested
        if sandbox:
            exchange_config['sandbox'] = True
            exchange_config['options']['defaultType'] = 'test'
        
        exchange: BaseExchange = exchange_class(exchange_config)
        
        # Test connection with a lightweight API call
        # Try fetch_balance first (most common)
        try:
            balance = exchange.fetch_balance()
            logger.info(f"✅ Successfully connected to {exchange_name} - Balance fetched")
            
            return {
                'success': True,
                'exchange_info': {
                    'name': exchange_name,
                    'id': exchange.id,
                    'urls': exchange.urls,
                    'version': exchange.version if hasattr(exchange, 'version') else None,
                },
                'balance': balance.get('USDT', {}) if 'USDT' in balance else balance.get('total', {}),
                'message': f'Successfully connected to {exchange_name}'
            }
            
        except AuthenticationError as e:
            logger.error(f"❌ Authentication failed for {exchange_name}: {e}")
            raise ExchangeConnectionError(
                f"Authentication failed: Invalid API credentials. "
                f"Please check your API key, secret, and passphrase (if required)."
            )
        
        except NetworkError as e:
            logger.error(f"❌ Network error for {exchange_name}: {e}")
            raise ExchangeConnectionError(
                f"Network error: Unable to connect to {exchange_name}. "
                f"Please check your internet connection and try again."
            )
        
        except ExchangeError as e:
            # Try alternative method: check_required_credentials
            try:
                required = exchange.check_required_credentials()
                if not required:
                    logger.info(f"✅ Successfully connected to {exchange_name} - Credentials validated")
                    return {
                        'success': True,
                        'exchange_info': {
                            'name': exchange_name,
                            'id': exchange.id,
                            'urls': exchange.urls,
                        },
                        'balance': None,
                        'message': f'Successfully connected to {exchange_name}'
                    }
                else:
                    raise ExchangeConnectionError(
                        f"Missing required credentials: {', '.join(required)}"
                    )
            except Exception as alt_e:
                logger.error(f"❌ Validation failed for {exchange_name}: {alt_e}")
                raise ExchangeConnectionError(
                    f"Validation failed: {str(alt_e)}. "
                    f"Please verify your API credentials and exchange settings."
                )
        
    except AttributeError:
        raise ExchangeValidationError(
            f"Exchange '{exchange_name}' (CCXT class: '{ccxt_class_name}') is not available in your CCXT installation. "
            f"Please install the required CCXT version or check exchange support."
        )
    
    except Exception as e:
        logger.error(f"❌ Unexpected error validating {exchange_name}: {e}")
        raise ExchangeValidationError(
            f"Unexpected error during validation: {str(e)}"
        )


def get_exchange_requirements(exchange_name: str) -> Dict[str, Any]:
    """
    Get requirements for a specific exchange
    
    Args:
        exchange_name: Exchange name
        
    Returns:
        Dict with:
            - requires_passphrase: bool
            - supported: bool
            - notes: str
    """
    exchange_name_lower = exchange_name.lower().strip()
    
    if exchange_name_lower not in SUPPORTED_EXCHANGES:
        return {
            'supported': False,
            'requires_passphrase': False,
            'notes': f'Exchange {exchange_name} is not supported'
        }
    
    # Exchanges that require passphrase
    requires_passphrase = exchange_name_lower in PASSPHRASE_EXCHANGES
    
    return {
        'supported': True,
        'requires_passphrase': requires_passphrase,
        'notes': f'Passphrase required' if requires_passphrase else 'No passphrase required'
    }


def list_supported_exchanges() -> list:
    """Return list of supported exchange names"""
    return list(SUPPORTED_EXCHANGES.keys())
