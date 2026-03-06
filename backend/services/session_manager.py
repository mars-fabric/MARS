"""
Session Manager Service

Provides database-backed session lifecycle management:
- Create sessions with initial state
- Save session state periodically during execution
- Load session state for resumption
- Suspend, resume, complete sessions
- Cleanup expired sessions
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from core.logging import get_logger

logger = get_logger(__name__)


class SessionManager:
    """
    Manages session lifecycle with database persistence.

    Session states:
    - active: Currently running or ready to run
    - suspended: Paused by user, can be resumed
    - completed: Finished successfully
    - expired: Timed out or cleaned up
    """

    def __init__(self, db_factory: Callable):
        """
        Initialize the session manager.

        Args:
            db_factory: Callable that returns a database session
        """
        self.db_factory = db_factory
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 60  # seconds
        self._session_ttl = 24 * 60 * 60  # 24 hours default

    async def start(self):
        """Start background cleanup task"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("SessionManager started with cleanup interval %ds", self._cleanup_interval)

    async def stop(self):
        """Stop background cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("SessionManager stopped")

    # ==================== Session Lifecycle ====================

    def create_session(
        self,
        mode: str,
        config: Dict[str, Any],
        user_id: Optional[str] = None,
        name: Optional[str] = None
    ) -> str:
        """
        Create a new session.

        Args:
            mode: Workflow mode (copilot, planning-control, etc.)
            config: Session configuration
            user_id: Optional user identifier
            name: Optional session name

        Returns:
            session_id (UUID string)
        """
        from cmbagent.database.models import Session, SessionState

        db = self.db_factory()
        try:
            session_id = str(uuid4())
            session_name = name or f"{mode}_{datetime.now():%Y%m%d_%H%M%S}"

            # Create parent session record
            session = Session(
                id=session_id,
                user_id=user_id,
                name=session_name,
                status="active",
                meta=config
            )
            db.add(session)

            # Create session state record
            state = SessionState(
                session_id=session_id,
                mode=mode,
                conversation_history=[],
                context_variables={},
                current_phase="init",
                status="active"
            )
            db.add(state)

            db.commit()
            logger.info("Created session %s for mode %s", session_id, mode)
            return session_id

        except Exception as e:
            db.rollback()
            logger.error("Failed to create session: %s", e)
            raise
        finally:
            db.close()

    def save_session_state(
        self,
        session_id: str,
        conversation_history: List[Dict[str, Any]],
        context_variables: Dict[str, Any] = None,
        current_phase: str = None,
        current_step: Optional[int] = None,
        plan_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Save session state to database.

        Called periodically during execution to persist state.
        Uses optimistic locking via version column with single retry.

        Args:
            session_id: Session identifier
            conversation_history: List of message dictionaries
            context_variables: Key-value context (must be JSON-serializable)
            current_phase: Current workflow phase
            current_step: Current step number (optional)
            plan_data: Plan structure (optional)

        Returns:
            True if saved successfully, False otherwise
        """
        from cmbagent.database.models import SessionState

        for attempt in range(2):  # retry once on version conflict
            db = self.db_factory()
            try:
                state = db.query(SessionState).filter(
                    SessionState.session_id == session_id,
                    SessionState.status == "active"
                ).first()

                if not state:
                    logger.warning("No active session state found for %s", session_id)
                    return False

                # Update state
                state.conversation_history = conversation_history
                if context_variables is not None:
                    state.context_variables = context_variables
                if current_phase is not None:
                    state.current_phase = current_phase
                state.current_step = current_step
                if plan_data is not None:
                    state.plan_data = plan_data
                state.updated_at = datetime.now(timezone.utc)
                state.version += 1

                db.commit()
                logger.debug("Saved session state for %s (version %d)", session_id, state.version)
                return True

            except Exception as e:
                db.rollback()
                if attempt == 0 and "stale" in str(e).lower():
                    logger.warning("Version conflict for session %s, retrying", session_id)
                    continue
                logger.error("Failed to save session state for %s: %s", session_id, e)
                return False
            finally:
                db.close()

        return False

    def load_session_state(self, session_id: str, include_completed: bool = False) -> Optional[Dict[str, Any]]:
        """
        Load session state for resumption or viewing.

        Args:
            session_id: Session identifier
            include_completed: If True, also return completed/expired sessions (for viewing)

        Returns:
            Dictionary with session state, or None if not found
        """
        from cmbagent.database.models import Session, SessionState

        db = self.db_factory()
        try:
            if include_completed:
                state = db.query(SessionState).filter(
                    SessionState.session_id == session_id,
                ).first()
            else:
                state = db.query(SessionState).filter(
                    SessionState.session_id == session_id,
                    SessionState.status.in_(["active", "suspended"])
                ).first()

            if not state:
                logger.warning("No resumable session found for %s", session_id)
                return None

            # Get parent session for config
            session = db.query(Session).filter(Session.id == session_id).first()

            result = {
                "session_id": session_id,
                "mode": state.mode,
                "conversation_history": state.conversation_history or [],
                "context_variables": state.context_variables or {},
                "current_phase": state.current_phase,
                "current_step": state.current_step,
                "plan_data": state.plan_data,
                "status": state.status,
                "config": session.meta if session else {},
                "created_at": state.created_at,
                "updated_at": state.updated_at,
                "version": state.version
            }

            logger.info("Loaded session state for %s (version %d)", session_id, state.version)
            return result

        except Exception as e:
            logger.error("Failed to load session state for %s: %s", session_id, e)
            return None
        finally:
            db.close()

    def suspend_session(self, session_id: str) -> bool:
        """
        Suspend a session for later resumption.

        Args:
            session_id: Session identifier

        Returns:
            True if suspended successfully
        """
        from cmbagent.database.models import SessionState

        db = self.db_factory()
        try:
            result = db.query(SessionState).filter(
                SessionState.session_id == session_id,
                SessionState.status == "active"
            ).update({
                "status": "suspended",
                "updated_at": datetime.now(timezone.utc)
            })

            db.commit()

            if result > 0:
                logger.info("Suspended session %s", session_id)
                return True
            else:
                logger.warning("No active session to suspend: %s", session_id)
                return False

        except Exception as e:
            db.rollback()
            logger.error("Failed to suspend session %s: %s", session_id, e)
            return False
        finally:
            db.close()

    def resume_session(self, session_id: str) -> bool:
        """
        Resume a suspended session.

        Args:
            session_id: Session identifier

        Returns:
            True if resumed successfully
        """
        from cmbagent.database.models import SessionState

        db = self.db_factory()
        try:
            result = db.query(SessionState).filter(
                SessionState.session_id == session_id,
                SessionState.status == "suspended"
            ).update({
                "status": "active",
                "updated_at": datetime.now(timezone.utc)
            })

            db.commit()

            if result > 0:
                logger.info("Resumed session %s", session_id)
                return True
            else:
                logger.warning("No suspended session to resume: %s", session_id)
                return False

        except Exception as e:
            db.rollback()
            logger.error("Failed to resume session %s: %s", session_id, e)
            return False
        finally:
            db.close()

    def complete_session(self, session_id: str) -> bool:
        """
        Mark a session as completed.

        Args:
            session_id: Session identifier

        Returns:
            True if completed successfully
        """
        from cmbagent.database.models import SessionState

        db = self.db_factory()
        try:
            result = db.query(SessionState).filter(
                SessionState.session_id == session_id
            ).update({
                "status": "completed",
                "updated_at": datetime.now(timezone.utc)
            })

            db.commit()

            if result > 0:
                logger.info("Completed session %s", session_id)
                return True
            return False

        except Exception as e:
            db.rollback()
            logger.error("Failed to complete session %s: %s", session_id, e)
            return False
        finally:
            db.close()

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all associated data.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted successfully
        """
        from cmbagent.database.models import Session

        db = self.db_factory()
        try:
            session = db.query(Session).filter(Session.id == session_id).first()
            if not session:
                return False

            db.delete(session)  # Cascade deletes session_states
            db.commit()

            logger.info("Deleted session %s", session_id)
            return True

        except Exception as e:
            db.rollback()
            logger.error("Failed to delete session %s: %s", session_id, e)
            return False
        finally:
            db.close()

    # ==================== Session Queries ====================

    def list_sessions(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        mode: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List sessions with optional filters.

        Args:
            user_id: Filter by user
            status: Filter by status (active, suspended, completed)
            mode: Filter by workflow mode
            limit: Maximum number of results

        Returns:
            List of session summaries
        """
        from cmbagent.database.models import Session, SessionState

        db = self.db_factory()
        try:
            query = db.query(
                Session.id,
                Session.name,
                Session.created_at,
                Session.last_active_at,
                SessionState.mode,
                SessionState.status,
                SessionState.current_phase,
                SessionState.updated_at
            ).join(
                SessionState, Session.id == SessionState.session_id
            )

            if user_id:
                query = query.filter(Session.user_id == user_id)
            if status:
                query = query.filter(SessionState.status == status)
            if mode:
                query = query.filter(SessionState.mode == mode)

            # SessionState can contain multiple rows per session over time.
            # Keep only the newest row per session so the UI reflects latest task state.
            query = query.order_by(SessionState.updated_at.desc(), Session.created_at.desc())

            results = []
            seen_sessions = set()
            for row in query.all():
                session_id = row[0]
                if session_id in seen_sessions:
                    continue

                seen_sessions.add(session_id)
                results.append({
                    "session_id": session_id,
                    "name": row[1],
                    "created_at": row[2].isoformat() if row[2] else None,
                    "last_active_at": row[3].isoformat() if row[3] else None,
                    "mode": row[4],
                    "status": row[5],
                    "current_phase": row[6],
                    "updated_at": row[7].isoformat() if row[7] else None,
                })

                if len(results) >= limit:
                    break

            return results

        except Exception as e:
            logger.error("Failed to list sessions: %s", e)
            return []
        finally:
            db.close()

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session summary information.

        Args:
            session_id: Session identifier

        Returns:
            Session info dictionary or None
        """
        from cmbagent.database.models import Session, SessionState

        db = self.db_factory()
        try:
            session = db.query(Session).filter(Session.id == session_id).first()
            if not session:
                return None

            state = db.query(SessionState).filter(
                SessionState.session_id == session_id
            ).first()

            return {
                "session_id": session.id,
                "name": session.name,
                "user_id": session.user_id,
                "mode": state.mode if state else None,
                "status": state.status if state else None,
                "current_phase": state.current_phase if state else None,
                "current_step": state.current_step if state else None,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": state.updated_at.isoformat() if state and state.updated_at else None,
                "config": session.meta,
            }

        finally:
            db.close()

    # ==================== Cleanup ====================

    async def _cleanup_loop(self):
        """Background task to cleanup expired sessions"""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Session cleanup error: %s", e)

    def _cleanup_expired(self):
        """Cleanup expired sessions and approvals"""
        from cmbagent.database.models import SessionState, ApprovalRequest, ActiveConnection

        db = self.db_factory()
        try:
            now = datetime.now(timezone.utc)

            # Expire old active sessions (no activity for 24 hours)
            expired_sessions = db.query(SessionState).filter(
                SessionState.status == "active",
                SessionState.updated_at < now - timedelta(seconds=self._session_ttl)
            ).update({
                "status": "expired",
                "updated_at": now
            })

            # Expire pending approvals past their deadline
            expired_approvals = db.query(ApprovalRequest).filter(
                ApprovalRequest.status == "pending",
                ApprovalRequest.expires_at < now
            ).update({
                "status": "expired"
            })

            # Cleanup stale connections (no heartbeat for 5 minutes)
            stale_connections = db.query(ActiveConnection).filter(
                ActiveConnection.last_heartbeat < now - timedelta(minutes=5)
            ).delete()

            db.commit()

            if expired_sessions or expired_approvals or stale_connections:
                logger.info(
                    "Cleanup: %d sessions expired, %d approvals expired, %d connections removed",
                    expired_sessions, expired_approvals, stale_connections
                )

        except Exception as e:
            db.rollback()
            logger.error("Cleanup failed: %s", e)
        finally:
            db.close()


# Factory function for dependency injection
def create_session_manager() -> SessionManager:
    """Create a SessionManager instance with database factory"""
    from cmbagent.database import get_db_session
    return SessionManager(db_factory=get_db_session)


# Global instance (lazy initialization)
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get global SessionManager instance"""
    global _session_manager
    if _session_manager is None:
        _session_manager = create_session_manager()
    return _session_manager
