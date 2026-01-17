#!/usr/bin/env python3
"""
Emergency script to clear stuck pending symbols from Redis.
Run on the server: python3 clear_pending.py
"""
import redis
import os
import sys

# Try to get Redis URL from config
redis_url = os.environ.get('REDIS_URL')

if not redis_url:
    # Try loading from config.ini
    try:
        import configparser
        config = configparser.ConfigParser()
        config.read('config.ini')
        redis_url = config.get('redis', 'url', fallback=None)
    except:
        pass

if not redis_url:
    redis_url = 'redis://localhost:6379/0'

print(f'Connecting to Redis: {redis_url}')

try:
    r = redis.from_url(redis_url)
    r.ping()
    print('✅ Connected to Redis')
except Exception as e:
    print(f'❌ Failed to connect to Redis: {e}')
    sys.exit(1)

# Clear legacy SET
deleted_set = r.delete('master:pending_symbols')
print(f'Deleted legacy set key: {deleted_set}')

# Clear per-symbol keys (new format)
pattern = 'master:pending_symbols:*'
keys = list(r.scan_iter(match=pattern, count=100))
if keys:
    deleted = r.delete(*keys)
    symbols = [k.decode() if isinstance(k, bytes) else k for k in keys]
    print(f'Deleted {deleted} per-symbol keys:')
    for s in symbols:
        print(f'  - {s}')
else:
    print('No per-symbol keys found')

# Show what's left
remaining = list(r.scan_iter(match='master:*', count=100))
if remaining:
    print(f'\nRemaining master:* keys: {[k.decode() if isinstance(k, bytes) else k for k in remaining]}')
else:
    print('\n✅ No master pending keys remaining')

print('\n' + '='*50)
print('✅ Redis pending symbols cleared!')
print('='*50)
print('\nNow restart the worker:')
print('  sudo systemctl restart mimic-worker')
print('\nOr if using docker:')
print('  docker-compose restart worker')
