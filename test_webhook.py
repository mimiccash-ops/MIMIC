#!/usr/bin/env python3
"""
TradingView Webhook Test Script
Tests webhook endpoint connectivity and response
"""

import requests
import json
import sys
import os
from datetime import datetime

# Load webhook passphrase from .env
from dotenv import load_dotenv
load_dotenv()

WEBHOOK_PASSPHRASE = os.environ.get('WEBHOOK_PASSPHRASE', 'mimiccashadmin')

def test_webhook(base_url, use_https=True):
    """
    Test the webhook endpoint
    
    Args:
        base_url: Base URL of your VPS (e.g., "mimic.cash" or "your-vps-ip")
        use_https: Whether to use HTTPS (default: True)
    """
    protocol = "https" if use_https else "http"
    webhook_url = f"{protocol}://{base_url}/webhook"
    
    print("="*70)
    print("TRADINGVIEW WEBHOOK TEST")
    print("="*70)
    print(f"Target URL: {webhook_url}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    print()
    
    # Test payload matching TradingView format
    test_payloads = [
        {
            "name": "LONG Signal Test",
            "payload": {
                "passphrase": WEBHOOK_PASSPHRASE,
                "symbol": "BTCUSDT",
                "action": "long",
                "risk_perc": 2.0,
                "leverage": 10,
                "tp_perc": 5.0,
                "sl_perc": 2.0,
                "strategy_id": 1
            }
        },
        {
            "name": "SHORT Signal Test",
            "payload": {
                "passphrase": WEBHOOK_PASSPHRASE,
                "symbol": "ETHUSDT",
                "action": "short",
                "risk_perc": 2.0,
                "leverage": 10,
                "tp_perc": 5.0,
                "sl_perc": 2.0,
                "strategy_id": 1
            }
        },
        {
            "name": "CLOSE Signal Test",
            "payload": {
                "passphrase": WEBHOOK_PASSPHRASE,
                "symbol": "BTCUSDT",
                "action": "close",
                "strategy_id": 1
            }
        }
    ]
    
    results = []
    
    for test in test_payloads:
        print(f"\n📡 Testing: {test['name']}")
        print("-" * 70)
        print(f"Payload: {json.dumps(test['payload'], indent=2)}")
        print()
        
        try:
            response = requests.post(
                webhook_url,
                json=test['payload'],
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'TradingView-Webhook-Test/1.0'
                },
                timeout=30,
                verify=use_https  # Verify SSL certificate if using HTTPS
            )
            
            success = response.status_code in [200, 201]
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Time: {response.elapsed.total_seconds():.2f}s")
            print(f"Response Body: {response.text[:500]}")
            
            if success:
                print("✅ SUCCESS - Webhook accepted!")
            else:
                print(f"❌ FAILED - Status {response.status_code}")
            
            results.append({
                'test': test['name'],
                'success': success,
                'status': response.status_code,
                'response': response.text
            })
            
        except requests.exceptions.SSLError as e:
            print(f"❌ SSL ERROR: {e}")
            print("💡 Try running with HTTP (use --no-https flag) or fix SSL certificate")
            results.append({
                'test': test['name'],
                'success': False,
                'error': f'SSL Error: {str(e)}'
            })
        except requests.exceptions.ConnectionError as e:
            print(f"❌ CONNECTION ERROR: {e}")
            print("💡 Check if:")
            print("   - Your VPS is running and accessible")
            print("   - Firewall allows incoming connections")
            print("   - Nginx is running and configured correctly")
            results.append({
                'test': test['name'],
                'success': False,
                'error': f'Connection Error: {str(e)}'
            })
        except requests.exceptions.Timeout as e:
            print(f"❌ TIMEOUT ERROR: {e}")
            print("💡 Server took too long to respond")
            results.append({
                'test': test['name'],
                'success': False,
                'error': f'Timeout: {str(e)}'
            })
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR: {e}")
            results.append({
                'test': test['name'],
                'success': False,
                'error': str(e)
            })
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r.get('success', False))
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED! Webhook is working correctly.")
        print("\n✅ Your TradingView webhooks should work now!")
        print("\n📋 Next steps:")
        print("   1. Copy your webhook URL: " + webhook_url)
        print("   2. In TradingView, go to Alerts > Webhook URL")
        print("   3. Paste the webhook URL")
        print("   4. Configure your alert message:")
        print('      {"passphrase":"' + WEBHOOK_PASSPHRASE + '","symbol":"{{ticker}}","action":"long","leverage":10,"tp_perc":5,"sl_perc":2}')
    else:
        print("\n⚠️ SOME TESTS FAILED - Check errors above")
        print("\n💡 Common issues:")
        print("   - Incorrect webhook passphrase")
        print("   - Firewall blocking port 443 (HTTPS) or 80 (HTTP)")
        print("   - Nginx not running or misconfigured")
        print("   - Application not running on correct port")
    
    print("="*70)
    
    return passed_tests == total_tests


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test TradingView Webhook')
    parser.add_argument('--url', type=str, required=True, help='Your VPS URL or IP (e.g., mimic.cash or 1.2.3.4)')
    parser.add_argument('--no-https', action='store_true', help='Use HTTP instead of HTTPS')
    
    args = parser.parse_args()
    
    success = test_webhook(args.url, use_https=not args.no_https)
    sys.exit(0 if success else 1)
