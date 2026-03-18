# Round 8: Advanced Synchronization & Distributed Computing

## 🎯 Goal
Implement high-precision synchronization using HPET, distributed computing architecture, advanced buffering strategies, and network jitter measurement for multi-device audio synchronization.

---

## 📋 Topics to Explore

### 1. HPET (High Precision Event Timer) Integration
**Objective:** Use hardware-level timing for precise audio synchronization

**Key Points:**
- HPET provides 64-bit up-counter at ≥10 MHz (sub-microsecond precision)
- More accurate than `time.time()` or `time.perf_counter()`
- Windows: Access via `QueryPerformanceCounter` / `QueryPerformanceFrequency`
- Linux: Access via `/dev/hpet` or kernel interfaces
- Python: Use `ctypes` to access Windows API or `time.perf_counter()` (may use HPET)

**Implementation Considerations:**
- Replace `time.time()` with HPET-based timing for critical paths
- Use HPET for:
  - Buffer timestamp tracking
  - Playback start time synchronization
  - Latency measurement
  - Jitter calculation

**Challenges:**
- HPET may be disabled on some systems (BIOS/UEFI)
- Need fallback to `time.perf_counter()` or `time.time()`
- Cross-platform compatibility (Windows vs Linux)

---

### 2. Distributed Computing Architecture
**Objective:** Design architecture for multi-node audio synchronization

**Key Concepts:**
- **Master Node:** Captures audio, distributes to fleet
- **Fleet Nodes:** Receive audio chunks, play synchronized
- **Clock Synchronization:** All nodes must have synchronized system clocks
- **Network Jitter Measurement:** Measure and compensate for network variability

**Architecture Design:**
```
┌─────────────────┐
│  Master Node   │
│  (Captures)    │
└────────┬────────┘
         │
         ├─── Network ───┐
         │               │
    ┌────▼────┐    ┌────▼────┐
    │ Node 1  │    │ Node 2  │
    │(Device) │    │(Device) │
    └─────────┘    └─────────┘
```

**Components:**
1. **Master Node:**
   - Captures audio from system
   - Timestamps chunks using HPET
   - Distributes chunks to fleet nodes
   - Monitors node health and synchronization

2. **Fleet Nodes:**
   - Receive audio chunks with timestamps
   - Buffer chunks in queue
   - Play from queue based on system clock
   - Report jitter and synchronization status

3. **Clock Synchronization:**
   - Use NTP or PTP for initial sync
   - Measure and compensate for clock drift
   - Adjust playback timing based on clock offset

---

### 3. Advanced Buffering Strategy
**Objective:** Implement 200-500ms front walk buffer with 3-5ms chunk reception

**Design:**
```
┌─────────────────────────────────────────┐
│         Front Walk Buffer               │
│  (200-500ms of audio data)              │
│                                         │
│  [Chunk 0] [Chunk 1] [Chunk 2] ...    │
│    ↑                                    │
│  Play Head                              │
└─────────────────────────────────────────┘
         │
         │ Receive every 3-5ms
         ▼
┌─────────────────────────────────────────┐
│      Reception Queue (Set/Queue)         │
│  [New Chunk] [New Chunk] [New Chunk]   │
└─────────────────────────────────────────┘
```

**Key Features:**
- **Front Walk Buffer:** 200-500ms of pre-buffered audio
  - Provides jitter tolerance
  - Allows smooth playback during network hiccups
  - Size configurable based on network conditions

- **Chunk Reception:** Every 3-5ms
  - Small chunks reduce latency
  - Frequent updates allow quick adaptation
  - Timestamp each chunk with HPET

- **Queue Management:**
  - Use ordered set/queue for chunk storage
  - Timestamp-based ordering
  - Remove played chunks from front
  - Maintain buffer size limits

- **Playback from System Clock:**
  - Use HPET/system clock to determine when to play
  - Calculate: `play_time = chunk_timestamp + buffer_delay`
  - Play chunk when `current_time >= play_time`

