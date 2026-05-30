import time

class TokenRateLimiter:
    def __init__(self):
        self.r = {}
    
    def is_allowed(self,user_id : str, capacity : int, refill_rate : float) -> bool:
        key = f"limiter:{user_id}"
        now = time.time()

        bucket = self.r.get(key)

        if not bucket:
            current_tokens = float(capacity)
            last_time = now
        else:
            current_tokens = float(bucket["tokens"])
            last_time = float(bucket["last_time"])

        time_passed = now - last_time
        new_tokens = min(float(capacity), current_tokens + (time_passed * refill_rate))

        if new_tokens >= 1:
            new_tokens -= 1
            allowed = True
        else:
            allowed = False
        
        self.r[key] = {
            "tokens" : new_tokens,
            "last_time" : now
        }

        return allowed

ai_chat_limiter = TokenRateLimiter()