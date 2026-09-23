DEFAULT_SEED = 42
DOCUMENTATION_NETWORKS = (
    "192.0.2.0/24",
    "198.51.100.0/24",
    "203.0.113.0/24",
)

THRESHOLDS = {
    "packet_loss": (3.0, 10.0),
    "latency": (80.0, 150.0),
    "cpu": (85.0, 95.0),
    "memory": (85.0, 95.0),
}
