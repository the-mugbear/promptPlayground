@test_runs_bp.route('/<int:run_id>/analyze_invalid_chars', methods=['POST'])
@login_required
def analyze_invalid_chars(run_id):
    """Analyzes test run results to identify invalid characters and creates a prompt filter."""
    try:
        # Get the test run with its executions
        run = TestRun.query.options(
            selectinload(TestRun.attempts).selectinload(TestRunAttempt.executions)
        ).get_or_404(run_id)

        # Get the latest attempt
        latest_attempt = run.attempts[-1] if run.attempts else None
        if not latest_attempt:
            return jsonify({'error': 'No test attempts found'}), 400

        # Analyze executions to find failed characters
        failed_chars = []
        successful_chars = []
        
        for execution in latest_attempt.executions:
            if execution.status == 'failed':
                # Extract the character from the test case name
                char = execution.test_case.name.split(': ')[-1]
                failed_chars.append(char)
            elif execution.status == 'passed':
                char = execution.test_case.name.split(': ')[-1]
                successful_chars.append(char)

        if not failed_chars:
            return jsonify({'error': 'No failed characters found'}), 400

        # Create a prompt filter
        filter_name = f"Character Filter from Run {run_id}"
        filter_description = f"Automatically generated from test run {run_id}. Blocks the following characters: {', '.join(failed_chars)}"
        
        pf = PromptFilter(
            name=filter_name,
            description=filter_description,
            filter_type="character",
            filter_config=json.dumps({
                "characters": failed_chars,
                "mode": "block"
            }),
            user_id=current_user.id
        )
        
        db.session.add(pf)
        db.session.commit()

        return jsonify({
            'success': True,
            'filter_id': pf.id,
            'filter_name': pf.name,
            'failed_chars': failed_chars,
            'successful_chars': successful_chars
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500 