**Implementation:**
```python
class AdvancedBuffer:
    def __init__(self, buffer_size_ms=300, chunk_interval_ms=4):
        self.buffer_size_ms = buffer_size_ms
        self.chunk_interval_ms = chunk_interval_ms
        self.chunk_queue = deque()  # Ordered queue
        self.play_head = 0  # Current playback position
        self.hpet_time = HPETTimer()  # HPET-based timer
        
    def receive_chunk(self, audio_data, timestamp):
        """Receive chunk every 3-5ms and add to queue."""
        chunk = {
            'data': audio_data,
            'timestamp': timestamp,
            'play_time': timestamp + (self.buffer_size_ms / 1000.0)
        }
        self.chunk_queue.append(chunk)
        
    def get_chunk_to_play(self):
        """Get chunk to play based on system clock."""
        current_time = self.hpet_time.now()
        
        # Find chunk that should be playing now
        while self.chunk_queue:
            chunk = self.chunk_queue[0]
            if current_time >= chunk['play_time']:
                return self.chunk_queue.popleft()
            else:
                # Not time to play yet
                break
                
        return None  # No chunk ready
```

---

### 4. Network Jitter Measurement
**Objective:** Measure and compensate for network jitter when joining a node

**Jitter Definition:**
- Variation in packet arrival times
- Can cause desynchronization
- Measured as: `jitter = |arrival_time[i] - expected_arrival_time[i]|`

**Measurement Strategy:**
1. **Initial Join:**
   - Node sends join request to master
   - Master responds with current time (HPET)
   - Node calculates clock offset: `offset = master_time - local_time`
   - Node adjusts local clock or tracks offset

2. **Jitter Measurement:**
   - Send periodic ping packets with timestamps
   - Measure round-trip time (RTT)
   - Calculate jitter: `jitter = std_dev(RTT)`
   - Track jitter over time window (e.g., 1 second)

3. **Synchronization Adjustment:**
   - Adjust buffer size based on jitter
   - Higher jitter → larger buffer (up to 500ms)
   - Lower jitter → smaller buffer (down to 200ms)
   - Dynamic adjustment during playback

**Implementation:**
```python
class NetworkJitterMeasurer:
    def __init__(self):
        self.rtt_samples = deque(maxlen=100)  # Last 100 RTT samples
        self.jitter_history = deque(maxlen=10)  # Last 10 jitter values
        
    def measure_rtt(self, master_time, local_time):
        """Measure round-trip time."""
        rtt = abs(master_time - local_time)
        self.rtt_samples.append(rtt)
        return rtt
    
    def calculate_jitter(self):
        """Calculate jitter as standard deviation of RTT."""
        if len(self.rtt_samples) < 2:
            return 0.0
        
        mean_rtt = sum(self.rtt_samples) / len(self.rtt_samples)
        variance = sum((x - mean_rtt) ** 2 for x in self.rtt_samples) / len(self.rtt_samples)
        jitter = variance ** 0.5  # Standard deviation
        
        self.jitter_history.append(jitter)
        return jitter
    
    def get_recommended_buffer_size(self):
        """Get recommended buffer size based on jitter."""
        avg_jitter = sum(self.jitter_history) / len(self.jitter_history) if self.jitter_history else 0
        
        # Map jitter to buffer size (200-500ms)
        if avg_jitter < 0.001:  # < 1ms
            return 200  # 200ms buffer
        elif avg_jitter < 0.005:  # < 5ms
            return 300  # 300ms buffer
        elif avg_jitter < 0.010:  # < 10ms
            return 400  # 400ms buffer
        else:  # >= 10ms
            return 500  # 500ms buffer
```

---

## 🏗️ Implementation Plan

### Phase 1: HPET Integration
1. Create `HPETTimer` class
   - Windows: Use `ctypes` to access `QueryPerformanceCounter`
   - Linux: Use `time.perf_counter()` (may use HPET)
   - Fallback to `time.perf_counter()` if HPET unavailable
   
2. Replace timing calls in critical paths
   - Buffer timestamp tracking
   - Playback synchronization
   - Latency measurement

3. Test HPET accuracy vs `time.time()`

### Phase 2: Advanced Buffering
1. Implement `AdvancedBuffer` class
   - Front walk buffer (200-500ms)
   - Chunk reception queue (3-5ms intervals)
   - System clock-based playback

2. Integrate with existing passthrough system
   - Replace current buffer management
   - Maintain backward compatibility

3. Test buffer behavior under various conditions

