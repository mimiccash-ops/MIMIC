"""
Generate VAPID keys for Web Push Notifications

VAPID (Voluntary Application Server Identification) keys are used to identify
your server when sending push notifications. The public key is shared with
browsers, and the private key is kept secret on your server.

Run this script to generate new VAPID keys:
    python generate_vapid_keys.py

Then add the keys to your .env file or config.ini.
"""

import base64
import os


def generate_vapid_keys():
    """Generate VAPID key pair for Web Push"""
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        print("❌ cryptography package not installed!")
        print("Run: pip install cryptography")
        return None, None
    
    # Generate EC private key using P-256 curve (required for VAPID)
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    
    # Extract private key bytes (32 bytes for P-256)
    private_numbers = private_key.private_numbers()
    private_bytes = private_numbers.private_value.to_bytes(32, 'big')
    
    # Get public key
    public_key = private_key.public_key()
    public_numbers = public_key.public_numbers()
    
    # Encode public key in uncompressed format (0x04 || x || y)
    x_bytes = public_numbers.x.to_bytes(32, 'big')
    y_bytes = public_numbers.y.to_bytes(32, 'big')
    public_bytes = b'\x04' + x_bytes + y_bytes
    
    # Base64url encode (without padding)
    private_key_b64 = base64.urlsafe_b64encode(private_bytes).rstrip(b'=').decode('ascii')
    public_key_b64 = base64.urlsafe_b64encode(public_bytes).rstrip(b'=').decode('ascii')
    
    return private_key_b64, public_key_b64


def main():
    print("=" * 70)
    print("                    VAPID Key Generator")
    print("                  Web Push Notifications")
    print("=" * 70)
    print()
    
    private_key, public_key = generate_vapid_keys()
    
    if not private_key or not public_key:
        return
    
    print("✅ VAPID keys generated successfully!")
    print()
    print("-" * 70)
    print("PUBLIC KEY (share with browsers, safe to expose):")
    print("-" * 70)
    print(public_key)
    print()
    print("-" * 70)
    print("PRIVATE KEY (keep secret, never share!):")
    print("-" * 70)
    print(private_key)
    print()
    print("=" * 70)
    print("                    Configuration")
    print("=" * 70)
    print()
    print("Add these to your .env file:")
    print()
    print(f"VAPID_PUBLIC_KEY={public_key}")
    print(f"VAPID_PRIVATE_KEY={private_key}")
    print("VAPID_CLAIM_EMAIL=mailto:admin@mimic.cash")
    print()
    print("-" * 70)
    print()
    print("Or add to config.ini under [WebPush] section:")
    print()
    print("[WebPush]")
    print(f"vapid_public_key = {public_key}")
    print(f"vapid_private_key = {private_key}")
    print("vapid_claim_email = mailto:admin@mimic.cash")
    print()
    print("=" * 70)
    print()
    
    # Optionally save to .env.vapid file
    save = input("Save keys to .env.vapid file? (y/N): ").strip().lower()
    if save == 'y':
        env_content = f"""# VAPID Keys for Web Push Notifications
# Generated on {__import__('datetime').datetime.now().isoformat()}
# Add these to your main .env file

VAPID_PUBLIC_KEY={public_key}
VAPID_PRIVATE_KEY={private_key}
VAPID_CLAIM_EMAIL=mailto:admin@mimic.cash
"""
        with open('.env.vapid', 'w') as f:
            f.write(env_content)
        print()
        print("✅ Keys saved to .env.vapid")
        print("   Copy the contents to your main .env file")


if __name__ == '__main__':
    main()
