from flask import Blueprint, Response, jsonify, stream_with_context

from streaming import catalog
import json
import time

bp = Blueprint('routes', __name__)


@bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'msg': 'The api is healthy'}), 200


@bp.get('/ready')
def ready_check():
    from api.readiness import readiness
    report = readiness()
    return jsonify(report), 200 if report['status'] == 'ready' else 503


# ----------------------------------------------------------------------
# Live match state (Redis <- Event Hubs consumer / local replay)
# ----------------------------------------------------------------------
@bp.route('/matches', methods=['GET'])
def list_matches():
    """Saved and streamed matches, deduplicated; live state takes precedence."""
    return jsonify({'matches': catalog.list_matches()}), 200


@bp.route('/matches/<match_id>/state', methods=['GET'])
def match_state(match_id):
    state = catalog.get_state(match_id)
    if state is None:
        return jsonify({'error': 'Match not found'}), 404
    return jsonify(state), 200


@bp.route('/matches/<match_id>/stream', methods=['GET'])
def match_stream(match_id):
    """SSE snapshots from the catalogue, checked once per second.

    Works with saved files and Redis. Heartbeats keep quiet connections open.
    """
    state = catalog.get_state(match_id)
    if state is None:
        return jsonify({'error': 'Match not found'}), 404

    def generate():
        # Poll the unified catalogue so saved matches work without Redis and a
        # newly started replay can take over without reconnecting the browser.
        previous = None
        heartbeat = time.monotonic()
        while True:
            snapshot = catalog.get_state(match_id)
            frame = json.dumps(snapshot) if snapshot else None
            if frame and frame != previous:
                yield f"event: state\ndata: {frame}\n\n"
                previous = frame
                heartbeat = time.monotonic()
            elif time.monotonic() - heartbeat >= 15:
                yield ": heartbeat\n\n"
                heartbeat = time.monotonic()
            time.sleep(1)

    response = Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
    )
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response
