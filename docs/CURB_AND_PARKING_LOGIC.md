# Curb and Parking Logic

## Curb detection prior
Red/white curb segments are typically:
- segment length: about 100 cm
- stripe width: about 15 cm

Use this as a scene prior, not as a legal proof by itself.

## Parking versus stopping
The vehicle should be treated as parked only if:
- it remains nearly stationary for a sustained period
- nearby traffic keeps flowing, or
- the vehicle is clearly mounted on sidewalk / curb zone

Downgrade confidence when:
- surrounding traffic is also stopped
- the stop duration is short
- the scene indicates congestion or queueing

## Suggested outputs
```json
{
  "stationary_duration_seconds": 12.8,
  "traffic_flow_state": "flowing",
  "parking_likelihood_score": 0.91,
  "stop_due_to_traffic_possible": false
}
```
