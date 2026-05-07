import asyncio
from typing import Dict, Any, AsyncGenerator
import logging

logger = logging.getLogger(__name__)

class EventDispatcher:
    def __init__(self):
        # Dictionary of thread_id -> list of queues
        self.subscribers: Dict[str, list[asyncio.Queue]] = {}
        # Dictionary of thread_id -> list of historical messages
        self.history: Dict[str, list[Any]] = {}
        self.lock = asyncio.Lock()

    async def subscribe(self, thread_id: str) -> AsyncGenerator[Any, None]:
        queue = asyncio.Queue()
        
        async with self.lock:
            # 1. Send historical messages first
            if thread_id in self.history:
                for msg in self.history[thread_id]:
                    await queue.put(msg)
            
            # 2. Add to subscribers list
            if thread_id not in self.subscribers:
                self.subscribers[thread_id] = []
            self.subscribers[thread_id].append(queue)
        
        logger.info(f"New subscriber for thread {thread_id}. Sent {len(self.history.get(thread_id, []))} historical messages.")
        
        try:
            while True:
                item = await queue.get()
                if item is None: # Sentinel for end of stream
                    break
                yield item
        finally:
            async with self.lock:
                if thread_id in self.subscribers:
                    self.subscribers[thread_id].remove(queue)
                    if not self.subscribers[thread_id]:
                        del self.subscribers[thread_id]
                        # Optional: Clean up history if no more subscribers and stream ended? 
                        # Better to keep it for a while or clean it up explicitly.
            logger.info(f"Subscriber removed for thread {thread_id}")

    async def publish(self, thread_id: str, data: Any):
        async with self.lock:
            # 1. Store in history with an index
            if thread_id not in self.history:
                self.history[thread_id] = []
            
            # Add index to the data
            indexed_data = {**data, "index": len(self.history[thread_id])}
            self.history[thread_id].append(indexed_data)
            
            # 2. Send to active subscribers
            if thread_id in self.subscribers:
                for queue in self.subscribers[thread_id]:
                    await queue.put(indexed_data)

    async def end_stream(self, thread_id: str):
        async with self.lock:
            if thread_id in self.subscribers:
                for queue in self.subscribers[thread_id]:
                    await queue.put(None)
            
            # Optionally clear history after some time to avoid memory leak
            # For now, we'll keep it or you can add a cleanup task.
            # asyncio.create_task(self._cleanup(thread_id, delay=300))

    async def _cleanup(self, thread_id: str, delay: int):
        await asyncio.sleep(delay)
        async with self.lock:
            if thread_id in self.history:
                del self.history[thread_id]
                logger.info(f"History cleared for thread {thread_id}")

# Global dispatcher instance
event_dispatcher = EventDispatcher()
