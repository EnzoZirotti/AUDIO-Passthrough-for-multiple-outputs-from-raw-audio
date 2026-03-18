# Round 9: Distributed Computing Architecture

## 🎯 Goal
Implement master-fleet architecture for distributed audio synchronization across multiple network nodes.

---

## 📋 Architecture Overview

### Master-Fleet Model

```
┌─────────────────────────────────────────┐
│         Master Node                     │
│  - Captures system audio                │
│  - Distributes chunks to fleet         │
│  - Manages node synchronization        │
│  - Monitors fleet health               │
└──────────────┬──────────────────────────┘
               │
               │ Network (UDP/TCP)
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼───┐  ┌───▼───┐  ┌───▼───┐
│ Node 1│  │ Node 2│  │ Node 3│
│Device │  │Device │  │Device │
└───────┘  └───────┘  └───────┘
```

---

## 🏗️ Components

### 1. Master Node
**Responsibilities:**
- Capture system audio
- Timestamp chunks with HPET
- Distribute chunks to fleet nodes
- Handle node join/leave
- Monitor fleet health
- Manage clock synchronization

**Key Features:**
- Audio capture (existing passthrough system)
- Network distribution (UDP multicast or TCP)
- Node registry (track connected nodes)
- Health monitoring (ping/heartbeat)
- Clock sync protocol

### 2. Fleet Node
**Responsibilities:**
- Connect to master node
- Receive audio chunks
- Measure network jitter
- Synchronize clock with master
- Play audio synchronized with fleet

**Key Features:**
- Network client (connect to master)
- Chunk reception (with timestamps)
- Jitter measurement (NetworkJitterMeasurer)
- Clock synchronization
- FrontWalkBuffer for playback

### 3. Communication Protocol

**Message Types:**
1. **JOIN_REQUEST** - Node wants to join fleet
2. **JOIN_RESPONSE** - Master accepts/denies join
3. **AUDIO_CHUNK** - Audio data with timestamp
4. **SYNC_REQUEST** - Clock synchronization request
5. **SYNC_RESPONSE** - Clock synchronization response
6. **HEARTBEAT** - Keep-alive ping
7. **LEAVE** - Node disconnecting

**Protocol Design:**
- UDP for audio chunks (low latency, can tolerate loss)
- TCP for control messages (reliable)
- JSON for control, binary for audio

---

## 🔧 Implementation Plan

### Phase 1: Communication Layer
1. Create network communication module
   - UDP socket for audio chunks
   - TCP socket for control messages
   - Message serialization/deserialization
   - Error handling and reconnection

### Phase 2: Master Node
1. Extend passthrough system
   - Add network distribution
   - Node registry management
   - Health monitoring
   - Clock sync server

### Phase 3: Fleet Node
1. Create fleet node client
   - Connect to master
   - Receive and buffer chunks
   - Measure jitter
   - Synchronize clock
   - Play synchronized audio

### Phase 4: Integration
1. Integrate with GUI
   - Master mode toggle
   - Fleet mode toggle
   - Node status display
   - Network configuration

---

## 📊 Technical Details

### Network Protocol

**Audio Chunk Message (UDP):**
```python
{
    'type': 'audio_chunk',
    'sequence': 12345,
    'timestamp': 1234567890.123456,  # HPET timestamp
    'data': <binary audio data>,
    'sample_rate': 44100,
    'channels': 2,
    'frames': 1024
}
```

**Control Messages (TCP):**
```python
# JOIN_REQUEST
{
    'type': 'join_request',
    'node_id': 'node_12345',
    'local_time': 1234567890.123456
}

# JOIN_RESPONSE
{
    'type': 'join_response',
    'accepted': True,
    'master_time': 1234567890.123456,
    'echo_local_time': 1234567890.123456,
    'fleet_id': 'fleet_abc123'
}

# SYNC_REQUEST
{
    'type': 'sync_request',
    'node_id': 'node_12345',
    'local_time': 1234567890.123456
}

# SYNC_RESPONSE
{
    'type': 'sync_response',
    'master_time': 1234567890.123456,
    'echo_local_time': 1234567890.123456
}
```

### Clock Synchronization

**Process:**
1. Node sends SYNC_REQUEST with local HPET time
2. Master receives, records receive time
3. Master sends SYNC_RESPONSE with:
   - Master HPET time (when response sent)
   - Echo of node's local time
4. Node calculates:
   - RTT = (receive_time - send_time) / 2
   - Clock offset = master_time - (local_receive_time - RTT)
5. Node adjusts timestamps using offset

### Jitter Measurement

**Process:**
1. Node measures RTT for each SYNC_REQUEST
2. NetworkJitterMeasurer calculates jitter (std dev)
3. Buffer size adjusted based on jitter:
   - Low jitter (<1ms) → 200ms buffer
   - Medium jitter (1-5ms) → 300ms buffer
   - High jitter (5-10ms) → 400ms buffer
   - Very high jitter (>10ms) → 500ms buffer

### Synchronized Playback

**Process:**
1. Master captures audio, timestamps with HPET
2. Master distributes chunk with timestamp
3. Node receives chunk, adjusts timestamp for clock offset
4. Node adds to FrontWalkBuffer with adjusted timestamp
5. FrontWalkBuffer plays chunk when: `current_time >= play_time`
6. All nodes play same chunk at same system time

---

## 🎯 Benefits

1. **Multi-Device Synchronization:** Play to multiple devices over network
2. **Scalability:** Add/remove nodes dynamically
3. **Jitter Tolerance:** Adaptive buffering based on network conditions
4. **Precision:** HPET timestamps ensure sub-millisecond accuracy
5. **Resilience:** Health monitoring and automatic reconnection

---

## ⚠️ Challenges

1. **Network Latency:** Adds delay to distributed system
2. **Clock Drift:** Clocks may drift, need periodic resync
3. **Packet Loss:** UDP chunks may be lost (need handling)
4. **Network Jitter:** Variable delays affect synchronization
5. **Firewall/NAT:** May need port forwarding or UPnP

---

## 📝 Implementation Steps

1. **Create Network Module** (`bluetoothstreamer/streaming/network_protocol.py`)
2. **Create Master Node** (`bluetoothstreamer/streaming/master_node.py`)
3. **Create Fleet Node** (`bluetoothstreamer/streaming/fleet_node.py`)
4. **Integrate with GUI** (add master/fleet mode options)
5. **Testing** (test with multiple nodes)

---

*Round 9: Distributed Computing*  
*Status: Planning Phase*  
*Ready for Implementation*
