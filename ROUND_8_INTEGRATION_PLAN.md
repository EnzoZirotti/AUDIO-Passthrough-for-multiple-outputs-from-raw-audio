# Round 8 Integration Plan

## Integration Strategy

### Phase 1: Add Configuration Option
- Add `use_front_walk_buffer` flag (default: False for backward compatibility)
- Make it configurable via GUI or environment variable

### Phase 2: Conditional Integration
- When `use_front_walk_buffer = True`:
  - Use `FrontWalkBuffer` instead of `audio_buffer` list
  - Use HPET timestamps instead of `time.time()`
  - Update output callbacks to use `get_chunk_to_play()`
- When `use_front_walk_buffer = False`:
  - Keep existing behavior (no changes)

### Phase 3: Testing
- Test with new buffer system enabled
- Test with new buffer system disabled (backward compatibility)
- Verify synchronization works correctly

## Key Changes

1. **Capture Callbacks:**
   - Replace `time.time()` with `hpet.now()` for timestamps
   - Use `front_walk_buffer.receive_chunk(audio_data, timestamp)` instead of `audio_buffer.append()`

2. **Output Callbacks:**
   - Replace direct buffer access with `front_walk_buffer.get_chunk_to_play(frames)`
   - Remove `device_read_indices` logic (FrontWalkBuffer handles this)

3. **Buffer Management:**
   - Remove manual buffer size limiting (FrontWalkBuffer handles this)
   - Remove `device_read_indices` adjustments (FrontWalkBuffer handles this)

## Benefits

- Higher precision timing (0.1 microseconds vs ~1ms)
- Better synchronization (system clock-based playback)
- Jitter tolerance (200-500ms buffer)
- Cleaner code (less manual buffer management)
