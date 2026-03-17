"""CLAWSEUM Arena Engine - Scheduler.

Match scheduling system:
- Cron-like scheduler for recurring missions
- Queue management
- Priority handling
"""

from __future__ import annotations

import asyncio
import heapq
import json
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple
from enum import Enum, auto

from config import (
    MissionType,
    MatchConfig,
    MissionConfig,
    AgentConfig,
    generate_match_id,
    DEFAULT_MATCH_TICKS,
    MIN_AGENTS,
    MAX_AGENTS,
)

logger = logging.getLogger(__name__)


class ScheduleFrequency(Enum):
    """Frequency options for scheduled matches."""
    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"


@dataclass(order=True)
class ScheduledMatch:
    """A scheduled match with priority ordering."""
    # Use priority for heap ordering (lower = higher priority)
    priority: int
    scheduled_at: datetime = field(compare=False)
    match_config: MatchConfig = field(compare=False)
    schedule_id: str = field(compare=False)
    frequency: ScheduleFrequency = field(compare=False, default=ScheduleFrequency.ONCE)
    cron_expression: Optional[str] = field(compare=False, default=None)
    next_run: Optional[datetime] = field(compare=False, default=None)
    max_runs: Optional[int] = field(compare=False, default=None)
    run_count: int = field(compare=False, default=0)
    enabled: bool = field(compare=False, default=True)
    metadata: Dict[str, Any] = field(compare=False, default_factory=dict)


@dataclass
class QueueItem:
    """An item in the execution queue."""
    match_id: str
    config: MatchConfig
    queued_at: datetime
    priority: int
    attempts: int = 0
    max_attempts: int = 3


MatchExecutor = Callable[[MatchConfig], Coroutine[Any, Any, Any]]