### Phase 3: Network Jitter Measurement
1. Implement `NetworkJitterMeasurer` class
   - RTT measurement
   - Jitter calculation
   - Buffer size recommendations

2. Add node join protocol
   - Clock synchronization
   - Jitter measurement during join
   - Initial buffer size calculation

3. Test jitter measurement accuracy

### Phase 4: Distributed Computing Architecture
1. Design master-fleet architecture
   - Master node implementation
   - Fleet node implementation
   - Communication protocol

2. Implement clock synchronization
   - NTP/PTP integration (optional)
   - Clock offset tracking
   - Drift compensation

3. Test multi-node synchronization

---

## 🔧 Technical Considerations

### HPET Access in Python

**Windows:**
```python
import ctypes
from ctypes import wintypes

# QueryPerformanceCounter
kernel32 = ctypes.windll.kernel32
QueryPerformanceCounter = kernel32.QueryPerformanceCounter
QueryPerformanceCounter.argtypes = [ctypes.POINTER(ctypes.c_int64)]
QueryPerformanceCounter.restype = wintypes.BOOL

QueryPerformanceFrequency = kernel32.QueryPerformanceFrequency
QueryPerformanceFrequency.argtypes = [ctypes.POINTER(ctypes.c_int64)]
QueryPerformanceFrequency.restype = wintypes.BOOL

def get_hpet_time():
    """Get HPET time in seconds."""
    frequency = ctypes.c_int64()
    counter = ctypes.c_int64()
    
    if QueryPerformanceFrequency(ctypes.byref(frequency)) and \
       QueryPerformanceCounter(ctypes.byref(counter)):
        return counter.value / frequency.value
    else:
        return None  # HPET not available
```

**Linux:**
```python
# time.perf_counter() may use HPET if available
import time

def get_hpet_time():
    """Get high-precision time (may use HPET)."""
    return time.perf_counter()
```

### Buffer Size Calculation

**Chunk Size:**
- Sample rate: 44100 Hz
- Chunk interval: 3-5ms
- Chunk size: `44100 * 0.004 = 176.4 samples` (≈177 samples per chunk)

**Buffer Size:**
- Buffer: 200-500ms
- Chunks in buffer: `(buffer_ms / chunk_interval_ms)`
- Example: 300ms buffer, 4ms chunks = 75 chunks

### Network Protocol Design

**Chunk Message Format:**
```python
{
    'type': 'audio_chunk',
    'sequence': 12345,  # Sequence number
    'timestamp': 1234567890.123456,  # HPET timestamp
    'data': <audio_data>,  # Audio samples
    'sample_rate': 44100,
    'channels': 2
}
```

**Synchronization Message:**
```python
{
    'type': 'sync_request',
    'local_time': 1234567890.123456,  # Local HPET time
}

{
    'type': 'sync_response',
    'master_time': 1234567890.123456,  # Master HPET time
    'local_time': 1234567890.123456,  # Echo of local time
}
```

---

## 📊 Expected Benefits

1. **Higher Precision:** HPET provides sub-microsecond timing
2. **Better Synchronization:** System clock-based playback ensures consistency
3. **Jitter Tolerance:** 200-500ms buffer handles network variability
4. **Scalability:** Distributed architecture supports multiple nodes
5. **Adaptability:** Dynamic buffer sizing based on network conditions

---

## ⚠️ Challenges & Considerations

1. **HPET Availability:** May not be available on all systems
2. **Network Latency:** Adds delay to distributed system
3. **Clock Drift:** Clocks may drift over time, need periodic resync
4. **Complexity:** More complex than current single-system approach
5. **Testing:** Requires multiple systems for full testing

---

## 🎯 Success Criteria

- ✅ HPET timing integrated and working
- ✅ Advanced buffering system implemented
- ✅ Network jitter measurement functional
- ✅ Multi-node synchronization working
- ✅ Backward compatibility maintained
- ✅ Performance improvements measurable

---

## 📝 Next Steps

1. **Discussion:** Review and refine this plan
2. **Prototype:** Start with HPET integration
3. **Iterate:** Build and test incrementally
4. **Document:** Document implementation details

---

*Round 8: Advanced Synchronization & Distributed Computing*  
*Status: Planning Phase*  
*Ready for Discussion & Implementation*
