# socket_events.py

from flask import request # To get the client's session ID (sid)
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user # To ensure actions are performed by authenticated users
from datetime import datetime

from extensions import socketio, db  # db might be needed if event handlers interact with models directly
from celery_app import celery      # CORRECT: Import celery from celery_app.py
from models.model_TestRun import TestRun
# from celery.result import AsyncResult # Not strictly needed here if just revoking by ID

# A helper function to emit updates to a specific room (can be shared with Celery tasks if structured differently,
# but Celery tasks will use socketio.emit directly via the message queue)
def emit_to_run_room(run_id, event, data):
    room = f'test_run_{run_id}'
    socketio.emit(event, data, room=room)
    print(f"SocketEvent: Emitted '{event}' to room '{room}'. Data: {data.get('status', data)}")


@socketio.on('connect')
def handle_connect():
    """
    Handles new client WebSocket connections.
    Authenticates users if needed for subsequent events.
    """
    if current_user.is_authenticated:
        print(f"SocketIO Client connected: {request.sid}, User: {current_user.id} ({current_user.email})")
        # No specific room joined here; client will request to join a test_run room.
    else:
        print(f"SocketIO Anonymous client connected: {request.sid}. Some actions may be restricted.")
        # You could choose to disconnect unauthenticated users if no anonymous interaction is allowed:
        # return False


@socketio.on('disconnect')
def handle_disconnect():
    """Handles client WebSocket disconnections."""
    print(f"SocketIO Client disconnected: {request.sid}")
    # Flask-SocketIO automatically handles leaving rooms the client was in upon disconnection.


@socketio.on('join_test_run_room')
def handle_join_test_run_room(data):
    """
    Allows a client to join a room specific to a TestRun to receive updates for it.
    Data should contain {'run_id': <test_run_id>}.
    """
    if not current_user.is_authenticated:
        emit('error_event', {'message': 'Authentication required to join room.'}, room=request.sid)
        print(f"SocketIO: Unauthenticated client {request.sid} attempted to join room.")
        return

    run_id = data.get('run_id')
    if not run_id:
        emit('error_event', {'message': 'run_id missing for join_test_run_room.'}, room=request.sid)
        return

    test_run = db.session.get(TestRun, run_id) # Use db.session.get for PK
    if not test_run:
        emit('error_event', {'message': f'TestRun {run_id} not found.'}, room=request.sid)
        return

    # Permission check: User should own the test run or be an admin
    if test_run.user_id != current_user.id and not current_user.is_admin:
        emit('error_event', {'message': 'Permission denied to monitor this test run.'}, room=request.sid)
        print(f"SocketIO: User {current_user.id} permission denied for run {run_id}.")
        return

    room_name = f'test_run_{run_id}'
    join_room(room_name)
    print(f"SocketIO: Client {request.sid} (User: {current_user.id}) joined room: {room_name}")

    # Send the current status of the test run back to the client who just joined
    emit('progress_update', test_run.get_status_data(), room=request.sid)


@socketio.on('leave_test_run_room')
def handle_leave_test_run_room(data):
    """Allows a client to explicitly leave a TestRun room."""
    if not current_user.is_authenticated:
        # Silently ignore or log, as they might not be in a room anyway
        return

    run_id = data.get('run_id')
    if not run_id:
        return # Or emit error

    room_name = f'test_run_{run_id}'
    leave_room(room_name)
    print(f"SocketIO: Client {request.sid} (User: {current_user.id}) left room: {room_name}")


# --- Handlers for Control Actions ---

@socketio.on('request_pause_run')
def handle_request_pause_run(data):
    """
    Client requests to pause a TestRun.
    Data should contain {'run_id': <test_run_id>}.
    """
    if not current_user.is_authenticated:
        emit('error_event', {'message': 'Authentication required.'}, room=request.sid)
        return

    run_id = data.get('run_id')
    if not run_id:
        emit('error_event', {'message': 'run_id missing for pause request.'}, room=request.sid)
        return

    test_run = db.session.get(TestRun, run_id)
    if not test_run:
        emit('error_event', {'message': f'TestRun {run_id} not found.'}, room=request.sid)
        return

    if test_run.user_id != current_user.id and not current_user.is_admin:
        emit('error_event', {'message': 'Permission denied.'}, room=request.sid)
        return

    if test_run.status == 'running':
        test_run.status = 'pausing' # Orchestrator task will see this and transition to 'paused'
        db.session.commit()
        print(f"SocketIO: Pause requested for TestRun {run_id} by User {current_user.id}. Status set to 'pausing'.")
        # The orchestrator task will emit 'run_paused' once it has actually paused.
        # We can emit a 'run_pausing' event here to give immediate feedback to all clients in the room.
        emit_to_run_room(run_id, 'run_pausing', test_run.get_status_data())
    else:
        emit('error_event', {'message': f'TestRun cannot be paused from status: {test_run.status}'}, room=request.sid)
        # Send current state back to the requester
        emit('progress_update', test_run.get_status_data(), room=request.sid)


