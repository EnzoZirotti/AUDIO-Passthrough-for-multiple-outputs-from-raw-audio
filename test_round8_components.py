"""
Test script for Round 8 components: HPET, FrontWalkBuffer, JitterMeasurer
"""

import numpy as np
import time
from bluetoothstreamer.core import HPETTimer, FrontWalkBuffer, NetworkJitterMeasurer, get_hpet_timer

def test_hpet_timer():
    """Test HPET timer functionality."""
    print("=" * 60)
    print("Testing HPET Timer")
    print("=" * 60)
    
    hpet = HPETTimer()
    print(f"HPET Available: {hpet.available}")
    print(f"Using HPET: {hpet.using_hpet}")
    if hpet.frequency:
        print(f"Frequency: {hpet.frequency:.0f} Hz ({hpet.frequency/1e6:.2f} MHz)")
    print(f"Resolution: {hpet.get_resolution()*1e6:.3f} microseconds")
    
    # Test timing accuracy
    print("\nTiming Accuracy Test:")
    times = []
    for i in range(10):
        t1 = hpet.now()
        time.sleep(0.001)  # 1ms
        t2 = hpet.now()
        elapsed = t2 - t1
        times.append(elapsed)
        print(f"  Sleep 1ms: measured {elapsed*1000:.3f}ms")
    
    avg = sum(times) / len(times)
    print(f"\nAverage: {avg*1000:.3f}ms (expected: 1.0ms)")
    print(f"Variance: {np.var(times)*1e6:.3f} microseconds")
    
    print("\n[OK] HPET Timer test complete\n")


def test_front_walk_buffer():
    """Test FrontWalkBuffer functionality."""
    print("=" * 60)
    print("Testing FrontWalkBuffer")
    print("=" * 60)
    
    buffer = FrontWalkBuffer(buffer_size_ms=300, chunk_interval_ms=4, sample_rate=44100)
    print(f"Buffer size: {buffer.buffer_size_ms}ms")
    print(f"Chunk interval: {buffer.chunk_interval_ms}ms")
    print(f"Max chunks: {buffer.max_chunks}")
    print(f"Chunk size: {buffer.chunk_size_samples} samples")
    
    # Simulate receiving chunks
    print("\nSimulating chunk reception:")
    hpet = get_hpet_timer()
    start_time = hpet.now()
    
    for i in range(20):
        # Create test audio chunk (stereo)
        chunk_data = np.random.randn(buffer.chunk_size_samples, 2).astype(np.float32)
        timestamp = start_time + (i * buffer.chunk_interval_ms / 1000.0)
        sequence = buffer.receive_chunk(chunk_data, timestamp)
        print(f"  Chunk {sequence}: {len(chunk_data)} samples, timestamp={timestamp:.6f}")
    
    # Check buffer status
    status = buffer.get_buffer_status()
    print(f"\nBuffer Status:")
    print(f"  Chunks in buffer: {status['chunks_in_buffer']}")
    print(f"  Buffer fill: {status['buffer_fill_ms']:.1f}ms ({status['buffer_fill_percent']:.1f}%)")
    print(f"  Total received: {status['total_chunks_received']}")
    print(f"  Total played: {status['total_chunks_played']}")
    
    # Test playback
    print("\nTesting playback (waiting for play times):")
    frames_needed = 512  # Typical callback size
    
    # Wait for buffer to fill and chunks to be ready
    time.sleep(0.35)  # Wait 350ms (buffer is 300ms)
    
    chunks_played = 0
    for i in range(5):
        chunk_data, sequence, wait_time = buffer.get_chunk_to_play(frames_needed)
        if chunk_data is not None:
            print(f"  Played chunk {sequence}: {len(chunk_data)} frames")
            chunks_played += 1
        else:
            if wait_time is not None:
                print(f"  Waiting {wait_time*1000:.2f}ms for next chunk")
            else:
                print(f"  No chunks available")
            time.sleep(0.01)  # Small delay
    
    status = buffer.get_buffer_status()
    print(f"\nAfter playback:")
    print(f"  Chunks played: {chunks_played}")
    print(f"  Buffer fill: {status['buffer_fill_ms']:.1f}ms")
    print(f"  Underruns: {status['stats']['underruns']}")
    print(f"  Overruns: {status['stats']['overruns']}")
    
    print("\n[OK] FrontWalkBuffer test complete\n")


def test_jitter_measurer():
    """Test NetworkJitterMeasurer functionality."""
    print("=" * 60)
    print("Testing NetworkJitterMeasurer")
    print("=" * 60)
    
    measurer = NetworkJitterMeasurer(window_size=10)
    hpet = get_hpet_timer()
    
    print("Simulating network measurements:")
    
    # Simulate network round-trips with varying jitter
    base_rtt = 0.010  # 10ms base RTT
    for i in range(15):
        # Simulate jitter (varying RTT)
        jitter_amount = np.random.normal(0, 0.002)  # 2ms std dev
        actual_rtt = base_rtt + abs(jitter_amount)
        
        local_send = hpet.now()
        time.sleep(actual_rtt / 2)  # Simulate network delay
        master_time = hpet.now() + 0.001  # Master is slightly ahead
        local_receive = hpet.now() + actual_rtt / 2
        
        jitter = measurer.measure_round_trip(master_time, local_send, local_receive)
        
        if jitter > 0:
            print(f"  Measurement {i+1}: RTT={actual_rtt*1000:.2f}ms, "
                  f"Jitter={jitter*1000:.2f}ms, "
                  f"Offset={measurer.get_clock_offset()*1000:.2f}ms")
    
    # Get statistics
    stats = measurer.get_stats()
    print(f"\nStatistics:")
    print(f"  Measurements taken: {stats['measurements_taken']}")
    print(f"  Current jitter: {stats['current_jitter_ms']:.2f}ms")
    print(f"  Average jitter: {stats['average_jitter_ms']:.2f}ms")
    print(f"  Clock offset: {stats['clock_offset_ms']:.2f}ms")
    print(f"  Recommended buffer: {stats['recommended_buffer_ms']:.1f}ms")
    
    print("\n[OK] NetworkJitterMeasurer test complete\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Round 8 Component Tests")
    print("=" * 60 + "\n")
    
    try:
        test_hpet_timer()
        test_front_walk_buffer()
        test_jitter_measurer()
        
        print("=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
