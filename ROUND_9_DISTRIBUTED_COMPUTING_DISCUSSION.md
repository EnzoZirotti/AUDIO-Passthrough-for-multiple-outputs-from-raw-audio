# Round 9: Distributed Computing - Technical Discussion

## 🎯 Overview

We've implemented a master-fleet architecture for distributed audio synchronization across multiple network nodes. This allows multiple devices/computers to play synchronized audio over a network.

---

## 🏗️ Architecture Components

### 1. Network Protocol (`network_protocol.py`)

**Purpose:** Handles all network communication between master and fleet nodes.

**Features:**
- **UDP for Audio Chunks:** Low latency, can tolerate packet loss
- **TCP for Control Messages:** Reliable delivery for critical messages
- **Message Serialization:** Efficient binary format for audio, JSON for control
- **Protocol Constants:** Configurable message sizes and timeouts

**Message Types:**
- `JOIN_REQUEST` - Node wants to join fleet
- `JOIN_RESPONSE` - Master accepts/denies join
- `AUDIO_CHUNK` - Audio data with HPET timestamp
- `SYNC_REQUEST` - Clock synchronization request
- `SYNC_RESPONSE` - Clock synchronization response
- `HEARTBEAT` - Keep-alive ping
- `LEAVE` - Node disconnecting

**Audio Chunk Format (UDP):**
```
[Header: 18 bytes]
- Sequence: 4 bytes (uint32)
- Timestamp: 8 bytes (double, HPET time)
- Sample Rate: 2 bytes (uint16)
- Channels: 1 byte (uint8)
- Frames: 2 bytes (uint16)
- Type: 1 byte (uint8)

[Audio Data: variable]
- Binary audio samples (float32)
```

**Control Message Format (TCP):**
```
[Length: 4 bytes]
[JSON Data: variable]
```

---

### 2. Master Node (`master_node.py`)

**Purpose:** Captures audio and distributes to fleet nodes.

**Responsibilities:**
1. **Audio Capture:** Receives audio from passthrough system
2. **Chunk Distribution:** Sends audio chunks to all fleet nodes via UDP
3. **Node Management:** Handles join/leave requests
4. **Clock Synchronization:** Responds to sync requests
5. **Health Monitoring:** Tracks node heartbeats, removes dead nodes

**Key Features:**
- **HPET Timestamps:** Each chunk timestamped with HPET for precision
- **Node Registry:** Tracks all connected fleet nodes
- **Heartbeat Monitoring:** Removes nodes that don't respond
- **Fleet Status:** Provides status information about fleet

**Workflow:**
```
1. Master starts, listens on UDP (audio) and TCP (control)
2. Fleet nodes connect via TCP, send JOIN_REQUEST
3. Master responds with JOIN_RESPONSE (includes clock sync)
4. Master captures audio, timestamps with HPET
5. Master distributes chunks to all fleet nodes via UDP
6. Fleet nodes periodically send SYNC_REQUEST for clock sync
7. Master responds with SYNC_RESPONSE
8. Fleet nodes send HEARTBEAT periodically
9. Master monitors heartbeats, removes dead nodes
```

---

### 3. Fleet Node (`fleet_node.py`)

**Purpose:** Receives audio from master and plays synchronized.

**Responsibilities:**
1. **Connect to Master:** Establish TCP and UDP connections
2. **Receive Chunks:** Receive audio chunks via UDP
3. **Measure Jitter:** Use NetworkJitterMeasurer to measure network jitter
4. **Synchronize Clock:** Periodically sync clock with master
5. **Play Audio:** Use FrontWalkBuffer for synchronized playback

**Key Features:**
- **Clock Synchronization:** Measures and compensates for clock offset
- **Jitter Measurement:** Tracks network jitter, adjusts buffer size
- **FrontWalkBuffer:** Uses system clock-based playback
- **Automatic Reconnection:** Handles network errors gracefully

