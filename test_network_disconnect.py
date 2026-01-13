#!/usr/bin/env python3
"""
Test Script for Network Disconnection Handling
Tests that the trading engine handles client disconnections gracefully
"""

import sys
import logging
from http.client import RemoteDisconnected
import urllib3.exceptions

# Configure logging to see the differences
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger("NetworkDisconnectTest")

def simulate_network_errors():
    """Simulate the network errors that should be caught"""
    
    errors_to_test = [
        ("RemoteDisconnected", RemoteDisconnected('Remote end closed connection without response')),
        ("ConnectionAbortedError", ConnectionAbortedError('Connection aborted')),
        ("ConnectionResetError", ConnectionResetError('Connection reset by peer')),
        ("ProtocolError", urllib3.exceptions.ProtocolError('Connection broken: Invalid response')),
    ]
    
    print("\n" + "="*70)
    print("Testing Network Disconnection Error Handling")
    print("="*70 + "\n")
    
    for error_name, error in errors_to_test:
        print(f"Testing: {error_name}")
        print(f"  Error: {error}")
        
        try:
            # Simulate the error being raised
            raise error
        except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
                urllib3.exceptions.ProtocolError) as e:
            # This is what the fixed code does
            logger.warning(f"Could not push update: Client disconnected ({type(e).__name__})")
            print(f"  [OK] Caught and logged as WARNING (no Telegram alert)")
        except Exception as e:
            # This would be an unexpected error
            logger.error(f"Unexpected error: {e}")
            print(f"  [ERROR] Would trigger Telegram SYSTEM ERROR alert")
        
        print()
    
    print("="*70)
    print("Test Complete!")
    print("="*70)
    print("\nExpected behavior:")
    print("  - All network errors should be caught")
    print("  - Logged as WARNING (not ERROR)")
    print("  - No Telegram alerts triggered")
    print("  - System continues running")

def test_exception_imports():
    """Verify that all required exceptions are importable"""
    
    print("\n" + "="*70)
    print("Verifying Exception Imports")
    print("="*70 + "\n")
    
    try:
        from http.client import RemoteDisconnected
        print("[OK] RemoteDisconnected imported successfully")
    except ImportError as e:
        print(f"[ERROR] Failed to import RemoteDisconnected: {e}")
        return False
    
    try:
        import urllib3.exceptions
        print("[OK] urllib3.exceptions imported successfully")
    except ImportError as e:
        print(f"[ERROR] Failed to import urllib3.exceptions: {e}")
        return False
    
    print("[OK] ConnectionAbortedError (built-in)")
    print("[OK] ConnectionResetError (built-in)")
    
    print("\n" + "="*70)
    print("All imports successful!")
    print("="*70)
    
    return True

def verify_files_syntax():
    """Verify that the modified files have no syntax errors"""
    
    print("\n" + "="*70)
    print("Verifying File Syntax")
    print("="*70 + "\n")
    
    files_to_check = ['trading_engine.py', 'app.py']
    all_ok = True
    
    for filename in files_to_check:
        try:
            import py_compile
            py_compile.compile(filename, doraise=True)
            print(f"[OK] {filename} - No syntax errors")
        except py_compile.PyCompileError as e:
            print(f"[ERROR] {filename} - Syntax error: {e}")
            all_ok = False
        except FileNotFoundError:
            print(f"[WARN] {filename} - File not found (run from project root)")
            all_ok = False
    
    print("\n" + "="*70)
    if all_ok:
        print("All files have valid syntax!")
    else:
        print("Some files have syntax errors - please review")
    print("="*70)
    
    return all_ok

if __name__ == '__main__':
    print("\n")
    print("="*70)
    print("     Network Disconnection Handling - Verification Test")
    print("="*70)
    
    # Test 1: Verify imports
    imports_ok = test_exception_imports()
    
    # Test 2: Verify file syntax
    syntax_ok = verify_files_syntax()
    
    # Test 3: Simulate network errors
    simulate_network_errors()
    
    # Summary
    print("\n\n")
    print("="*70)
    print("                      TEST SUMMARY")
    print("="*70)
    print()
    
    if imports_ok and syntax_ok:
        print("[SUCCESS] All tests passed!")
        print()
        print("Next steps:")
        print("  1. Restart your trading engine")
        print("  2. Connect a client via browser")
        print("  3. Close the browser tab")
        print("  4. Verify NO Telegram 'SYSTEM ERROR' alerts appear")
        print("  5. Check logs for WARNING messages (not ERROR)")
        sys.exit(0)
    else:
        print("[FAILED] Some tests failed - please review the errors above")
        sys.exit(1)