@socketio.on('request_resume_run')
def handle_request_resume_run(data):
    """
    Client requests to resume a TestRun.
    Data should contain {'run_id': <test_run_id>}.
    """
    if not current_user.is_authenticated:
        emit('error_event', {'message': 'Authentication required.'}, room=request.sid)
        return

    run_id = data.get('run_id')
    if not run_id:
        emit('error_event', {'message': 'run_id missing for resume request.'}, room=request.sid)
        return

    test_run = db.session.get(TestRun, run_id)
    if not test_run:
        emit('error_event', {'message': f'TestRun {run_id} not found.'}, room=request.sid)
        return

    if test_run.user_id != current_user.id and not current_user.is_admin:
        emit('error_event', {'message': 'Permission denied.'}, room=request.sid)
        return

    if test_run.status == 'paused':
        test_run.status = 'running' # Orchestrator task will see this and resume
        db.session.commit()
        print(f"SocketIO: Resume requested for TestRun {run_id} by User {current_user.id}. Status set to 'running'.")
        # The orchestrator task will emit 'run_resuming' or a general 'progress_update'.
        # We can emit a 'run_resuming' event here for immediate feedback.
        emit_to_run_room(run_id, 'run_resuming', test_run.get_status_data())
    else:
        emit('error_event', {'message': f'TestRun cannot be resumed from status: {test_run.status}'}, room=request.sid)
        emit('progress_update', test_run.get_status_data(), room=request.sid)


@socketio.on('request_cancel_run')
def handle_request_cancel_run(data):
    """
    Client requests to cancel a TestRun.
    Data should contain {'run_id': <test_run_id>}.
    """
    if not current_user.is_authenticated:
        emit('error_event', {'message': 'Authentication required.'}, room=request.sid)
        return

    run_id = data.get('run_id')
    if not run_id:
        emit('error_event', {'message': 'run_id missing for cancel request.'}, room=request.sid)
        return

    test_run = db.session.get(TestRun, run_id)
    if not test_run:
        emit('error_event', {'message': f'TestRun {run_id} not found.'}, room=request.sid)
        return

    if test_run.user_id != current_user.id and not current_user.is_admin:
        emit('error_event', {'message': 'Permission denied.'}, room=request.sid)
        return

    # Valid states to initiate cancellation from
    valid_cancel_states = ['pending', 'running', 'pausing', 'paused']
    if test_run.status in valid_cancel_states:
        orchestrator_task_id = test_run.celery_task_id

        # Set status to 'cancelling' first. The orchestrator task should see this.
        test_run.status = 'cancelling'
        db.session.commit()
        print(f"SocketIO: Cancel requested for TestRun {run_id} (Task ID: {orchestrator_task_id}) by User {current_user.id}. Status set to 'cancelling'.")
        emit_to_run_room(run_id, 'run_cancelling', test_run.get_status_data())

        if orchestrator_task_id:
            try:
                # Send revoke signal to the orchestrator Celery task
                celery.control.revoke(orchestrator_task_id, signal='SIGTERM')
                print(f"SocketIO: Sent revoke(terminate=True) to Celery task {orchestrator_task_id} for TestRun {run_id}.")
                # The orchestrator task is responsible for its own cleanup and final status update ('cancelled' or 'failed').
            except Exception as e:
                print(f"SocketIO: Error sending revoke signal for task {orchestrator_task_id}: {e}")
                # The status is already 'cancelling'. The task might still see this and stop.
                # Or, a timeout mechanism in the orchestrator might eventually lead to 'failed'.
                emit('error_event', {'message': f'Error initiating task cancellation: {e}'}, room=request.sid)
        else:
            # No active orchestrator task ID, but status was in a cancellable state (e.g., 'pending' but task never stored ID yet, or error)
            print(f"SocketIO: TestRun {run_id} was in a cancellable state ({test_run.status}) but no Celery Task ID found. Setting status to 'cancelled'.")
            test_run.status = 'cancelled' # Directly set to cancelled
            test_run.end_time = datetime.utcnow()
            db.session.commit()
            emit_to_run_room(run_id, 'run_cancelled', test_run.get_status_data())
    else:
        emit('error_event', {'message': f'TestRun cannot be cancelled from status: {test_run.status}'}, room=request.sid)
        emit('progress_update', test_run.get_status_data(), room=request.sid)