class MatchScheduler:
    """Scheduler for managing match execution."""
    
    def __init__(
        self,
        executor: Optional[MatchExecutor] = None,
        max_concurrent: int = 3,
        database: Optional[Any] = None,
    ):
        self.executor = executor
        self.max_concurrent = max_concurrent
        self.database = database
        
        # Scheduling state
        self._schedules: Dict[str, ScheduledMatch] = {}
        self._queue: List[Tuple[int, datetime, str, QueueItem]] = []  # heap
        self._queue_items: Dict[str, QueueItem] = {}
        self._running: Set[str] = set()
        self._completed: Dict[str, Any] = {}
        self._failed: Dict[str, Tuple[Any, str]] = {}
        
        # Control
        self._running_flag = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)
    
    async def start(self) -> None:
        """Start the scheduler."""
        async with self._lock:
            if self._running_flag:
                return
            self._running_flag = True
            self._task = asyncio.create_task(self._scheduler_loop())
            logger.info("Match scheduler started")
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        async with self._lock:
            if not self._running_flag:
                return
            self._running_flag = False
            if self._task:
                self._task.cancel()
        
        if self._task:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Match scheduler stopped")
    
    async def schedule(
        self,
        match_config: MatchConfig,
        priority: int = 0,
        frequency: ScheduleFrequency = ScheduleFrequency.ONCE,
        cron_expression: Optional[str] = None,
        max_runs: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Schedule a new match or recurring schedule."""
        schedule_id = f"sch_{generate_match_id()}"
        
        scheduled = ScheduledMatch(
            schedule_id=schedule_id,
            priority=priority,
            scheduled_at=match_config.scheduled_at or datetime.now(timezone.utc),
            match_config=match_config,
            frequency=frequency,
            cron_expression=cron_expression,
            next_run=match_config.scheduled_at or datetime.now(timezone.utc),
            max_runs=max_runs,
            metadata=metadata or {},
        )
        
        async with self._lock:
            self._schedules[schedule_id] = scheduled
            
            # If it's a one-time schedule, add to queue immediately
            if frequency == ScheduleFrequency.ONCE:
                await self._enqueue_scheduled_match(scheduled)
        
        logger.info(f"Scheduled match {schedule_id} for {scheduled.scheduled_at}")
        return schedule_id
    
    async def unschedule(self, schedule_id: str) -> bool:
        """Remove a scheduled match."""
        async with self._lock:
            if schedule_id in self._schedules:
                self._schedules[schedule_id].enabled = False
                del self._schedules[schedule_id]
                logger.info(f"Unscheduled {schedule_id}")
                return True
            return False
    
    async def queue_match(
        self,
        config: MatchConfig,
        priority: int = 0,
    ) -> str:
        """Queue a match for immediate execution (when slot available)."""
        match_id = config.match_id
        
        item = QueueItem(
            match_id=match_id,
            config=config,
            queued_at=datetime.now(timezone.utc),
            priority=priority,
        )
        
        async with self._lock:
            heapq.heappush(
                self._queue,
                (priority, item.queued_at, match_id, item)
            )
            self._queue_items[match_id] = item
            self._condition.notify()
        
        logger.info(f"Queued match {match_id} with priority {priority}")
        return match_id
    
    async def cancel_queued_match(self, match_id: str) -> bool:
        """Cancel a queued match."""
        async with self._lock:
            if match_id in self._queue_items:
                del self._queue_items[match_id]
                # Rebuild heap without the cancelled item
                new_queue = []
                for prio, ts, mid, item in self._queue:
                    if mid != match_id:
                        new_queue.append((prio, ts, mid, item))
                heapq.heapify(new_queue)
                self._queue = new_queue
                return True
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """Get scheduler status."""
        async with self._lock:
            return {
                "running": self._running_flag,
                "schedules_count": len(self._schedules),
                "queue_length": len(self._queue),
                "running_matches": list(self._running),
                "completed_count": len(self._completed),
                "failed_count": len(self._failed),
            }
    
    async def get_schedule(self, schedule_id: str) -> Optional[ScheduledMatch]:
        """Get a scheduled match by ID."""
        async with self._lock:
            return self._schedules.get(schedule_id)
    
    async def list_schedules(
        self,
        enabled_only: bool = True,
    ) -> List[ScheduledMatch]:
        """List all scheduled matches."""
        async with self._lock:
            schedules = list(self._schedules.values())
            if enabled_only:
                schedules = [s for s in schedules if s.enabled]
            return sorted(schedules, key=lambda s: s.scheduled_at)
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while True:
            async with self._lock:
                if not self._running_flag:
                    break
                
                # Check for recurring schedules that need to be queued
                now = datetime.now(timezone.utc)
                for schedule in self._schedules.values():
                    if not schedule.enabled:
                        continue
                    if schedule.frequency == ScheduleFrequency.ONCE:
                        continue
                    if schedule.max_runs and schedule.run_count >= schedule.max_runs:
                        continue
                    if schedule.next_run and schedule.next_run <= now:
                        await self._enqueue_scheduled_match(schedule)
                        schedule.next_run = self._calculate_next_run(schedule)
                        schedule.run_count += 1
                
                # Check if we can start a new match
                can_start = len(self._running) < self.max_concurrent and self._queue
                
                if not can_start:
                    # Wait for something to change
                    try:
                        await asyncio.wait_for(
                            self._condition.wait(),
                            timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        pass
                    continue
                
                # Get next item from queue
                if self._queue:
                    _, _, match_id, item = heapq.heappop(self._queue)
                    if match_id in self._queue_items:
                        del self._queue_items[match_id]
                        self._running.add(match_id)
                        
                        # Start execution
                        asyncio.create_task(self._execute_match(match_id, item))
            
            # Brief yield
            await asyncio.sleep(0.01)
    
    async def _enqueue_scheduled_match(self, scheduled: ScheduledMatch) -> None:
        """Enqueue a scheduled match."""
        item = QueueItem(
            match_id=scheduled.match_config.match_id,
            config=scheduled.match_config,
            queued_at=datetime.now(timezone.utc),
            priority=scheduled.priority,
        )
        
        heapq.heappush(
            self._queue,
            (scheduled.priority, item.queued_at, item.match_id, item)
        )
        self._queue_items[item.match_id] = item
        self._condition.notify()
    
    async def _execute_match(self, match_id: str, item: QueueItem) -> None:
        """Execute a match."""
        logger.info(f"Executing match {match_id}")
        
        try:
            if self.executor:
                result = await self.executor(item.config)
                async with self._lock:
                    self._completed[match_id] = result
            else:
                logger.warning(f"No executor configured for match {match_id}")
        
        except Exception as e:
            logger.exception(f"Match {match_id} failed: {e}")
            async with self._lock:
                self._failed[match_id] = (item, str(e))
                
                # Retry logic
                if item.attempts < item.max_attempts:
                    item.attempts += 1
                    # Re-queue with lower priority
                    heapq.heappush(
                        self._queue,
                        (item.priority + item.attempts * 10, datetime.now(timezone.utc), match_id, item)
                    )
                    self._queue_items[match_id] = item
                    logger.info(f"Re-queued match {match_id} (attempt {item.attempts})")
        
        finally:
            async with self._lock:
                self._running.discard(match_id)
                self._condition.notify()
    
    def _calculate_next_run(self, schedule: ScheduledMatch) -> Optional[datetime]:
        """Calculate the next run time for a recurring schedule."""
        now = datetime.now(timezone.utc)
        
        if schedule.frequency == ScheduleFrequency.HOURLY:
            return now + timedelta(hours=1)
        elif schedule.frequency == ScheduleFrequency.DAILY:
            return now + timedelta(days=1)
        elif schedule.frequency == ScheduleFrequency.WEEKLY:
            return now + timedelta(weeks=1)
        elif schedule.frequency == ScheduleFrequency.CUSTOM and schedule.cron_expression:
            # Parse simple cron (minute hour)
            return self._parse_cron(schedule.cron_expression, now)
        
        return None
    
    def _parse_cron(self, cron: str, base: datetime) -> Optional[datetime]:
        """Parse a simple cron expression."""
        try:
            parts = cron.split()
            if len(parts) >= 2:
                minute = int(parts[0])
                hour = int(parts[1])
                
                next_run = base.replace(minute=minute, hour=hour, second=0, microsecond=0)
                if next_run <= base:
                    next_run += timedelta(days=1)
                return next_run
        except (ValueError, IndexError):
            pass
        
        return base + timedelta(hours=1)  # Default fallback


class QuickMatchBuilder:
    """Builder for common match configurations."""
    
    @staticmethod
    def resource_race(
        agent_count: int = 4,
        ticks: int = DEFAULT_MATCH_TICKS,
        seed: Optional[int] = None,
    ) -> MatchConfig:
        """Build a resource race match with random bots."""
        if not MIN_AGENTS <= agent_count <= MAX_AGENTS:
            raise ValueError(f"Agent count must be between {MIN_AGENTS} and {MAX_AGENTS}")
        
        rng = random.Random(seed)
        codenames = [
            "Astra", "Vanta", "Milo", "Nyx", "Quartz", "Rook", "Sable", "Iris",
            "Kite", "Flux", "Echo", "Nova",
        ]
        rng.shuffle(codenames)
        strategies = ["greedy", "balanced", "aggressive", "opportunist", "cooperative", "deceptive"]
        
        agents = []
        for i in range(agent_count):
            agents.append(AgentConfig(
                agent_id=f"bot-{i+1}",
                name=codenames[i],
                strategy=rng.choice(strategies),
            ))
        
        return MatchConfig(
            mission=MissionConfig(
                mission_type=MissionType.RESOURCE_RACE,
                ticks=ticks,
            ),
            agents=agents,
            seed=seed,
        )
    
    @staticmethod
    def multi_phase(
        phases: List[MissionType],
        agent_count: int = 4,
        ticks: int = DEFAULT_MATCH_TICKS,
        seed: Optional[int] = None,
    ) -> MatchConfig:
        """Build a multi-phase match with random bots."""
        if not MIN_AGENTS <= agent_count <= MAX_AGENTS:
            raise ValueError(f"Agent count must be between {MIN_AGENTS} and {MAX_AGENTS}")
        
        rng = random.Random(seed)
        codenames = [
            "Astra", "Vanta", "Milo", "Nyx", "Quartz", "Rook", "Sable", "Iris",
            "Kite", "Flux", "Echo", "Nova",
        ]
        rng.shuffle(codenames)
        strategies = ["greedy", "balanced", "aggressive", "opportunist", "cooperative", "deceptive"]
        
        agents = []
        for i in range(agent_count):
            agents.append(AgentConfig(
                agent_id=f"bot-{i+1}",
                name=codenames[i],
                strategy=rng.choice(strategies),
            ))
        
        return MatchConfig(
            mission=MissionConfig(
                mission_type=phases[0] if phases else MissionType.RESOURCE_RACE,
                ticks=ticks,
                phases=phases,
            ),
            agents=agents,
            seed=seed,
        )
    
    @staticmethod
    def from_agent_configs(
        agents: List[AgentConfig],
        mission_type: MissionType = MissionType.RESOURCE_RACE,
        ticks: int = DEFAULT_MATCH_TICKS,
        seed: Optional[int] = None,
    ) -> MatchConfig:
        """Build a match from existing agent configs."""
        return MatchConfig(
            mission=MissionConfig(
                mission_type=mission_type,
                ticks=ticks,
            ),
            agents=agents,
            seed=seed,
        )


# Convenience functions for common scheduling patterns

async def schedule_hourly_tournament(
    scheduler: MatchScheduler,
    agent_count: int = 6,
    ticks: int = 30,
) -> str:
    """Schedule an hourly tournament."""
    config = QuickMatchBuilder.resource_race(agent_count=agent_count, ticks=ticks)
    
    return await scheduler.schedule(
        match_config=config,
        priority=5,
        frequency=ScheduleFrequency.HOURLY,
        metadata={"type": "hourly_tournament"},
    )


async def schedule_daily_championship(
    scheduler: MatchScheduler,
    agent_count: int = 8,
    ticks: int = 50,
) -> str:
    """Schedule a daily championship with all phases."""
    config = QuickMatchBuilder.multi_phase(
        phases=[MissionType.RESOURCE_RACE, MissionType.NEGOTIATION, MissionType.SABOTAGE],
        agent_count=agent_count,
        ticks=ticks,
    )
    
    return await scheduler.schedule(
        match_config=config,
        priority=10,
        frequency=ScheduleFrequency.DAILY,
        metadata={"type": "daily_championship"},
    )
