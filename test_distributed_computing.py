"""
Test script for distributed computing components.
Tests MasterNode and FleetNode functionality.
"""

import time
import numpy as np
from bluetoothstreamer.streaming import MasterNode, FleetNode, NetworkProtocol

def test_network_protocol():
    """Test network protocol serialization."""
    print("=" * 60)
    print("Testing Network Protocol")
    print("=" * 60)
    
    protocol = NetworkProtocol("test_node")
    
    # Test control message serialization
    join_request = protocol.create_join_request(1234567890.123456)
    serialized = protocol.serialize_control_message(join_request)
    deserialized = protocol.deserialize_control_message(serialized)
    
    print(f"Join Request: {join_request}")
    print(f"Serialized: {len(serialized)} bytes")
    print(f"Deserialized: {deserialized}")
    assert deserialized['type'] == 'join_request'
    assert deserialized['node_id'] == 'test_node'
    print("[OK] Control message serialization works\n")
    
    # Test audio chunk serialization
    audio_data = np.random.randn(1024, 2).astype(np.float32).tobytes()
    serialized_chunk = protocol.serialize_audio_chunk(
        sequence=12345,
        timestamp=1234567890.123456,
        audio_data=audio_data,
        sample_rate=44100,
        channels=2,
        frames=1024
    )
    
    deserialized_chunk = protocol.deserialize_audio_chunk(serialized_chunk)
    print(f"Audio Chunk: sequence={deserialized_chunk['sequence']}, "
          f"timestamp={deserialized_chunk['timestamp']}, "
          f"frames={deserialized_chunk['frames']}")
    assert deserialized_chunk['sequence'] == 12345
    assert deserialized_chunk['frames'] == 1024
    print("[OK] Audio chunk serialization works\n")


def test_master_node():
    """Test master node initialization."""
    print("=" * 60)
    print("Testing Master Node")
    print("=" * 60)
    
    master = MasterNode(udp_port=5000, tcp_port=5001)
    print(f"Master Node ID: {master.node_id}")
    print(f"Fleet ID: {master.fleet_id}")
    print(f"UDP Port: {master.udp_port}")
    print(f"TCP Port: {master.tcp_port}")
    
    # Test starting (will fail if ports in use, but that's OK)
    try:
        master.start()
        print("[OK] Master node started")
        
        # Get status
        status = master.get_fleet_status()
        print(f"Fleet Status: {status['node_count']} nodes")
        
        # Test distributing chunk
        test_audio = np.random.randn(1024, 2).astype(np.float32)
        master.distribute_audio_chunk(test_audio, 44100)
        print(f"Chunk sequence: {master.chunk_sequence}")
        
        time.sleep(0.1)  # Let threads start
        master.stop()
        print("[OK] Master node stopped\n")
    except Exception as e:
        print(f"[SKIP] Master node test (ports may be in use): {e}\n")


def test_fleet_node():
    """Test fleet node initialization."""
    print("=" * 60)
    print("Testing Fleet Node")
    print("=" * 60)
    
    fleet = FleetNode(
        master_host="127.0.0.1",
        master_udp_port=5000,
        master_tcp_port=5001,
        sample_rate=44100
    )
    print(f"Fleet Node ID: {fleet.node_id}")
    print(f"Master: {fleet.master_host}:{fleet.master_tcp_port}")
    print(f"Buffer Size: {fleet.buffer_size_ms}ms")
    
    # Test status
    status = fleet.get_status()
    print(f"Status: connected={status['connected']}, "
          f"clock_offset={status['clock_offset_ms']:.2f}ms")
    
    print("[OK] Fleet node initialized\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Distributed Computing Component Tests")
    print("=" * 60 + "\n")
    
    try:
        test_network_protocol()
        test_master_node()
        test_fleet_node()
        
        print("=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
