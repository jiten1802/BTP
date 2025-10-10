import os
import threading
import random
from typing import List
from dotenv import load_dotenv

load_dotenv()

class APIKeyManager:
    """
    Manages multiple Gemini API keys with rotation strategies.
    """
    
    def __init__(self):
        self.keys = self._load_api_keys()
        self.current_index = 0
        self.lock = threading.Lock()
        self.thread_keys = {}  # Store key per thread
        self.key_stats = {key: {"calls": 0, "errors": 0} for key in self.keys}
        
        if not self.keys:
            raise ValueError("No API keys found in environment variables")
        
        print(f"🔑 Loaded {len(self.keys)} API keys for rotation")
    
    def _load_api_keys(self) -> List[str]:
        """Load all available API keys from environment variables"""
        keys = []
        
        # Try to load multiple keys
        for i in range(1, 10):  # Check up to 9 keys
            key = os.getenv(f"GROQ_API_KEY_{i}")
            if key:
                keys.append(key.strip())
            else:
                break
        
        # # Also check for the original key name
        # original_key = os.getenv("GROQ_API_KEY")
        # if original_key and original_key not in keys:
        #     keys.append(original_key.strip())
        
        return keys
    
    def get_random_key(self) -> str:
        """Get a random API key"""
        return random.choice(self.keys)
    
    def get_round_robin_key(self) -> str:
        """Get next key in round-robin fashion (thread-safe)"""
        with self.lock:
            key = self.keys[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.keys)
            return key
    
    def get_key_for_thread(self) -> str:
        """Assign a specific key to each thread (best for concurrency)"""
        thread_id = threading.get_ident()
        
        if thread_id not in self.thread_keys:
            with self.lock:
                # Assign keys evenly across threads
                key_index = len(self.thread_keys) % len(self.keys)
                self.thread_keys[thread_id] = self.keys[key_index]
                print(f"🧵 Thread {thread_id} assigned key {key_index + 1}")
        
        return self.thread_keys[thread_id]
    
    def get_least_used_key(self) -> str:
        """Get the key with the least number of calls"""
        with self.lock:
            # Find key with minimum calls
            min_calls = min(self.key_stats[key]["calls"] for key in self.keys)
            for key in self.keys:
                if self.key_stats[key]["calls"] == min_calls:
                    return key
            return self.keys[0]  # Fallback
    
    def record_api_call(self, key: str, success: bool = True):
        """Record API call statistics"""
        with self.lock:
            if key in self.key_stats:
                self.key_stats[key]["calls"] += 1
                if not success:
                    self.key_stats[key]["errors"] += 1
    
    def get_key_stats(self) -> dict:
        """Get statistics for all keys"""
        with self.lock:
            return {
                f"Key_{i+1}": {
                    "calls": self.key_stats[key]["calls"],
                    "errors": self.key_stats[key]["errors"],
                    "error_rate": self.key_stats[key]["errors"] / max(self.key_stats[key]["calls"], 1)
                }
                for i, key in enumerate(self.keys)
            }
    
    def print_stats(self):
        """Print key usage statistics"""
        stats = self.get_key_stats()
        print("\n📊 API Key Usage Statistics:")
        for key_name, stat in stats.items():
            print(f"  {key_name}: {stat['calls']} calls, {stat['errors']} errors ({stat['error_rate']:.1%} error rate)")
        print()

# Global instance
api_key_manager = APIKeyManager()
