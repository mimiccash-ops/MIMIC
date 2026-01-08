#!/usr/bin/env python3
"""
Brain Capital - Load Testing / Stress Test Script

This script tests the system's ability to execute trades for 1000 users
within the target latency of < 500ms.

Usage:
    python stress_test.py [--users 1000] [--cleanup]

Requirements:
    - Flask app context available
    - Database accessible (SQLite or PostgreSQL)
"""

import asyncio
import argparse
import logging
import sys
import time
import random
import string
import threading
import statistics
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("StressTest")

# Reduce noise from other loggers during stress test
logging.getLogger("TradingEngine").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


# ==================== MOCK EXCHANGE CLIENT ====================

@dataclass
class OrderResult:
    """Result of a mock order execution"""
    user_id: int
    username: str
    order_time: float  # Time when order was "executed"
    success: bool
    latency_ms: float  # Latency from signal start to order execution


class MockBinanceClient:
    """
    Mock Binance client that simulates API calls with realistic latency.
    Used for stress testing without making real API calls.
    """
    
    def __init__(self, user_id: int, username: str, simulated_latency_ms: float = 10.0):
        self.user_id = user_id
        self.username = username
        self.simulated_latency_ms = simulated_latency_ms
        self._positions = {}
        self._balance = 10000.0  # Mock balance
        
    def futures_account_balance(self) -> list:
        """Simulate fetching account balance"""
        # Simulate network latency
        time.sleep(self.simulated_latency_ms / 1000.0)
        return [{'asset': 'USDT', 'balance': str(self._balance), 'availableBalance': str(self._balance)}]
    
    def futures_symbol_ticker(self, symbol: str) -> dict:
        """Simulate fetching symbol ticker"""
        time.sleep(self.simulated_latency_ms / 1000.0)
        # Return a realistic price
        prices = {'BTCUSDT': 65000.0, 'ETHUSDT': 3500.0, 'SOLUSDT': 150.0}
        price = prices.get(symbol, 100.0)
        return {'symbol': symbol, 'price': str(price)}
    
    def futures_position_information(self, symbol: str = None) -> list:
        """Simulate fetching position information"""
        time.sleep(self.simulated_latency_ms / 1000.0)
        if symbol:
            pos = self._positions.get(symbol, {'symbol': symbol, 'positionAmt': '0'})
            return [pos]
        return list(self._positions.values())
    
    def futures_change_leverage(self, symbol: str, leverage: int) -> dict:
        """Simulate changing leverage"""
        time.sleep(self.simulated_latency_ms / 1000.0)
        return {'symbol': symbol, 'leverage': leverage}
    
    def futures_change_margin_type(self, symbol: str, marginType: str) -> dict:
        """Simulate changing margin type"""
        time.sleep(self.simulated_latency_ms / 1000.0)
        return {'symbol': symbol, 'marginType': marginType}
    
    def futures_create_order(self, **kwargs) -> dict:
        """Simulate creating a futures order"""
        time.sleep(self.simulated_latency_ms / 1000.0)
        symbol = kwargs.get('symbol', 'BTCUSDT')
        side = kwargs.get('side', 'BUY')
        quantity = kwargs.get('quantity', 0.001)
        
        # Update mock position
        self._positions[symbol] = {
            'symbol': symbol,
            'positionAmt': str(quantity) if side == 'BUY' else str(-quantity)
        }
        
        return {
            'orderId': random.randint(100000, 999999),
            'symbol': symbol,
            'side': side,
            'type': kwargs.get('type', 'MARKET'),
            'status': 'FILLED',
            'executedQty': str(quantity),
            'avgPrice': '65000.0'
        }
    
    def futures_change_position_mode(self, dualSidePosition: bool) -> dict:
        """Simulate changing position mode"""
        return {'dualSidePosition': dualSidePosition}


