import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash # Or your hashing function
from extensions import db
from flask import Blueprint
from models.model_User import User, ROLE_ADMIN, ROLE_USER
from models.model_APIChain import APIChain, APIChainStep
from models.model_Endpoints import Endpoint

from services.chain_execution_service import APIChainExecutor, ChainExecutionError

# Format to seed and test chains
# podman exec -it fuzzy_prompts_web flask seed-test-chainD
# podman exec -it fuzzy_prompts_web flask execute-chain 1

bp = Blueprint('cli', __name__, cli_group=None)

@click.command('create-admin')
@click.option('--username', prompt=True, help='The username for the admin user.') #
@click.option('--email', prompt=True, help='The email address for the admin user.')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='The password for the admin user.')
@click.option('--is-admin', is_flag=True, help='Set this user as an admin.')

def create_admin_command(username, email, password, is_admin):
    """Creates a new admin user."""
    print(f"--- Create Admin Command ---")
    print(f"Received --username: {username}")
    print(f"Received --email: {email}")
    print(f"Received --is-admin flag: {is_admin} (Type: {type(is_admin)})") # Crucial debug

    existing_user = User.query.filter(
        (User.email == email) | (User.username == username)
    ).first()
    if existing_user:
        print(f"Error: User with email '{email}' or username '{username}' already exists.")
        return

    try:
        new_admin = User(
            username=username,
            email=email
        )
        new_admin.set_password(password)

        print(f"Value of is_admin before setting role: {is_admin}") # Another check
        if is_admin:
            print(f"Setting role to ROLE_ADMIN ('{ROLE_ADMIN}')")
            new_admin.role = ROLE_ADMIN
        else:
            print(f"Setting role to ROLE_USER ('{ROLE_USER}')")
            new_admin.role = ROLE_USER

        print(f"User object before commit: username='{new_admin.username}', email='{new_admin.email}', role='{new_admin.role}'")

        db.session.add(new_admin)
        db.session.commit()
        print(f"User '{new_admin.username}' (role: {new_admin.role}) created successfully.")
    except Exception as e:
        db.session.rollback()
        print(f"Error creating admin user: {e}")


@click.command('execute-chain')
@click.argument('chain_id', type=int)
@with_appcontext
def execute_chain_command(chain_id):
    """
    Executes a specific API chain by its ID.
    Example: flask execute-chain 1
    """
    click.echo(f"Attempting to execute API Chain with ID: {chain_id}...")

    chain = db.session.get(APIChain, chain_id) # More direct way to get by PK with Flask-SQLAlchemy 3.x+
    if not chain:
        click.secho(f"Error: API Chain with ID {chain_id} not found.", fg="red")
        return

    click.echo(f"Found Chain: {chain.name}. Preparing to execute...")
    
    executor = APIChainExecutor() # Instantiate your executor

    try:
        results = executor.execute_chain(chain_id)
        click.secho(f"\nChain execution completed for Chain ID: {chain_id}", fg="green")
        
        click.echo("\n--- Final Context ---")
        if results.get("final_context"):
            for key, value in results["final_context"].items():
                click.echo(f"  {key}: {value}")
        else:
            click.echo("  (No final context data)")

        click.echo("\n--- Step Results ---")
        if results.get("step_results"):
            for step_res in results["step_results"]:
                status_color = "green" if step_res.get("status") == "success" else "red"
                click.secho(
                    f"  Step Order: {step_res.get('step_order')}, "
                    f"Endpoint: {step_res.get('endpoint_name', 'N/A')}, "
                    f"Status: {step_res.get('status')}",
                    fg=status_color
                )
                if step_res.get("message"):
                    click.secho(f"    Message: {step_res.get('message')}", fg="yellow")
                if "response_status_code" in step_res:
                     click.echo(f"    Response Status: {step_res.get('response_status_code')}")

        # You can pretty-print the full results dictionary if you want more detail
        # import json
        # click.echo("\n--- Full Results (JSON) ---")
        # click.echo(json.dumps(results, indent=2, default=str)) # default=str for datetime etc.

    except ChainExecutionError as e:
        click.secho(f"Chain Execution Error for Chain ID {chain_id}: {e}", fg="red")
        if e.original_exception:
            click.secho(f"  Original Exception: {type(e.original_exception).__name__} - {e.original_exception}", fg="red")
        # Depending on your logger setup, this exception might also be logged.
    except Exception as e:
        click.secho(f"An unexpected error occurred while trying to execute chain {chain_id}: {e}", fg="red")
        # This will also likely appear in your Flask application logs.

