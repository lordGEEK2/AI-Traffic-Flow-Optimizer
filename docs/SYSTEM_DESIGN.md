# Documentation

## System Design

### Signal Timing Algorithm

The signal controller uses dynamic timing based on traffic density:

```
green_time = BASE_GREEN_TIME + (density / 100) * (MAX_GREEN_TIME - BASE_GREEN_TIME)
green_time = clamp(green_time, MIN_GREEN_TIME, MAX_GREEN_TIME)
```

### Density Smoothing (EMA)

To prevent signal flickering from momentary count changes:

```
smoothed = α × raw + (1 − α) × previous_smoothed
```

Where `α = 0.3` provides a good balance between responsiveness and stability.

### Emergency Green Corridor

When an emergency vehicle is detected:
1. **Immediate**: Current intersection lane → GREEN, all others → RED
2. **Propagation**: Downstream intersections receive PRE-GREEN
3. **Timeout**: Auto-releases after 45 seconds if not cleared manually
4. **Cooldown**: 15-second cooldown prevents rapid re-triggers

### Detection Methods (Priority Order)
1. YOLO class detection (if custom model has emergency classes)
2. HSV color heuristic (red/blue light detection in upper frame third)
3. Simulation mode (periodic random events for demos)
