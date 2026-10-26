"""Read-only pre-demo checks: python -m streaming.doctor."""
import os


def main():
    from app import create_app
    from api.readiness import readiness

    with create_app().app_context():
        report = readiness()
    for name, check in report["checks"].items():
        print(f"{name:8} {check['status']:12} {check['detail']}")
    print(report["note"])
    if os.getenv("EVENTHUB_CONNECTION_STRING"):
        print(f"Azure configured: hub={os.getenv('EVENTHUB_NAME', 'match-events')}, "
              f"group={os.getenv('EVENTHUB_CONSUMER_GROUP', 'start-builder')}. "
              "Verify the group exists and keep streaming.consumer running.")
    else:
        print("Azure not configured. Use synth.generator --to-redis for the local pipeline.")
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