class MockCCXTExchange:
    """
    Mock CCXT exchange client for async operations.
    """
    
    def __init__(self, user_id: int, username: str, exchange_type: str = 'okx', 
                 simulated_latency_ms: float = 15.0):
        self.user_id = user_id
        self.username = username
        self.exchange_type = exchange_type
        self.simulated_latency_ms = simulated_latency_ms
        self._positions = {}
        self._balance = 10000.0
        
    async def fetch_balance(self) -> dict:
        """Simulate fetching balance"""
        await asyncio.sleep(self.simulated_latency_ms / 1000.0)
        return {'USDT': {'free': self._balance, 'total': self._balance}}
    
    async def fetch_ticker(self, symbol: str) -> dict:
        """Simulate fetching ticker"""
        await asyncio.sleep(self.simulated_latency_ms / 1000.0)
        return {'symbol': symbol, 'last': 65000.0}
    
    async def fetch_positions(self, symbols: list = None) -> list:
        """Simulate fetching positions"""
        await asyncio.sleep(self.simulated_latency_ms / 1000.0)
        return list(self._positions.values())
    
    async def set_leverage(self, leverage: int, symbol: str) -> dict:
        """Simulate setting leverage"""
        await asyncio.sleep(self.simulated_latency_ms / 1000.0)
        return {'leverage': leverage}
    
    async def create_order(self, symbol: str, type: str, side: str, amount: float, 
                          price: float = None, params: dict = None) -> dict:
        """Simulate creating an order"""
        await asyncio.sleep(self.simulated_latency_ms / 1000.0)
        
        self._positions[symbol] = {
            'symbol': symbol,
            'contracts': amount if side == 'buy' else -amount,
            'side': 'long' if side == 'buy' else 'short'
        }
        
        return {
            'id': str(random.randint(100000, 999999)),
            'symbol': symbol,
            'side': side,
            'type': type,
            'amount': amount,
            'status': 'closed',
            'filled': amount,
            'average': 65000.0
        }
    
    async def close(self):
        """Simulate closing connection"""
        pass


# ==================== LATENCY TRACKER ====================

