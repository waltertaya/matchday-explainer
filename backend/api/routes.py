from flask import Blueprint, Response, jsonify, request, stream_with_context

from streaming import state as mstate
import json
import queue
import threading
import time

bp = Blueprint('routes', __name__)


@bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({'msg': 'The api is healthy'}), 200


# ----------------------------------------------------------------------
# Live match state (Redis <- Event Hubs consumer / local replay)
# ----------------------------------------------------------------------
@bp.route('/matches', methods=['GET'])
def list_matches():
    """All matches the state builder has seen, newest activity first."""
    return jsonify({'matches': mstate.list_matches()}), 200


@bp.route('/matches/<match_id>/state', methods=['GET'])
def match_state(match_id):
    state = mstate.load_state(match_id)
    if state is None:
        return jsonify({'error': 'Match not found (no state in Redis)'}), 404
    return jsonify(state), 200


@bp.route('/matches/<match_id>/stream', methods=['GET'])
def match_stream(match_id):
    """Server-Sent Events: pushes the full state after every stream event.

    The browser subscribes with EventSource; every state change in Redis
    (published by the state builder) is forwarded as an `event: state`
    message. A heartbeat comment keeps intermediaries from closing the
    connection during quiet spells.
    """
    state = mstate.load_state(match_id)
    if state is None:
        return jsonify({'error': 'Match not found (no state in Redis)'}), 404

    channel = mstate.CHANNEL.format(match_id=match_id)
    client = mstate.r()

    def generate():
        pubsub = client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(channel)
        try:
            # Initial snapshot so the client renders immediately.
            snapshot = mstate.load_state(match_id)
            if snapshot:
                yield f"event: state\ndata: {json.dumps(snapshot)}\n\n"
            while True:
                msg = pubsub.get_message(timeout=15.0)
                if msg and msg['type'] == 'message':
                    snapshot = mstate.load_state(match_id)
                    if snapshot:
                        yield f"event: state\ndata: {json.dumps(snapshot)}\n\n"
                else:
                    yield ": heartbeat\n\n"
        finally:
            pubsub.close()

    response = Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
    )
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response
