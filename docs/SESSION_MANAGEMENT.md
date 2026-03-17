# Session Management Architecture Documentation

## Table of Contents
1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [Session Lifecycle](#session-lifecycle)
4. [Backend Architecture](#backend-architecture)
5. [Frontend Architecture](#frontend-architecture)
6. [Session Flow Diagrams](#session-flow-diagrams)
7. [API Reference](#api-reference)
8. [Database Schema](#database-schema)
9. [Configuration](#configuration)

---

## Overview

The session management system provides stateful, resumable workflow execution across multiple modes. It supports:

- **Pause/Resume**: Sessions can be suspended and resumed later
- **Multi-tab Support**: Multiple browser tabs can view different sessions
- **Real-time Updates**: WebSocket-based event streaming
- **Human-in-the-Loop**: Approval requests within sessions
- **Cost Tracking**: Per-session resource usage
- **Optimistic Locking**: Concurrent modification detection
- **Auto-cleanup**: Background expiration of stale sessions

---

## Project Structure

### Backend (Python/FastAPI)

```
backend/
├── routers/
│   ├── sessions.py           # Session REST API endpoints
│   ├── tasks.py              # Task submission endpoints
│   ├── runs.py               # Workflow run endpoints
│   └── copilot.py            # Copilot mode endpoints
├── services/
│   ├── session_manager.py    # Session lifecycle management
│   ├── connection_manager.py # WebSocket connection management
│   ├── workflow_service.py   # Workflow execution service
│   └── execution_service.py  # Task execution service
├── websocket/
│   ├── handlers.py           # WebSocket endpoint handlers
│   ├── events.py             # Event definitions
│   └── callbacks/            # Event callbacks
├── core/
│   ├── app.py               # FastAPI app factory
│   ├── config.py            # Configuration
│   └── logging.py           # Logging setup
└── main.py                  # Application entry point
```

### Frontend (Next.js/React/TypeScript)

```
mars-ui/
├── contexts/
│   ├── WebSocketContext.tsx       # WebSocket and session state
│   └── ParallelSessionsContext.tsx # Multi-tab session management
├── components/
│   ├── SessionManager/            # Session detail views
│   │   ├── SessionDetailPanel.tsx
│   │   ├── SessionList.tsx
│   │   └── Session*.tsx (tabs)
│   └── sessions/                  # Session screen components
│       ├── SessionScreen.tsx
│       └── SessionCard.tsx
├── hooks/
│   └── useSessionDetail.ts        # Session detail loading hook
├── types/
│   ├── sessions.ts                # Session TypeScript types
│   └── websocket-events.ts        # WebSocket event types
├── lib/
│   ├── config.ts                  # API configuration
│   └── modes.ts                   # Workflow mode definitions
└── app/
    ├── sessions/                  # Sessions page
    ├── page.tsx                   # Main workflow page
    └── layout.tsx                 # Root layout
```

### Database Layer

```
cmbagent/database/
├── models.py                      # SQLAlchemy models
├── base.py                        # Database connection
├── repository.py                  # Data access layer
└── session_manager.py             # Session persistence logic
```

---

## Session Lifecycle

### States

```
┌─────────────┐
│   Created   │
└──────┬──────┘
       │
       v
┌─────────────┐     ┌──────────────┐
│   Active    │────>│  Suspended   │
└──────┬──────┘     └──────┬───────┘
       │                   │
       │<──────────────────┘
       │                (Resume)
       v
┌─────────────┐
│  Completed  │
└──────┬──────┘
       │
       v
┌─────────────┐
│   Expired   │
└─────────────┘
```

### Session Status Values

| Status | Description |
|--------|-------------|
| `active` | Session is currently running or ready to accept commands |
| `suspended` | Session is paused, can be resumed |
| `completed` | Session finished successfully |
| `expired` | Session exceeded TTL (24 hours for active, configurable for suspended) |
| `failed` | Session encountered an error and terminated |

---

## Backend Architecture

### 1. Session Manager Service

**File:** `backend/services/session_manager.py`

The `SessionManager` class (lines 24-569) is the core service for session lifecycle management.

#### Key Methods

##### Create Session
```python
create_session(mode: str, config: dict, user_id: Optional[str] = None) -> str
```
- **Location:** `session_manager.py:64-120`
- **Purpose:** Creates new session with mode configuration
- **Returns:** Session ID (UUID)
- **Database:** Creates `Session` and `SessionState` records

##### Save Session State
```python
save_session_state(session_id: str, state: SessionState) -> None
```
- **Location:** `session_manager.py:122-188`
- **Purpose:** Persists session state with optimistic locking
- **Features:**
  - Version-based concurrency control
  - Retry on version conflict (1 retry)
  - Updates `last_active_at` timestamp
  - Handles stale state errors

##### Load Session State
```python
load_session_state(session_id: str) -> Optional[SessionState]
```
- **Location:** `session_manager.py:190-244`
- **Purpose:** Loads session state for resumption
- **Returns:** `SessionState` object or None if not found

##### Suspend Session
```python
suspend_session(session_id: str) -> None
```
- **Location:** `session_manager.py:246-282`
- **Purpose:** Pauses active session
- **Database:** Updates status to `suspended`

##### Resume Session
```python
resume_session(session_id: str) -> SessionState
```
- **Location:** `session_manager.py:284-320`
- **Purpose:** Reactivates suspended session
- **Validation:** Checks session exists and is suspended
- **Returns:** Loaded session state

##### Complete Session
```python
complete_session(session_id: str) -> None
```
- **Location:** `session_manager.py:322-355`
- **Purpose:** Marks session as completed
- **Database:** Updates status and completion timestamp

##### Delete Session
```python
delete_session(session_id: str) -> None
```
- **Location:** `session_manager.py:357-386`
- **Purpose:** Soft-deletes session and associated data
- **Cascade:** Marks related workflow runs as deleted

##### List Sessions
```python
list_sessions(user_id: Optional[str] = None,
              status: Optional[str] = None,
              limit: int = 100,
              offset: int = 0) -> List[SessionInfo]
```
- **Location:** `session_manager.py:390-454`
- **Purpose:** Lists sessions with filters
- **Filters:** By user, status, with pagination

##### Get Session Info
```python
get_session_info(session_id: str) -> Optional[SessionInfo]
```
- **Location:** `session_manager.py:456-492`
- **Purpose:** Gets detailed session information
- **Includes:** Conversation history, context, config

#### Background Cleanup

```python
_cleanup_expired() -> None
```
- **Location:** `session_manager.py:507-549`
- **Schedule:** Runs every 60 seconds
- **Actions:**
  - Expires active sessions older than 24 hours
  - Expires pending approvals past deadline
  - Cleans stale WebSocket connections (5 min timeout)

---

### 2. Connection Manager Service

**File:** `backend/services/connection_manager.py`

The `ConnectionManager` class (lines 80-540) handles WebSocket connections and event delivery.

#### Key Methods

##### Connect
```python
async connect(task_id: str, websocket: WebSocket,
              session_id: Optional[str] = None) -> None
```
- **Location:** `connection_manager.py:107-164`
- **Purpose:** Registers WebSocket connection
- **Limits:** Max 100 concurrent connections
- **Database:** Creates `ActiveConnection` record

##### Disconnect
```python
async disconnect(task_id: str) -> None
```
- **Location:** `connection_manager.py:166-189`
- **Purpose:** Unregisters connection
- **Cleanup:** Removes from active connections table

##### Send Event
```python
async send_event(task_id: str, event: Dict) -> bool
```
- **Location:** `connection_manager.py:195-274`
- **Purpose:** Sends event or queues for delivery
- **Features:**
  - Queues events if connection lost
  - Retries on failure
  - Persists to `ExecutionEvent` table

##### Replay Missed Events
```python
async replay_missed_events(task_id: str,
                          last_seen_event_id: Optional[int]) -> None
```
- **Location:** `connection_manager.py:461-472`
- **Purpose:** Replays events after reconnection
- **Query:** Fetches events from database since last seen

---

### 3. WebSocket Handler

**File:** `backend/websocket/handlers.py`

#### WebSocket Endpoint Flow

```python
async def websocket_endpoint(websocket: WebSocket, task_id: str)
```
- **Location:** `handlers.py:51-227`

**Flow:**

1. **Accept WebSocket** (line 59)
   ```python
   await websocket.accept()
   ```

2. **Register Connection** (line 64)
   ```python
   await connection_manager.connect(task_id, websocket)
   ```

3. **Receive Initial Data** (lines 70-77)
   ```python
   initial_data = await websocket.receive_json()
   task = initial_data.get("task")
   config = initial_data.get("config", {})
   ```

4. **Create or Reuse Session** (lines 86-98)
   ```python
   session_id = config.get("copilotSessionId") or config.get("session_id")
   if not session_id:
       session_id = _session_manager.create_session(mode, config)
   else:
       # Reuse existing session
   ```

5. **Inject Session ID** (line 101)
   ```python
   config["copilotSessionId"] = session_id
   ```

6. **Create Workflow Run** (lines 125-133)
   ```python
   run = WorkflowRun(
       task_id=task_id,
       session_id=session_id,
       mode=mode,
       agent=config.get("agent", "unknown"),
       model=config.get("model", "unknown"),
       status="running",
       started_at=datetime.utcnow()
   )
   db.add(run)
   db.commit()
   ```

7. **Send Initial Status** (lines 137-142)
   ```python
   await websocket.send_json({
       "type": "status",
       "status": "connected",
       "sessionId": session_id,
       "taskId": task_id
   })
   ```

8. **Execute Task** (line 146)
   ```python
   asyncio.create_task(
       _execute_workflow(task_id, task, config, mode, session_id)
   )
   ```

9. **Handle Client Messages** (lines 154-199)
   - Human feedback
   - Approval responses
   - Control commands (pause, cancel)

10. **Cleanup on Disconnect** (lines 222-226)
    ```python
    finally:
        await connection_manager.disconnect(task_id)
    ```

---

### 4. Session REST API

**File:** `backend/routers/sessions.py`

All endpoints are prefixed with `/api/sessions`.

#### Endpoints

##### List Workflow Modes
```
GET /api/sessions/modes/list
```
- **Location:** `sessions.py:72-129`
- **Returns:** List of available modes with metadata
- **Response:**
  ```json
  [
    {
      "id": "copilot",
      "name": "Copilot Mode",
      "description": "Interactive multi-agent assistant",
      "supportsResume": true,
      "supportsHITL": true,
      "icon": "🤖"
    }
  ]
  ```

##### Create Session
```
POST /api/sessions/
Body: { "mode": "copilot", "config": {...}, "name": "My Session" }
```
- **Location:** `sessions.py:132-170`
- **Purpose:** Explicitly create a new session
- **Returns:** Session ID and metadata

##### List Sessions
```
GET /api/sessions/?user_id=...&status=active&limit=100&offset=0
```
- **Location:** `sessions.py:173-205`
- **Purpose:** List sessions with filters
- **Query Params:**
  - `user_id` (optional)
  - `status` (optional): active, suspended, completed
  - `limit` (default: 100)
  - `offset` (default: 0)

##### Get Session Detail
```
GET /api/sessions/{session_id}
```
- **Location:** `sessions.py:208-245`
- **Purpose:** Get detailed session information
- **Response:**
  ```json
  {
    "session_id": "uuid",
    "name": "Session name",
    "mode": "copilot",
    "status": "active",
    "current_phase": "execution",
    "current_step": 3,
    "created_at": "2026-02-18T...",
    "updated_at": "2026-02-18T...",
    "conversation_history": [...],
    "context_variables": {...},
    "plan_data": {...},
    "config": {...}
  }
  ```

##### Get Conversation History
```
GET /api/sessions/{session_id}/history
```
- **Location:** `sessions.py:248-282`
- **Purpose:** Get conversation messages
- **Response:** Array of conversation messages

##### Suspend Session
```
POST /api/sessions/{session_id}/suspend
```
- **Location:** `sessions.py:285-315`
- **Purpose:** Pause active session
- **Effect:** Changes status to `suspended`

##### Resume Session
```
POST /api/sessions/{session_id}/resume
Body: { "additional_context": "Continue from where we left off" }
```
- **Location:** `sessions.py:318-355`
- **Purpose:** Reactivate suspended session
- **Effect:** Changes status to `active`
- **Note:** Client must establish new WebSocket connection

##### Delete Session
```
DELETE /api/sessions/{session_id}
```
- **Location:** `sessions.py:358-388`
- **Purpose:** Soft-delete session
- **Effect:** Marks session as deleted, cascades to runs

##### Get Session Runs
```
GET /api/sessions/{session_id}/runs?limit=50&offset=0
```
- **Location:** `sessions.py:391-435`
- **Purpose:** Get workflow runs for session
- **Response:** Array of workflow run objects

---

## Frontend Architecture

### 1. WebSocket Context

**File:** `mars-ui/contexts/WebSocketContext.tsx`

The main React context for managing WebSocket connections and session state.

#### Context State

```typescript
interface WebSocketContextValue {
  // Connection
  connected: boolean;
  currentRunId: string | null;
  copilotSessionId: string | null;

  // Workflow state
  workflowStatus: string | null;
  dagData: { nodes: any[], edges: any[] };
  consoleOutput: string[];
  costSummary: CostSummary | null;

  // Messages
  agentMessages: AgentMessage[];
  approvalRequests: ApprovalRequest[];

  // Actions
  connect: (taskId: string, task: string, config: any) => Promise<void>;
  disconnect: () => void;
  sendMessage: (message: string) => void;
  submitApproval: (requestId: string, approved: boolean, feedback?: string) => void;
  resumeSession: (sessionId: string, additionalContext?: string) => Promise<void>;
  loadSessionHistory: (sessionId: string) => Promise<void>;
}
```

#### Key Functions

##### Connect to WebSocket
```typescript
const connect = useCallback(async (
  taskId: string,
  task: string,
  config: any
) => {
  // 1. Create WebSocket connection
  const ws = new WebSocket(getWsUrl(`/ws/${taskId}`));

  // 2. Setup event handlers
  ws.onopen = () => {
    ws.send(JSON.stringify({ task, config }));
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Handle various event types
    if (data.type === 'status') {
      setCopilotSessionId(data.sessionId);
    }
    // ... other handlers
  };

  // 3. Store connection
  wsRef.current = ws;
}, []);
```

##### Resume Session
```typescript
const resumeSession = useCallback(async (
  sessionId: string,
  additionalContext?: string
) => {
  // 1. Load session info
  const response = await fetch(
    getApiUrl(`/api/sessions/${sessionId}`)
  );
  const session = await response.json();

  // 2. Resume via API
  await fetch(
    getApiUrl(`/api/sessions/${sessionId}/resume`),
    { method: "POST" }
  );

  // 3. Connect with session context
  const taskId = `task-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  await connect(taskId, additionalContext || "Continue session.", {
    ...session.config,
    copilotSessionId: sessionId,
    mode: session.mode,
  });

  setCopilotSessionId(sessionId);
}, [connect]);
```

##### Load Session History
```typescript
const loadSessionHistory = useCallback(async (sessionId: string) => {
  const response = await fetch(
    getApiUrl(`/api/sessions/${sessionId}/history`)
  );
  const history = await response.json();

  // Populate context with historical messages
  setAgentMessages(history);
}, []);
```

---

### 2. Parallel Sessions Context

**File:** `mars-ui/contexts/ParallelSessionsContext.tsx`

Manages multiple session tabs in the UI.

#### Context State

```typescript
interface SessionTab {
  id: string;          // tab-{timestamp}-{random}
  label: string;       // "New Workflow" or session name
  active: boolean;     // is this tab active?
  sessionId?: string;  // linked session ID
  isLive?: boolean;    // is WebSocket connected?
}

interface ParallelSessionsContextValue {
  tabs: SessionTab[];
  activeTabId: string | null;

  addTab: (label: string, sessionId?: string) => string;
  removeTab: (tabId: string) => void;
  switchTab: (tabId: string) => void;
  updateTabSession: (tabId: string, sessionId: string) => void;
}
```

#### Background Polling

**Location:** Lines 114-194

- Polls `/api/sessions?limit=50` every 5 seconds
- Updates non-live tabs with backend session status
- Syncs session names and states across tabs

---

### 3. Session List UI

**File:** `mars-ui/components/sessions/SessionScreen.tsx`

The main sessions management page.

#### Features

1. **Fetch Sessions**
   ```typescript
   const fetchSessions = async () => {
     const response = await fetch(
       getApiUrl('/api/sessions?limit=100')
     );
     const data = await response.json();
     setSessions(data);
   };
   ```

2. **Group by Status** (lines 22-28)
   ```typescript
   const groupedSessions = {
     active: sessions.filter(s => s.status === 'active'),
     paused: sessions.filter(s => s.status === 'suspended'),
     completed: sessions.filter(s => s.status === 'completed'),
     failed: sessions.filter(s => s.status === 'failed')
   };
   ```

3. **Search Filter** (lines 80-88)
   ```typescript
   const filteredSessions = sessions.filter(session =>
     session.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
     session.mode.toLowerCase().includes(searchQuery.toLowerCase())
   );
   ```

4. **Auto-refresh** (line 54)
   - Polls every 30 seconds for updates

5. **Actions**
   - **Resume:** Navigates to main page with query params `?resumeSessionId={id}`
   - **Pause:** `POST /api/sessions/{id}/suspend`
   - **Delete:** `DELETE /api/sessions/{id}`

---

### 4. Session Detail Panel

**File:** `mars-ui/components/SessionManager/SessionDetailPanel.tsx`

Shows detailed session information with tabbed interface.

#### Tabs

1. **Overview** - Session metadata and status
2. **DAG** - Workflow graph visualization
3. **Console** - Execution logs
4. **Events** - Execution events timeline
5. **Costs** - Cost breakdown by model/agent
6. **Files** - Generated/modified files
7. **Config** - Session configuration JSON

#### Data Loading

```typescript
const useSessionDetail = (sessionId: string) => {
  const [session, setSession] = useState<SessionDetail | null>(null);

  useEffect(() => {
    const fetchSession = async () => {
      const response = await fetch(
        getApiUrl(`/api/sessions/${sessionId}`)
      );
      const data = await response.json();
      setSession(data);
    };

    fetchSession();
    const interval = setInterval(fetchSession, 5000); // Poll every 5s

    return () => clearInterval(interval);
  }, [sessionId]);

  return session;
};
```

---

## Session Flow Diagrams

### 1. Session Creation Flow

```
User Action (UI)
    │
    ├──> Submit Task Form
    │    - Task description
    │    - Mode selection
    │    - Config options
    │
    v
┌─────────────────────────┐
│  POST /api/tasks/submit │
│  (Optional: Create      │
│   session explicitly)   │
└────────┬────────────────┘
         │
         v
┌─────────────────────────┐
│  Connect to WebSocket   │
│  /ws/{task_id}          │
└────────┬────────────────┘
         │
         v
┌─────────────────────────┐
│  Send Initial Data      │
│  { task, config }       │
└────────┬────────────────┘
         │
         v
┌─────────────────────────┐
│  Backend:               │
│  1. Register connection │
│  2. Create/reuse session│
│  3. Create workflow run │
│  4. Start execution     │
└────────┬────────────────┘
         │
         v
┌─────────────────────────┐
│  Receive session_id     │
│  { type: "status",      │
│    sessionId: "..." }   │
└────────┬────────────────┘
         │
         v
┌─────────────────────────┐
│  Store in context       │
│  copilotSessionId = id  │
└─────────────────────────┘
```

### 2. Session Resume Flow

```
User Action (UI)
    │
    ├──> Click "Resume" on session card
    │
    v
┌──────────────────────────┐
│ GET /api/sessions/{id}   │
│ (Load session config)    │
└────────┬─────────────────┘
         │
         v
┌──────────────────────────┐
│ POST /api/sessions/{id}/ │
│      resume              │
└────────┬─────────────────┘
         │
         v
┌──────────────────────────┐
│ Backend:                 │
│ - Load SessionState      │
│ - Change status to active│
└────────┬─────────────────┘
         │
         v
┌──────────────────────────┐
│ UI: Create new WebSocket │
│ connection with:         │
│ - copilotSessionId: id   │
│ - task: "Continue..."    │
└────────┬─────────────────┘
         │
         v
┌──────────────────────────┐
│ Backend:                 │
│ - Reuse existing session │
│ - Load conversation hist │
│ - Resume execution       │
└────────┬─────────────────┘
         │
         v
┌──────────────────────────┐
│ UI: Load history and     │
│ display in chat          │
└──────────────────────────┘
```

### 3. Session State Persistence Flow

```
Workflow Execution
    │
    ├──> Agent completes step
    │
    v
┌──────────────────────────┐
│ SessionManager.          │
│ save_session_state()     │
└────────┬─────────────────┘
         │
         v
┌──────────────────────────┐
│ 1. Load current state    │
│ 2. Increment version     │
│ 3. Update fields:        │
│    - conversation_history│
│    - context_variables   │
│    - current_phase/step  │
│    - updated_at          │
└────────┬─────────────────┘
         │
         v
┌──────────────────────────┐
│ Database Commit          │
│ (Optimistic lock)        │
└────────┬─────────────────┘
         │
         ├──> Success: Continue
         │
         └──> Version conflict:
              Retry once, then fail
```

### 4. Multi-tab Session Management

```
Tab 1 (Live)                  Tab 2 (Background)
    │                              │
    ├──> WebSocket connected       ├──> No WebSocket
    │    Real-time updates         │
    │                              │
    v                              v
┌────────────────┐          ┌────────────────┐
│ Store session  │          │ Store session  │
│ ID in tab      │          │ ID in tab      │
└───────┬────────┘          └──────┬─────────┘
        │                           │
        │                           v
        │                  ┌────────────────┐
        │                  │ Poll API every │
        │                  │ 5 seconds      │
        │                  └──────┬─────────┘
        │                         │
        │                         v
        │                  ┌────────────────┐
        │                  │ GET /api/      │
        │                  │ sessions?limit │
        │                  │ =50            │
        │                  └──────┬─────────┘
        │                         │
        │                         v
        │                  ┌────────────────┐
        │                  │ Update tab     │
        │                  │ status/name    │
        │                  └────────────────┘
        │
        v
┌────────────────┐
│ User switches  │
│ to Tab 2       │
└───────┬────────┘
        │
        v
┌────────────────┐
│ Option to      │
│ reconnect WS   │
│ for live view  │
└────────────────┘
```

### 5. Session Cleanup Flow

```
Background Task (Every 60s)
    │
    v
┌──────────────────────────┐
│ SessionManager.          │
│ _cleanup_expired()       │
└────────┬─────────────────┘
         │
         ├──> Check active sessions
         │    - Find sessions with
         │      last_active_at > 24h
         │    - Set status = 'expired'
         │
         ├──> Check pending approvals
         │    - Find approvals past
         │      deadline
         │    - Auto-reject expired
         │
         └──> Check stale connections
              - Find connections with
                last_heartbeat > 5min
              - Remove from active
                connections table
```

---

## API Reference

### Session Endpoints

#### GET /api/sessions/modes/list

**Description:** List available workflow modes

**Response:**
```json
[
  {
    "id": "copilot",
    "name": "Copilot Mode",
    "description": "Interactive multi-agent assistant",
    "supportsResume": true,
    "supportsHITL": true,
    "icon": "🤖"
  }
]
```

---

#### POST /api/sessions/

**Description:** Create new session

**Request Body:**
```json
{
  "mode": "copilot",
  "config": {
    "model": "claude-3-sonnet",
    "temperature": 0.7
  },
  "name": "My Session"
}
```

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "active",
  "created_at": "2026-02-18T12:00:00Z"
}
```

---

#### GET /api/sessions/

**Description:** List sessions with filters

**Query Parameters:**
- `user_id` (optional): Filter by user
- `status` (optional): Filter by status (active, suspended, completed)
- `limit` (default: 100): Max results
- `offset` (default: 0): Pagination offset

**Response:**
```json
[
  {
    "session_id": "uuid",
    "name": "Session name",
    "mode": "copilot",
    "status": "active",
    "created_at": "2026-02-18T12:00:00Z",
    "last_active_at": "2026-02-18T12:30:00Z"
  }
]
```

---

#### GET /api/sessions/{session_id}

**Description:** Get detailed session information

**Response:**
```json
{
  "session_id": "uuid",
  "name": "Session name",
  "mode": "copilot",
  "status": "active",
  "current_phase": "execution",
  "current_step": 3,
  "created_at": "2026-02-18T12:00:00Z",
  "updated_at": "2026-02-18T12:30:00Z",
  "conversation_history": [
    {
      "role": "user",
      "content": "Hello",
      "timestamp": "2026-02-18T12:00:00Z"
    },
    {
      "role": "assistant",
      "content": "Hi! How can I help?",
      "timestamp": "2026-02-18T12:00:01Z"
    }
  ],
  "context_variables": {
    "last_file_edited": "main.py",
    "total_tokens": 1500
  },
  "plan_data": {
    "steps": ["Step 1", "Step 2"],
    "current_step": 1
  },
  "config": {
    "model": "claude-3-sonnet",
    "temperature": 0.7
  }
}
```

---

#### GET /api/sessions/{session_id}/history

**Description:** Get conversation history

**Response:**
```json
[
  {
    "role": "user",
    "content": "Hello",
    "timestamp": "2026-02-18T12:00:00Z"
  },
  {
    "role": "assistant",
    "content": "Hi! How can I help?",
    "timestamp": "2026-02-18T12:00:01Z"
  }
]
```

---

#### POST /api/sessions/{session_id}/suspend

**Description:** Pause active session

**Response:**
```json
{
  "status": "suspended",
  "message": "Session suspended successfully"
}
```

---

#### POST /api/sessions/{session_id}/resume

**Description:** Resume suspended session

**Request Body (optional):**
```json
{
  "additional_context": "Continue from where we left off"
}
```

**Response:**
```json
{
  "status": "active",
  "message": "Session resumed successfully"
}
```

---

#### DELETE /api/sessions/{session_id}

**Description:** Delete session

**Response:**
```json
{
  "message": "Session deleted successfully"
}
```

---

#### GET /api/sessions/{session_id}/runs

**Description:** Get workflow runs for session

**Query Parameters:**
- `limit` (default: 50): Max results
- `offset` (default: 0): Pagination offset

**Response:**
```json
[
  {
    "id": "run-uuid",
    "mode": "copilot",
    "agent": "planner",
    "model": "claude-3-sonnet",
    "status": "completed",
    "task_description": "Create a new feature",
    "started_at": "2026-02-18T12:00:00Z",
    "completed_at": "2026-02-18T12:15:00Z",
    "is_branch": false,
    "meta": {
      "cost": 0.05,
      "tokens": 1500
    }
  }
]
```

---

### WebSocket Protocol

#### Connection

```
ws://localhost:8000/ws/{task_id}
```

#### Initial Message (Client → Server)

```json
{
  "task": "Create a login page",
  "config": {
    "mode": "copilot",
    "model": "claude-3-sonnet",
    "copilotSessionId": "uuid-if-resuming"
  }
}
```

#### Status Event (Server → Client)

```json
{
  "type": "status",
  "status": "connected",
  "sessionId": "uuid",
  "taskId": "task-uuid"
}
```

#### Other Event Types

- `dag_update` - DAG node/edge updates
- `console` - Console output
- `agent_message` - Agent chat messages
- `cost_update` - Cost tracking updates
- `approval_request` - HITL approval needed
- `workflow_complete` - Workflow finished
- `error` - Error occurred

---

## Database Schema

### Session Table

**File:** `cmbagent/database/models.py:24-50`

```sql
CREATE TABLE sessions (
  id TEXT PRIMARY KEY,              -- UUID
  user_id TEXT,                     -- User identifier
  name TEXT,                        -- Display name
  created_at TIMESTAMP,             -- Creation time
  last_active_at TIMESTAMP,         -- Last activity time
  status TEXT,                      -- active, archived, deleted
  meta JSON,                        -- Additional metadata
  resource_limits JSON              -- Resource constraints
);
```

**Relationships:**
- One-to-many with `session_states`
- One-to-many with `workflow_runs`
- One-to-many with `projects`
- One-to-many with `cost_records`

---

### SessionState Table

**File:** `cmbagent/database/models.py:53-117`

```sql
CREATE TABLE session_states (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,                  -- Foreign key to sessions
  mode TEXT,                        -- Workflow mode
  conversation_history JSON,        -- Chat messages
  context_variables JSON,           -- Runtime context
  plan_data JSON,                   -- Planning data
  current_phase TEXT,               -- Current execution phase
  current_step INTEGER,             -- Current step number
  status TEXT,                      -- active, suspended, completed, expired
  created_at TIMESTAMP,             -- Creation time
  updated_at TIMESTAMP,             -- Last update time
  expires_at TIMESTAMP,             -- Expiration time
  version INTEGER,                  -- Optimistic lock version

  FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

**Indexes:**
- `session_id` for fast lookups
- `status` for filtering

---

### WorkflowRun Table

**File:** `cmbagent/database/models.py:120-177`

```sql
CREATE TABLE workflow_runs (
  id TEXT PRIMARY KEY,              -- UUID
  task_id TEXT,                     -- WebSocket task ID
  session_id TEXT,                  -- Foreign key to sessions
  mode TEXT,                        -- Workflow mode
  agent TEXT,                       -- Agent name
  model TEXT,                       -- LLM model
  status TEXT,                      -- running, completed, failed
  task_description TEXT,            -- User task
  started_at TIMESTAMP,             -- Start time
  completed_at TIMESTAMP,           -- End time
  is_branch BOOLEAN,                -- Is branched execution
  meta JSON,                        -- Additional metadata

  FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

---

### ActiveConnection Table

**File:** `cmbagent/database/models.py:479-509`

```sql
CREATE TABLE active_connections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT UNIQUE,              -- WebSocket task ID
  session_id TEXT,                  -- Foreign key to sessions
  server_instance TEXT,             -- Server hostname/ID
  connected_at TIMESTAMP,           -- Connection time
  last_heartbeat TIMESTAMP,         -- Last heartbeat

  FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

**Purpose:** Tracks active WebSocket connections for multi-instance deployments

---

### CostRecord Table

**File:** `cmbagent/database/models.py:377-402`

```sql
CREATE TABLE cost_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,                  -- Foreign key to sessions
  run_id TEXT,                      -- Foreign key to workflow_runs
  agent TEXT,                       -- Agent name
  model TEXT,                       -- LLM model
  input_tokens INTEGER,             -- Tokens sent
  output_tokens INTEGER,            -- Tokens received
  cost REAL,                        -- USD cost
  timestamp TIMESTAMP,              -- Record time
  meta JSON,                        -- Additional metadata

  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (run_id) REFERENCES workflow_runs(id)
);
```

---

### ApprovalRequest Table

**File:** `cmbagent/database/models.py:405-444`

```sql
CREATE TABLE approval_requests (
  id TEXT PRIMARY KEY,              -- UUID
  session_id TEXT,                  -- Foreign key to sessions
  run_id TEXT,                      -- Foreign key to workflow_runs
  request_type TEXT,                -- Type of approval
  request_data JSON,                -- Request details
  status TEXT,                      -- pending, approved, rejected, expired
  created_at TIMESTAMP,             -- Creation time
  responded_at TIMESTAMP,           -- Response time
  response_data JSON,               -- Response details
  deadline TIMESTAMP,               -- Auto-expire time

  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (run_id) REFERENCES workflow_runs(id)
);
```

---

## Configuration

### Backend Configuration

**File:** `backend/core/config.py`

Environment variables:
- `DATABASE_URL` - SQLAlchemy database URL (default: SQLite)
- `API_HOST` - FastAPI host (default: 0.0.0.0)
- `API_PORT` - FastAPI port (default: 8000)
- `LOG_LEVEL` - Logging level (default: INFO)
- `MAX_CONCURRENT_CONNECTIONS` - Max WebSocket connections (default: 100)
- `SESSION_TTL_HOURS` - Active session TTL (default: 24)
- `CLEANUP_INTERVAL_SECONDS` - Cleanup task interval (default: 60)

---

### Frontend Configuration

**File:** `mars-ui/lib/config.ts`

Environment variables:
- `NEXT_PUBLIC_API_URL` - Backend API URL (default: http://localhost:8000)
- `NEXT_PUBLIC_WS_URL` - WebSocket URL (default: ws://localhost:8000)

Helpers:
```typescript
export const getApiUrl = (path: string) => `${API_BASE_URL}${path}`
export const getWsUrl = (path: string) => `${WS_BASE_URL}${path}`
```

---

### Database Configuration

**File:** `cmbagent/database/base.py`

SQLAlchemy setup:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cmbagent_workdir/database/cmbagent.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_session():
    """Dependency for FastAPI endpoints"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## Workflow Modes

| Mode | Resume | HITL | Description |
|------|--------|------|-------------|
| `copilot` | ✅ | ✅ | Interactive multi-agent assistant with planning |
| `planning-control` | ✅ | ✅ | Two-phase: planning then execution with approval |
| `one-shot` | ❌ | ❌ | Single agent, immediate execution, no planning |
| `hitl-interactive` | ✅ | ✅ | Full human-in-the-loop with iterative guidance |
| `idea-generation` | ✅ | ✅ | Research idea generation pipeline |
| `ocr` | ❌ | ❌ | PDF text extraction (utility mode) |
| `arxiv` | ❌ | ❌ | Extract/download arXiv papers (utility mode) |
| `enhance-input` | ❌ | ❌ | Enhance text with arXiv references (utility mode) |

**Mode Metadata Location:** `backend/routers/sessions.py:72-129`

---

## Key Design Patterns

### 1. Optimistic Locking

Session state uses version-based concurrency control:

```python
# backend/services/session_manager.py:150-188
for attempt in range(2):
    try:
        state.version += 1
        db.commit()
        break
    except IntegrityError:
        if attempt == 0:
            db.rollback()
            continue  # Retry once
        raise
```

**Benefits:**
- Prevents lost updates in concurrent scenarios
- Lightweight (no locks required)
- One retry on conflict

---

### 2. Event Replay

Connection manager supports missed event replay:

```python
# backend/services/connection_manager.py:461-472
async def replay_missed_events(task_id: str, last_seen_event_id: Optional[int]):
    events = db.query(ExecutionEvent).filter(
        ExecutionEvent.task_id == task_id,
        ExecutionEvent.id > last_seen_event_id
    ).order_by(ExecutionEvent.id).all()

    for event in events:
        await send_event(task_id, event.data)
```

**Benefits:**
- Handles reconnection gracefully
- No message loss
- Client can specify last seen event

---

### 3. Cascade Soft Delete

Session deletion cascades to related entities:

```python
# backend/services/session_manager.py:357-386
def delete_session(session_id: str):
    # Mark session as deleted
    session.status = "deleted"

    # Cascade to workflow runs
    db.query(WorkflowRun).filter(
        WorkflowRun.session_id == session_id
    ).update({"status": "deleted"})

    db.commit()
```

**Benefits:**
- Preserves data for auditing
- Can be restored if needed
- Maintains referential integrity

---

### 4. Background Cleanup

Periodic cleanup task runs asynchronously:

```python
# backend/services/session_manager.py:496-549
async def _cleanup_loop():
    while True:
        try:
            _cleanup_expired()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        await asyncio.sleep(60)
```

**Benefits:**
- Prevents resource leaks
- Automatic TTL enforcement
- Non-blocking (separate task)

---

## Common Workflows

### Starting a New Session

1. User fills form in UI (`app/page.tsx`)
2. UI calls `connect(taskId, task, config)` from WebSocket context
3. WebSocket connects to `/ws/{task_id}`
4. Backend creates session via `SessionManager.create_session()`
5. Backend sends `{ type: "status", sessionId: "..." }`
6. UI stores `copilotSessionId` in context
7. Execution begins, events stream to UI

---

### Pausing a Session

1. User clicks "Pause" button (`SessionScreen.tsx:66-77`)
2. UI calls `POST /api/sessions/{id}/suspend`
3. Backend updates status to `suspended`
4. WebSocket connection may close (but events are persisted)
5. UI shows "Paused" status

---

### Resuming a Session

1. User clicks "Resume" button (`SessionScreen.tsx:59`)
2. UI navigates to main page with `?resumeSessionId={id}`
3. Main page calls `resumeSession(sessionId)` from context
4. Context loads session info: `GET /api/sessions/{id}`
5. Context calls resume API: `POST /api/sessions/{id}/resume`
6. Backend changes status to `active`
7. Context creates new WebSocket with `copilotSessionId: id`
8. Backend reuses existing session, loads history
9. UI displays conversation history
10. Execution continues from last checkpoint

---

### Viewing Session History

1. User opens session detail panel (`SessionDetailPanel.tsx`)
2. Component loads session: `GET /api/sessions/{id}`
3. Component displays conversation history in tabs
4. Component polls for updates every 5 seconds

---

### Multi-tab Management

1. User opens multiple browser tabs
2. Each tab has separate `WebSocketContext` instance
3. One tab is "live" (WebSocket connected)
4. Other tabs run background polling (every 5 seconds)
5. `ParallelSessionsContext` syncs tab states
6. User can switch tabs, each maintains own session
7. Switching to a tab allows reconnecting WebSocket for live view

---

## Troubleshooting

### Session Not Resuming

**Symptoms:** Resume fails or session not found

**Checks:**
1. Verify session exists: `GET /api/sessions/{id}`
2. Check session status (must be `suspended` or `active`)
3. Check expiration: `expires_at` field
4. Review backend logs for errors

**Solutions:**
- If expired, session cannot be resumed (create new)
- If active, no need to resume (just reconnect)
- If not found, session may have been deleted

---

### WebSocket Connection Issues

**Symptoms:** Connection drops, events not received

**Checks:**
1. Check `connected` state in WebSocket context
2. Verify `task_id` is valid
3. Check backend `active_connections` table
4. Review network tab in browser DevTools

**Solutions:**
- Implement reconnection logic (check last event ID)
- Use event replay: `replay_missed_events()`
- Check firewall/proxy settings
- Ensure WebSocket protocol is supported

---

### State Version Conflicts

**Symptoms:** "Stale state error" in logs

**Cause:** Concurrent session state updates

**Solutions:**
- Built-in retry mechanism (1 attempt)
- If persistent, check for race conditions in code
- Consider serializing state updates

---

### Session Cleanup Not Working

**Symptoms:** Old sessions not expiring

**Checks:**
1. Verify cleanup task is running (logs)
2. Check `SESSION_TTL_HOURS` configuration
3. Review `last_active_at` timestamps

**Solutions:**
- Ensure cleanup loop starts: `SessionManager._start_cleanup_loop()`
- Check for exceptions in cleanup task
- Manually trigger: `SessionManager._cleanup_expired()`

---

## Performance Considerations

### Database Indexing

Ensure indexes exist on:
- `sessions.id` (primary key)
- `session_states.session_id` (foreign key)
- `workflow_runs.session_id` (foreign key)
- `active_connections.task_id` (unique)
- `cost_records.session_id` (foreign key)

### WebSocket Scaling

For multi-instance deployments:
- Use Redis for connection tracking (instead of `active_connections` table)
- Implement sticky sessions or connection affinity
- Share event queue across instances

### Polling Optimization

Frontend polling intervals:
- Background tabs: 5 seconds
- Session list: 30 seconds
- Session detail (when open): 5 seconds

Consider:
- Server-sent events (SSE) for non-WebSocket updates
- Implementing caching with ETags
- Using GraphQL subscriptions

---

## Security Considerations

### Authentication

Currently, authentication is minimal. Production deployments should:
- Add JWT-based authentication
- Validate `user_id` in session operations
- Implement API rate limiting
- Add CORS configuration

### Authorization

Sessions should be scoped to users:
- Verify session ownership before operations
- Implement role-based access control (RBAC)
- Audit all session access attempts

### Input Validation

All endpoints validate inputs:
- Session IDs are UUIDs
- Status values are enums
- Pagination limits are bounded
- JSON payloads are validated

---

## Future Enhancements

### Planned Features

1. **Session Sharing**
   - Allow multiple users to collaborate on sessions
   - Implement permissions (view, edit, admin)

2. **Session Templates**
   - Save session configurations as templates
   - Quick-start from templates

3. **Advanced Search**
   - Full-text search across conversation history
   - Filter by date range, mode, status

4. **Session Analytics**
   - Cost trends over time
   - Performance metrics
   - Usage patterns

5. **Export/Import**
   - Export sessions as JSON/Markdown
   - Import sessions from backups

---

## References

### Key Files

**Backend:**
- `backend/services/session_manager.py:24-569` - Core session logic
- `backend/routers/sessions.py` - REST API endpoints
- `backend/websocket/handlers.py:51-227` - WebSocket handler

**Frontend:**
- `mars-ui/contexts/WebSocketContext.tsx` - WebSocket state
- `mars-ui/contexts/ParallelSessionsContext.tsx` - Multi-tab management
- `mars-ui/components/sessions/SessionScreen.tsx` - Session list UI
- `mars-ui/components/SessionManager/SessionDetailPanel.tsx` - Detail view

**Database:**
- `cmbagent/database/models.py:24-117` - Session models

---

## Glossary

**Session** - A stateful context for workflow execution, persisting across reconnections

**SessionState** - The runtime state of a session (conversation, context, plan)

**WorkflowRun** - A single execution within a session (can have multiple runs per session)

**Copilot Mode** - Interactive multi-agent mode with planning and HITL support

**HITL** - Human-in-the-loop: workflow pauses for human approval/input

**Optimistic Locking** - Concurrency control using version numbers

**DAG** - Directed Acyclic Graph: visual representation of workflow steps

**TTL** - Time to live: automatic expiration time for sessions

**WebSocket** - Full-duplex communication channel for real-time updates

---

## Simplifying to Single-Session Approach

### Why Simplify?

The current multi-tab session management adds significant complexity:
- **ParallelSessionsContext** managing multiple tabs
- Background polling for non-live tabs (every 5 seconds)
- Tab switching logic and state synchronization
- Complex display logic (live vs snapshot data)
- Higher memory usage and API call overhead

**Trade-offs:**
- ✅ **Reduced complexity**: Remove entire tab management layer
- ✅ **Better performance**: No background polling, fewer API calls
- ✅ **Simpler UX**: Focus on one workflow at a time
- ❌ **Lost capability**: Cannot work on multiple workflows simultaneously

### What Changes?

#### 1. Remove Frontend Components

**Delete these files:**
- `mars-ui/contexts/ParallelSessionsContext.tsx` - Entire multi-tab context
- `mars-ui/components/layout/SessionTabBar.tsx` - Tab bar UI

**Simplify these files:**
- `mars-ui/app/page.tsx` - Remove tab switching logic, use WebSocket state directly
- `mars-ui/app/providers.tsx` - Remove `ParallelSessionsProvider`

#### 2. Simplified State Management

**Before (Multi-tab):**
```typescript
<WebSocketProvider>
  <ParallelSessionsProvider>
    {/* Multiple tabs, complex state */}
  </ParallelSessionsProvider>
</WebSocketProvider>
```

**After (Single-session):**
```typescript
<WebSocketProvider>
  {/* Direct WebSocket state, no tabs */}
</WebSocketProvider>
```

#### 3. Updated Main Page (`app/page.tsx`)

**Remove:**
- All tab management (addTab, removeTab, switchTab)
- Background polling for non-live tabs
- Tab snapshot data storage
- Display logic switching between live/snapshot

**Keep:**
- WebSocket connection management
- Session resume capability
- Real-time updates (console, DAG, costs)
- Session list/browser

**Simplified Display:**
```typescript
// Before (complex):
const displayConsole = isActiveTabLive
  ? consoleOutput
  : (activeTab?.consoleOutput || []);

// After (simple):
const displayConsole = consoleOutput; // Always from WebSocket
```

#### 4. Session Navigation Flow

**Single-session workflow:**
1. User starts new session → WebSocket connects
2. Session runs → Real-time updates
3. User pauses → Session suspended
4. User resumes → New WebSocket connection
5. User starts new session → **Previous session disconnects**

**Key difference:** Starting a new session automatically disconnects from current session. User must save/pause current work first.

#### 5. Backend Changes

**No backend changes needed!** The backend already supports:
- Single WebSocket connections per task
- Session persistence
- Resume capability
- Multiple sessions (stored, not concurrent)

The simplification is **frontend-only**.

#### 6. Updated UI Flow

**Main Screen Layout:**
```
┌─────────────────────────────────────────┐
│ TopBar (logo, theme, user)              │
├─────────────────────────────────────────┤
│ SideNav                   │ Main Area   │
│ - New Session             │             │
│ - Resume Session          │  Console    │
│ - View All Sessions       │  DAG        │
│ - Settings                │  Costs      │
│                           │  Files      │
└───────────────────────────┴─────────────┘
```

**No tab bar** - single session always visible.

#### 7. Session Switching

**Current (multi-tab):**
- Multiple sessions open in tabs
- Switch between tabs instantly
- Each tab maintains independent state

**Single-session:**
- One active session at a time
- To switch: Pause current → Resume different session
- Forces intentional context switching

#### 8. Migration Guide

**Step 1: Remove ParallelSessionsContext**
```bash
rm mars-ui/contexts/ParallelSessionsContext.tsx
```

**Step 2: Remove SessionTabBar**
```bash
rm mars-ui/components/layout/SessionTabBar.tsx
```

**Step 3: Update providers.tsx**
```typescript
// Remove this import
import { ParallelSessionsProvider } from '@/contexts/ParallelSessionsContext';

// Remove this wrapper
<ParallelSessionsProvider>
```

**Step 4: Simplify page.tsx**

Remove all references to:
- `useParallelSessions()` hook
- `tabs`, `activeTab`, `activeTabId`
- Tab management functions
- Background polling logic
- Display data switching logic

Use WebSocket state directly:
```typescript
const {
  consoleOutput,
  dagData,
  costSummary,
  workflowStatus,
  connect,
  disconnect,
  resumeSession
} = useWebSocket();
```

**Step 5: Update navigation**

When starting new session:
```typescript
const handleNewSession = async () => {
  // Disconnect current session if active
  if (copilotSessionId) {
    await handleSuspend(); // Auto-pause current
  }

  // Start new session
  await connect(taskId, task, config);
};
```

#### 9. User Experience Changes

**Before:**
- User can open 5+ sessions in tabs
- Switch between them freely
- Background tabs keep running (polled)
- Can forget about sessions in background tabs

**After:**
- User focuses on one session at a time
- Must explicitly pause before switching
- Clearer mental model: "current session"
- Better awareness of running workflows

#### 10. Performance Improvements

**Removed overhead:**
- ❌ Background polling (5s intervals)
- ❌ Tab state snapshots (memory)
- ❌ Multiple API calls per tab
- ❌ Complex state synchronization

**Expected gains:**
- 🚀 50-70% reduction in API calls
- 🚀 Cleaner React component tree
- 🚀 Faster page load (less context initialization)
- 🚀 Simpler state management (easier debugging)

#### 11. Recommended Implementation Order

1. **Phase 1: Prepare**
   - Audit current `page.tsx` for tab dependencies
   - Document current tab-specific logic
   - Test current session resume flow

2. **Phase 2: Remove**
   - Delete `ParallelSessionsContext.tsx`
   - Delete `SessionTabBar.tsx`
   - Update `providers.tsx`

3. **Phase 3: Refactor**
   - Simplify `page.tsx` display logic
   - Remove tab management UI
   - Update session navigation

4. **Phase 4: Test**
   - Test session creation
   - Test session resume
   - Test session switching (pause → resume)
   - Test WebSocket reconnection

5. **Phase 5: Polish**
   - Add clear "current session" indicator
   - Add warnings when starting new session
   - Update documentation

#### 12. Code Comparison

**Current `page.tsx` Complexity:**
```typescript
// ~800 lines with:
- Tab management (100+ lines)
- Background polling (50+ lines)
- Display data switching (50+ lines)
- Tab state synchronization (30+ lines)
```

**Simplified `page.tsx`:**
```typescript
// ~500 lines with:
- Direct WebSocket state usage
- Simple session switching
- Cleaner component structure
```

**Estimated LOC reduction:** ~300 lines (~37% reduction)

#### 13. Benefits Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Contexts** | 2 (WebSocket + ParallelSessions) | 1 (WebSocket only) |
| **API Calls** | High (polling per tab) | Low (single session) |
| **Memory** | High (multiple snapshots) | Low (single state) |
| **Complexity** | High (tab management) | Low (direct state) |
| **UX** | Multi-tasking | Focused |
| **Code LOC** | ~800 lines | ~500 lines |

#### 14. Potential Issues & Solutions

**Issue 1: User wants multiple sessions**
- **Solution:** Session browser always available - quick pause/resume
- **Alternative:** Add "session bookmarks" for frequently used sessions

**Issue 2: Accidental session switch**
- **Solution:** Confirm dialog before disconnecting active session
- **Warning:** "You have an active session. Pause before switching?"

**Issue 3: Lost work when starting new**
- **Solution:** Auto-pause current session before starting new
- **Safety:** Always persist session state on pause

#### 15. Next Steps

To implement single-session approach:

```bash
# 1. Create feature branch
git checkout -b feature/single-session-simplification

# 2. Remove multi-tab files
git rm mars-ui/contexts/ParallelSessionsContext.tsx
git rm mars-ui/components/layout/SessionTabBar.tsx

# 3. Update providers and page.tsx
# (Manual refactoring needed)

# 4. Test thoroughly
npm run dev
# Verify: session creation, resume, switching

# 5. Commit changes
git add .
git commit -m "Simplify to single-session approach"

# 6. Update documentation
```

---

*Last updated: 2026-03-01*
*Version: 2.0 - Added single-session simplification guide*