class LatencyTracker:
    """Thread-safe tracker for order execution latencies"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._results: List[OrderResult] = []
        self._signal_start_time: Optional[float] = None
        
    def set_signal_start(self):
        """Mark the start of signal processing"""
        self._signal_start_time = time.perf_counter()
        
    def record_order(self, user_id: int, username: str, success: bool = True):
        """Record when an order was executed"""
        order_time = time.perf_counter()
        latency_ms = (order_time - self._signal_start_time) * 1000 if self._signal_start_time else 0
        
        result = OrderResult(
            user_id=user_id,
            username=username,
            order_time=order_time,
            success=success,
            latency_ms=latency_ms
        )
        
        with self._lock:
            self._results.append(result)
            
    def get_results(self) -> List[OrderResult]:
        """Get all recorded results"""
        with self._lock:
            return list(self._results)
    
    @staticmethod
    def _percentile(sorted_data: List[float], p: float) -> float:
        """Calculate percentile from sorted data (pure Python implementation)"""
        if not sorted_data:
            return 0.0
        n = len(sorted_data)
        if n == 1:
            return sorted_data[0]
        
        # Linear interpolation method
        k = (n - 1) * (p / 100.0)
        f = int(k)
        c = f + 1
        
        if c >= n:
            return sorted_data[-1]
        
        return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)
    
    def get_statistics(self) -> Dict:
        """Calculate latency statistics"""
        with self._lock:
            if not self._results:
                return {}
            
            latencies = [r.latency_ms for r in self._results if r.success]
            if not latencies:
                return {}
            
            latencies_sorted = sorted(latencies)
            
            return {
                'total_users': len(self._results),
                'successful': len(latencies),
                'failed': len(self._results) - len(latencies),
                'min_ms': min(latencies),
                'max_ms': max(latencies),
                'mean_ms': statistics.mean(latencies),
                'median_ms': statistics.median(latencies),
                'p50_ms': self._percentile(latencies_sorted, 50),
                'p90_ms': self._percentile(latencies_sorted, 90),
                'p95_ms': self._percentile(latencies_sorted, 95),
                'p99_ms': self._percentile(latencies_sorted, 99),
                'stdev_ms': statistics.stdev(latencies) if len(latencies) > 1 else 0,
                'first_order_ms': latencies_sorted[0],
                'last_order_ms': latencies_sorted[-1],
            }
    
    def clear(self):
        """Clear all results"""
        with self._lock:
            self._results.clear()
            self._signal_start_time = None


# Global tracker instance
latency_tracker = LatencyTracker()


# ==================== STRESS TEST ENGINE ====================

class StressTestEngine:
    """
    Stress test engine that creates mock users and simulates signal processing.
    """
    
    def __init__(self, app=None, num_users: int = 1000):
        self.app = app
        self.num_users = num_users
        self.mock_users: List[Dict] = []
        self.created_user_ids: List[int] = []
        
    def create_dummy_users(self) -> List[int]:
        """
        Create dummy users in the database for stress testing.
        Returns list of created user IDs.
        """
        from models import db, User
        
        logger.info(f"📝 Creating {self.num_users} dummy test users...")
        
        with self.app.app_context():
            created_ids = []
            batch_size = 100
            
            for batch_start in range(0, self.num_users, batch_size):
                batch_end = min(batch_start + batch_size, self.num_users)
                batch_users = []
                
                for i in range(batch_start, batch_end):
                    # Generate unique username with timestamp
                    ts = int(time.time() * 1000) % 100000
                    random_suffix = ''.join(random.choices(string.ascii_lowercase, k=4))
                    username = f"stress_user_{i}_{ts}_{random_suffix}"
                    
                    user = User(
                        username=username,
                        first_name=f"Test{i}",
                        last_name="User",
                        is_active=True,
                        is_paused=False,
                        role='user',
                        custom_risk=3.0,
                        custom_leverage=20,
                        max_positions=5,
                        risk_multiplier=1.0,
                    )
                    user.set_password("test_password_123")
                    batch_users.append(user)
                
                db.session.add_all(batch_users)
                db.session.commit()
                
                for user in batch_users:
                    created_ids.append(user.id)
                
                logger.info(f"   ✓ Created batch {batch_start}-{batch_end} ({len(created_ids)}/{self.num_users})")
            
            self.created_user_ids = created_ids
            logger.info(f"✅ Created {len(created_ids)} dummy users")
            return created_ids
    
    def create_mock_clients(self, user_ids: List[int], 
                           latency_mean_ms: float = 10.0,
                           latency_std_ms: float = 5.0) -> List[Dict]:
        """
        Create mock exchange clients for all users.
        Simulates realistic latency distribution.
        """
        from models import db, User
        
        logger.info(f"🔧 Creating mock exchange clients for {len(user_ids)} users...")
        
        mock_clients = []
        
        with self.app.app_context():
            for i, user_id in enumerate(user_ids):
                user = db.session.get(User, user_id)
                if not user:
                    continue
                
                # Random latency for this user (simulating network variance)
                user_latency = max(1.0, random.gauss(latency_mean_ms, latency_std_ms))
                
                # Mix of Binance and CCXT clients (realistic scenario)
                if random.random() < 0.7:  # 70% Binance
                    client = MockBinanceClient(
                        user_id=user.id,
                        username=user.username,
                        simulated_latency_ms=user_latency
                    )
                    is_ccxt = False
                    is_async = False
                else:  # 30% other exchanges (OKX, Bybit, etc.)
                    exchange_type = random.choice(['okx', 'bybit', 'bitget'])
                    client = MockCCXTExchange(
                        user_id=user.id,
                        username=user.username,
                        exchange_type=exchange_type,
                        simulated_latency_ms=user_latency
                    )
                    is_ccxt = True
                    is_async = True
                
                mock_clients.append({
                    'id': user.id,
                    'exchange_id': None,
                    'name': user.username,
                    'fullname': f"{user.first_name} {user.last_name}".strip(),
                    'client': client,
                    'exchange_type': 'binance' if not is_ccxt else exchange_type,
                    'exchange_name': 'Mock Exchange',
                    'is_paused': False,
                    'risk': user.custom_risk,
                    'leverage': user.custom_leverage,
                    'max_pos': user.max_positions,
                    'risk_multiplier': user.risk_multiplier or 1.0,
                    'telegram_chat_id': None,
                    'lock': asyncio.Lock() if is_async else threading.Lock(),
                    'is_ccxt': is_ccxt,
                    'is_async': is_async,
                    'proxy': None,
                })
                
                if (i + 1) % 200 == 0:
                    logger.info(f"   ✓ Created {i + 1}/{len(user_ids)} mock clients")
        
        self.mock_users = mock_clients
        logger.info(f"✅ Created {len(mock_clients)} mock exchange clients")
        return mock_clients
    
    def cleanup_dummy_users(self):
        """Remove all dummy test users from database"""
        from models import db, User
        
        logger.info(f"🧹 Cleaning up {len(self.created_user_ids)} dummy users...")
        
        with self.app.app_context():
            # Delete users created during this test
            if self.created_user_ids:
                User.query.filter(User.id.in_(self.created_user_ids)).delete()
                db.session.commit()
                logger.info(f"   ✓ Deleted {len(self.created_user_ids)} users by ID")
            
            # Also clean up any orphaned stress test users
            orphaned = User.query.filter(User.username.like('stress_user_%')).delete()
            db.session.commit()
            if orphaned:
                logger.info(f"   ✓ Deleted {orphaned} orphaned stress test users")
        
        logger.info("✅ Cleanup complete")


# ==================== INSTRUMENTED TRADING ENGINE ====================

async def execute_trade_instrumented(user_data: dict, signal: dict, 
                                     master_entry_price: float = 65000.0,
                                     master_balance: float = 100000.0,
                                     master_trade_cost: float = 3000.0):
    """
    Instrumented trade execution that records latency.
    Simplified version of the real execute_trade_async.
    """
    user_id = user_data['id']
    username = user_data['name']
    
    try:
        client = user_data['client']
        is_async = user_data.get('is_async', False)
        
        symbol = signal['symbol']
        action = signal['action']
        risk = signal.get('risk', 3.0)
        leverage = signal.get('lev', 20)
        
        # Simulate the trade execution flow
        if is_async:
            # Async CCXT client
            await client.fetch_balance()
            await client.set_leverage(leverage, f"{symbol}/USDT:USDT")
            
            side = 'buy' if action == 'long' else 'sell'
            await client.create_order(
                symbol=f"{symbol}/USDT:USDT",
                type='market',
                side=side,
                amount=0.001
            )
        else:
            # Sync Binance client
            client.futures_account_balance()
            client.futures_change_leverage(symbol=symbol, leverage=leverage)
            
            side = 'BUY' if action == 'long' else 'SELL'
            client.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=0.001
            )
        
        # Record successful order
        latency_tracker.record_order(user_id, username, success=True)
        return {'status': 'success', 'user_id': user_id}
        
    except Exception as e:
        latency_tracker.record_order(user_id, username, success=False)
        return {'status': 'error', 'user_id': user_id, 'error': str(e)}


async def process_signal_batch_instrumented(users: List[Dict], signal: dict):
    """
    Process signal for all users concurrently with instrumentation.
    """
    logger.info(f"🚀 Processing signal for {len(users)} users concurrently...")
    
    # Mark signal start time
    latency_tracker.set_signal_start()
    
    # Create tasks for all users
    tasks = []
    for user_data in users:
        task = execute_trade_instrumented(user_data, signal)
        tasks.append(task)
    
    # Execute all trades concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Count results
    success_count = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'success')
    error_count = len(results) - success_count
    
    return {'success': success_count, 'errors': error_count}


# ==================== MAIN STRESS TEST ====================

def run_stress_test(app, num_users: int = 1000, cleanup: bool = True):
    """
    Run the full stress test.
    
    Args:
        app: Flask application instance
        num_users: Number of dummy users to create
        cleanup: Whether to clean up dummy users after test
    """
    print("\n" + "=" * 70)
    print("🔥 BRAIN CAPITAL - LOAD STRESS TEST")
    print("=" * 70)
    print(f"📊 Test Configuration:")
    print(f"   • Target Users: {num_users}")
    print(f"   • Target Latency: < 500ms for all users")
    print(f"   • Cleanup After: {cleanup}")
    print("=" * 70 + "\n")
    
    test_engine = StressTestEngine(app=app, num_users=num_users)
    
    try:
        # Step 1: Create dummy users
        print("\n📝 STEP 1: Creating dummy users in database...")
        user_ids = test_engine.create_dummy_users()
        
        # Step 2: Create mock exchange clients
        print("\n🔧 STEP 2: Creating mock exchange clients...")
        mock_clients = test_engine.create_mock_clients(
            user_ids=user_ids,
            latency_mean_ms=10.0,  # Average 10ms simulated API latency
            latency_std_ms=5.0     # Standard deviation of 5ms
        )
        
        # Step 3: Simulate webhook signal
        print("\n📨 STEP 3: Simulating webhook signal...")
        test_signal = {
            'symbol': 'BTCUSDT',
            'action': 'long',
            'risk': 3.0,
            'lev': 20,
            'tp_perc': 5.0,
            'sl_perc': 2.0
        }
        logger.info(f"📊 Signal: {test_signal['action'].upper()} {test_signal['symbol']}")
        
        # Step 4: Execute signal and measure latency
        print("\n⚡ STEP 4: Executing signal for all users...")
        latency_tracker.clear()
        
        start_time = time.perf_counter()
        
        # Run the async batch processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                process_signal_batch_instrumented(mock_clients, test_signal)
            )
        finally:
            loop.close()
        
        end_time = time.perf_counter()
        total_time_ms = (end_time - start_time) * 1000
        
        # Step 5: Calculate and display results
        print("\n" + "=" * 70)
        print("📊 STRESS TEST RESULTS")
        print("=" * 70)
        
        stats = latency_tracker.get_statistics()
        
        if stats:
            print(f"\n📈 Execution Summary:")
            print(f"   • Total Users Processed: {stats['total_users']}")
            print(f"   • Successful Orders:     {stats['successful']}")
            print(f"   • Failed Orders:         {stats['failed']}")
            print(f"   • Total Wall Time:       {total_time_ms:.2f} ms")
            
            print(f"\n⏱️  Latency Distribution (Signal → Order Executed):")
            print(f"   • Min:    {stats['min_ms']:>8.2f} ms")
            print(f"   • Max:    {stats['max_ms']:>8.2f} ms")
            print(f"   • Mean:   {stats['mean_ms']:>8.2f} ms")
            print(f"   • Median: {stats['median_ms']:>8.2f} ms")
            print(f"   • StdDev: {stats['stdev_ms']:>8.2f} ms")
            
            print(f"\n📊 Percentile Latencies:")
            print(f"   • P50:    {stats['p50_ms']:>8.2f} ms  {'✅' if stats['p50_ms'] < 500 else '❌'}")
            print(f"   • P90:    {stats['p90_ms']:>8.2f} ms  {'✅' if stats['p90_ms'] < 500 else '❌'}")
            print(f"   • P95:    {stats['p95_ms']:>8.2f} ms  {'✅' if stats['p95_ms'] < 500 else '❌'}")
            print(f"   • P99:    {stats['p99_ms']:>8.2f} ms  {'✅' if stats['p99_ms'] < 500 else '❌'}")
            
            print(f"\n🎯 Target Assessment (< 500ms for all users):")
            target_met = stats['p99_ms'] < 500
            if target_met:
                print(f"   ✅ TARGET MET! P99 latency ({stats['p99_ms']:.2f}ms) < 500ms")
            else:
                print(f"   ❌ TARGET MISSED! P99 latency ({stats['p99_ms']:.2f}ms) >= 500ms")
            
            # Performance grade
            print(f"\n📝 Performance Grade:")
            if stats['p99_ms'] < 100:
                grade = "A+ (Excellent)"
            elif stats['p99_ms'] < 250:
                grade = "A (Very Good)"
            elif stats['p99_ms'] < 500:
                grade = "B (Good - Target Met)"
            elif stats['p99_ms'] < 1000:
                grade = "C (Acceptable)"
            else:
                grade = "D (Needs Improvement)"
            print(f"   Grade: {grade}")
            
            # Throughput
            throughput = stats['successful'] / (total_time_ms / 1000) if total_time_ms > 0 else 0
            print(f"\n🚀 Throughput: {throughput:.1f} orders/second")
            
        else:
            print("❌ No results collected - check for errors above")
        
        print("\n" + "=" * 70)
        
        return stats
        
    finally:
        # Step 6: Cleanup
        if cleanup:
            print("\n🧹 STEP 6: Cleaning up test data...")
            test_engine.cleanup_dummy_users()
        else:
            print(f"\n⚠️  Skipping cleanup - {len(test_engine.created_user_ids)} test users remain in database")
            print(f"   Run with --cleanup to remove them later")


def main():
    """Main entry point for stress test"""
    parser = argparse.ArgumentParser(description='Brain Capital Load Stress Test')
    parser.add_argument('--users', '-u', type=int, default=1000,
                       help='Number of dummy users to create (default: 1000)')
    parser.add_argument('--cleanup', '-c', action='store_true', default=True,
                       help='Cleanup dummy users after test (default: True)')
    parser.add_argument('--no-cleanup', action='store_true',
                       help='Skip cleanup - leave dummy users in database')
    parser.add_argument('--latency', '-l', type=float, default=10.0,
                       help='Mean simulated API latency in ms (default: 10)')
    parser.add_argument('--cleanup-only', action='store_true',
                       help='Only run cleanup of orphaned stress test users')
    
    args = parser.parse_args()
    
    # Import Flask app
    try:
        from app import app
        logger.info("✅ Flask app imported successfully")
    except ImportError as e:
        logger.error(f"❌ Failed to import Flask app: {e}")
        logger.error("   Make sure you're running from the project root directory")
        sys.exit(1)
    
    # Cleanup only mode
    if args.cleanup_only:
        print("\n🧹 Running cleanup of orphaned stress test users...")
        test_engine = StressTestEngine(app=app, num_users=0)
        test_engine.cleanup_dummy_users()
        print("✅ Cleanup complete")
        return
    
    # Run the stress test
    cleanup = not args.no_cleanup
    stats = run_stress_test(
        app=app,
        num_users=args.users,
        cleanup=cleanup
    )
    
    # Exit with appropriate code
    if stats and stats.get('p99_ms', float('inf')) < 500:
        print("\n✅ Stress test PASSED - Target latency met!")
        sys.exit(0)
    else:
        print("\n❌ Stress test FAILED - Target latency not met")
        sys.exit(1)


if __name__ == '__main__':
    main()

