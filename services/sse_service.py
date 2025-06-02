import asyncio
import logging
import json
import uuid
from typing import Dict, Optional, Any, AsyncGenerator
from datetime import datetime
from collections import defaultdict
from models.processing_models import ProcessingUpdate, ProcessingStatus, ProcessingJob

logger = logging.getLogger(__name__)

class SSEService:
    """Service for managing Server-Sent Events connections and broadcasting updates."""
    
    def __init__(self):
        # Dictionary to store active connections: {job_id: [queue1, queue2, ...]}
        self.connections: Dict[str, list] = defaultdict(list)
        # Dictionary to store processing jobs: {job_id: ProcessingJob}
        self.jobs: Dict[str, ProcessingJob] = {}
        logger.info("SSE Service initialized")
    
    def create_job(self, video_url: str) -> str:
        """
        Create a new processing job.
        
        Args:
            video_url: YouTube URL to process
            
        Returns:
            str: Job ID
        """
        job_id = str(uuid.uuid4())
        job = ProcessingJob(
            id=job_id,
            video_url=video_url,
            status=ProcessingStatus.CREATED,
            created_at=datetime.utcnow()
        )
        self.jobs[job_id] = job
        
        logger.info(f"Created processing job {job_id} for URL: {video_url}")
        return job_id
    
    def get_job(self, job_id: str) -> Optional[ProcessingJob]:
        """Get processing job by ID."""
        return self.jobs.get(job_id)
    
    def update_job(self, job_id: str, **updates):
        """Update processing job with new data."""
        if job_id in self.jobs:
            job = self.jobs[job_id]
            for key, value in updates.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            job.updated_at = datetime.utcnow()
    
    async def add_connection(self, job_id: str) -> AsyncGenerator[str, None]:
        """
        Add a new SSE connection for a job.
        
        Args:
            job_id: Processing job ID
            
        Yields:
            str: SSE formatted messages
        """
        # Create a queue for this connection
        queue = asyncio.Queue()
        self.connections[job_id].append(queue)
        
        logger.info(f"Added SSE connection for job {job_id}. Total connections: {len(self.connections[job_id])}")
        
        try:
            # Send initial connection message
            initial_message = self._format_sse_message({
                "type": "connection",
                "job_id": job_id,
                "message": "Connected to processing stream",
                "timestamp": datetime.utcnow().isoformat()
            })
            yield initial_message
            
            # Send current job status if exists
            if job_id in self.jobs:
                job = self.jobs[job_id]
                status_message = self._format_sse_message({
                    "type": "status",
                    "job_id": job_id,
                    "status": job.status.value,
                    "progress": job.progress_percentage,
                    "message": f"Current status: {job.status.value}",
                    "timestamp": datetime.utcnow().isoformat()
                })
                yield status_message
            
            # Listen for updates
            while True:
                try:
                    # Wait for message with timeout
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield self._format_sse_message(message)
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    heartbeat = self._format_sse_message({
                        "type": "heartbeat",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    yield heartbeat
                    
        except asyncio.CancelledError:
            logger.info(f"SSE connection cancelled for job {job_id}")
        except Exception as e:
            logger.error(f"Error in SSE connection for job {job_id}: {str(e)}")
        finally:
            # Clean up connection
            if queue in self.connections[job_id]:
                self.connections[job_id].remove(queue)
            if not self.connections[job_id]:
                del self.connections[job_id]
            logger.info(f"Removed SSE connection for job {job_id}")
    
    async def broadcast_update(self, job_id: str, update: ProcessingUpdate):
        """
        Broadcast an update to all connections for a job.
        
        Args:
            job_id: Processing job ID
            update: Update to broadcast
        """
        if job_id not in self.connections:
            logger.debug(f"No active connections for job {job_id}")
            return
        
        # Update job record
        self.update_job(
            job_id,
            status=update.status,
            current_step=update.step,
            progress_percentage=update.progress,
            error_message=update.error
        )
        
        # Prepare message
        message_data = {
            "type": update.type,
            "job_id": update.job_id,
            "video_id": update.video_id,
            "status": update.status.value,
            "step": update.step,
            "progress": update.progress,
            "message": update.message,
            "data": update.data,
            "timestamp": update.timestamp.isoformat(),
            "error": update.error
        }
        
        # Broadcast to all connections
        connections = self.connections[job_id].copy()  # Copy to avoid modification during iteration
        for queue in connections:
            try:
                await queue.put(message_data)
            except Exception as e:
                logger.error(f"Failed to send message to connection: {str(e)}")
                # Remove failed connection
                if queue in self.connections[job_id]:
                    self.connections[job_id].remove(queue)
        
        logger.debug(f"Broadcasted update to {len(connections)} connections for job {job_id}")
    
    def _format_sse_message(self, data: dict) -> str:
        """Format data as SSE message."""
        return f"data: {json.dumps(data)}\n\n"
    
    def get_connection_count(self, job_id: str) -> int:
        """Get number of active connections for a job."""
        return len(self.connections.get(job_id, []))
    
    def get_total_connections(self) -> int:
        """Get total number of active connections."""
        return sum(len(queues) for queues in self.connections.values())

# Create global SSE service instance
sse_service = SSEService()