@click.command('seed-test-chain')
@with_appcontext
def seed_test_chain_command():
    """
    Seeds the database with a sample two-step API chain for testing.
    This chain uses the public httpbin.org service.
    """
    click.echo("Seeding a sample API chain for testing...")

    # --- Step 1: Clean up any previous test chain with the same name ---
    # This makes the command idempotent (safe to run multiple times)
    existing_chain = APIChain.query.filter_by(name="Httpbin.org Test Chain").first()
    if existing_chain:
        click.echo("Found and deleting existing test chain to prevent duplicates.")
        db.session.delete(existing_chain)
        # Also delete the associated endpoints if they were just for this test
        Endpoint.query.filter_by(name="TEST_CHAIN_HTTPBIN_GET").delete()
        Endpoint.query.filter_by(name="TEST_CHAIN_HTTPBIN_POST").delete()
        db.session.commit()

    # --- Step 2: Create the necessary Endpoint records ---
    click.echo("Creating Endpoint configurations...")
    
    # Endpoint for Step 1: GET request to httpbin.org to get our request info back
    endpoint1_get = Endpoint(
        name="TEST_CHAIN_HTTPBIN_GET",
        hostname="https://httpbin.org",
        endpoint="/get",
        method="GET"
        # No payload or headers needed for this simple GET
    )
    db.session.add(endpoint1_get)

    # Endpoint for Step 2: POST request to httpbin.org, payload will be templated
    endpoint2_post = Endpoint(
        name="TEST_CHAIN_HTTPBIN_POST",
        hostname="https://httpbin.org",
        endpoint="/post",
        method="POST",
        # This payload contains a Jinja2 variable that will be replaced
        # with a value extracted from the response of Step 1.
        http_payload='{"source_host_from_step1": "{{ host_from_step1 }}", "message": "Data from previous step was injected!"}'
    )
    db.session.add(endpoint2_post)
    
    # We need to commit here so that the endpoints get IDs to be used in the steps
    db.session.commit()
    click.secho(f"  > Created Endpoint '{endpoint1_get.name}' with ID: {endpoint1_get.id}", fg="cyan")
    click.secho(f"  > Created Endpoint '{endpoint2_post.name}' with ID: {endpoint2_post.id}", fg="cyan")


    # --- Step 3: Create the APIChain that links the steps ---
    click.echo("Creating APIChain record...")
    test_chain = APIChain(
        name="Httpbin.org Test Chain",
        description="A test chain that gets data from httpbin.org/get and sends it to httpbin.org/post.",
        user_id=1  # Assuming a User with id=1 exists (e.g., your admin user)
    )
    db.session.add(test_chain)
    db.session.commit() # Commit to get the chain ID
    click.secho(f"  > Created APIChain '{test_chain.name}' with ID: {test_chain.id}", fg="cyan")


    # --- Step 4: Create the APIChainSteps ---
    click.echo("Creating APIChainStep records...")
    
    # Step 1: Call the GET endpoint and extract the 'Host' header from the JSON response body
    step1 = APIChainStep(
        chain_id=test_chain.id,
        endpoint_id=endpoint1_get.id,
        step_order=0,
        name="Get request info and extract Host header",
        # httpbin.org/get returns request headers in a JSON object called "headers"
        data_extraction_rules=[
            {
                "variable_name": "host_from_step1", 
                "source_type": "json_body", 
                "source_identifier": "headers.Host" # Use dot notation for nested JSON
            }
        ]
    )
    db.session.add(step1)

    # Step 2: Call the POST endpoint. It has no rules because it's the last step.
    step2 = APIChainStep(
        chain_id=test_chain.id,
        endpoint_id=endpoint2_post.id,
        step_order=1,
        name="Post the extracted Host value to a new endpoint"
        # No data_extraction_rules needed for the last step
    )
    db.session.add(step2)

    # --- Step 5: Final Commit ---
    db.session.commit()
    click.secho("Successfully seeded the database with a test API chain.", fg="green")
    click.echo(f"You can now run 'flask execute-chain {test_chain.id}' to test it.")


# Register the command using the blueprint method
# Ensure you import and register this blueprint in fuzzy_prompts.py create_app()
bp.cli.add_command(create_admin_command)
bp.cli.add_command(execute_chain_command)
bp.cli.add_command(seed_test_chain_command)