**Workflow:**
```
1. Fleet node connects to master via TCP
2. Sends JOIN_REQUEST with local HPET time
3. Receives JOIN_RESPONSE, calculates initial clock offset
4. Starts UDP receive thread for audio chunks
5. Starts sync thread (periodic clock synchronization)
6. Starts heartbeat thread (periodic keep-alive)
7. Receives chunks, adjusts timestamps for clock offset
8. Adds chunks to FrontWalkBuffer
9. Plays chunks based on system clock
10. Periodically syncs clock and adjusts buffer size
```

---

## 🔄 Synchronization Process

### Clock Synchronization

**Step 1: Initial Join**
```
Fleet Node → Master: JOIN_REQUEST { local_time: T1 }
Master → Fleet Node: JOIN_RESPONSE { master_time: T2, echo_local_time: T1 }
Fleet Node calculates: clock_offset = T2 - T1 (initial estimate)
```

**Step 2: Periodic Sync**
```
Fleet Node → Master: SYNC_REQUEST { local_time: T3 }
Master → Fleet Node: SYNC_RESPONSE { master_time: T4, echo_local_time: T3 }
Fleet Node calculates:
  - RTT = (T5 - T3) / 2  (where T5 = local receive time)
  - clock_offset = T4 - (T5 - RTT)
  - jitter = std_dev(RTT)
```

**Step 3: Timestamp Adjustment**
```
Master timestamp: T_master
Fleet node adjusts: T_local = T_master - clock_offset
FrontWalkBuffer receives: receive_chunk(audio_data, T_local)
```

### Playback Synchronization

**Process:**
1. Master captures audio
2. Master timestamps with HPET: `T_capture`
3. Master distributes chunk with timestamp
4. Fleet node receives, adjusts timestamp: `T_adjusted = T_capture - clock_offset`
5. Fleet node adds to FrontWalkBuffer: `play_time = T_adjusted + buffer_delay`
6. FrontWalkBuffer plays when: `current_time >= play_time`
7. All nodes play same chunk at same system time

---

## 📊 Jitter Measurement & Buffer Adjustment

### Jitter Measurement

**Process:**
1. Fleet node measures RTT for each SYNC_REQUEST
2. NetworkJitterMeasurer calculates jitter (standard deviation of RTT)
3. Tracks jitter over time window (default: 100 samples)

**Jitter → Buffer Size Mapping:**
- **< 1ms jitter** → 200ms buffer
- **1-5ms jitter** → 300ms buffer
- **5-10ms jitter** → 400ms buffer
- **> 10ms jitter** → 500ms buffer

### Dynamic Buffer Adjustment

**Process:**
1. Fleet node measures jitter during sync
2. Gets recommended buffer size from NetworkJitterMeasurer
3. If change is significant (>50ms), adjusts FrontWalkBuffer
4. Buffer adapts to network conditions automatically

**Benefits:**
- Low jitter networks → smaller buffer → lower latency
- High jitter networks → larger buffer → better tolerance
- Automatic adaptation to changing network conditions

---

## 🔧 Technical Implementation Details

### Network Ports

**Default Configuration:**
- **UDP Port:** 5000 (audio chunks)
- **TCP Port:** 5001 (control messages)

**Configurable:**
- Can be changed in MasterNode/FleetNode constructors
- Should use different ports if running multiple fleets

### Message Sizes

**Audio Chunk (UDP):**
- Header: 18 bytes
- Audio data: variable (typically 8KB for 1024 frames × 2 channels × 4 bytes)
- Total: ~8KB per chunk

**Control Messages (TCP):**
- Length prefix: 4 bytes
- JSON data: typically 50-200 bytes
- Total: ~100-250 bytes per message

### Threading Model

**Master Node:**
- Main thread: Audio capture and distribution
- TCP server thread: Handles control messages
- Heartbeat thread: Monitors fleet health

**Fleet Node:**
- Main thread: Connection management
- UDP receive thread: Receives audio chunks
- Sync thread: Clock synchronization
- Heartbeat thread: Sends keep-alive

---

## 🎯 Use Cases

### 1. Multi-Room Audio
- Master in living room captures audio
- Fleet nodes in bedroom, kitchen, etc.
- All rooms play synchronized audio

### 2. Multi-Device Synchronization
- Master on computer
- Fleet nodes on phones, tablets, other computers
- All devices play same audio simultaneously

### 3. Distributed Speaker System
- Master captures system audio
- Multiple fleet nodes with different speakers
- Creates synchronized multi-speaker setup

---

## ⚠️ Challenges & Solutions

### Challenge 1: Network Latency
**Problem:** Network adds delay to audio
**Solution:** 
- FrontWalkBuffer provides 200-500ms buffer
- Jitter measurement adapts buffer size
- Clock synchronization compensates for offset

### Challenge 2: Clock Drift
**Problem:** Clocks drift over time
**Solution:**
- Periodic clock synchronization (every 5 seconds)
- Continuous clock offset tracking
- Timestamp adjustment on every chunk

### Challenge 3: Packet Loss
**Problem:** UDP packets may be lost
**Solution:**
- FrontWalkBuffer provides buffer tolerance
- Sequence numbers allow detection of lost packets
- Buffer can handle occasional packet loss

### Challenge 4: Network Jitter
**Problem:** Variable network delays
**Solution:**
- Jitter measurement tracks variability
- Dynamic buffer sizing adapts to jitter
- System clock-based playback smooths variations

### Challenge 5: Firewall/NAT
**Problem:** Nodes behind firewalls/NAT
**Solution:**
- UDP/TCP ports need to be open
- May need port forwarding
- Could use UPnP for automatic port mapping (future)

---

## 📝 Integration Points

### With Existing Passthrough System

**Master Mode:**
- Extend `start_audio_passthrough()` to create MasterNode
- Call `master.distribute_audio_chunk()` in capture callbacks
- Display fleet status in GUI

**Fleet Mode:**
- Create FleetNode, connect to master
- Use `fleet.get_chunk_to_play()` in output callbacks
- Display connection status and jitter in GUI

### With FrontWalkBuffer

**Already Integrated:**
- FleetNode uses FrontWalkBuffer for playback
- HPET timestamps ensure precision
- System clock-based playback ensures synchronization

---

## 🚀 Future Enhancements

1. **Multicast Support:** Use UDP multicast for efficient distribution
2. **Encryption:** Encrypt audio chunks for security
3. **Compression:** Compress audio for lower bandwidth
4. **Discovery:** Automatic master discovery (mDNS/Bonjour)
5. **GUI Integration:** Add master/fleet mode toggles in GUI
6. **Statistics:** Real-time jitter and latency statistics
7. **Auto-Reconnect:** Automatic reconnection on network errors
8. **Load Balancing:** Distribute load across multiple masters

---

## 🧪 Testing Strategy

### Unit Tests
- Network protocol serialization/deserialization
- Master node node management
- Fleet node connection and sync

### Integration Tests
- Master-fleet connection
- Audio chunk distribution
- Clock synchronization accuracy
- Jitter measurement accuracy

### End-to-End Tests
- Multiple fleet nodes connected
- Synchronized playback test
- Network jitter simulation
- Clock drift simulation

---

## 📊 Expected Performance

### Latency
- **Network Latency:** 1-50ms (depending on network)
- **Buffer Delay:** 200-500ms (configurable)
- **Total Latency:** ~200-550ms from capture to playback

### Synchronization Accuracy
- **HPET Precision:** 0.1 microseconds
- **Clock Sync Accuracy:** <1ms (with periodic sync)
- **Playback Sync:** <5ms between nodes (on same network)

### Bandwidth
- **Audio Chunk:** ~8KB per chunk
- **Chunk Rate:** ~43 chunks/second (1024 frames at 44.1kHz)
- **Bandwidth:** ~350KB/s per node (~2.8Mbps)

---

*Round 9: Distributed Computing Discussion*  
*Status: Implementation Complete*  
*Ready for Integration & Testing*
