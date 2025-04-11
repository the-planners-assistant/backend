#!/usr/bin/env python3
import asyncio
import asyncpg
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# --- Configuration ---
# Load environment variables from .env file
try:
    dotenv_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=dotenv_path, override=False)
    print(f"INFO: Loaded .env file from: {dotenv_path.resolve()}", file=sys.stderr)
except Exception as e:
    print(f"Warning: Could not load .env file: {e}", file=sys.stderr)

# Database Connection Details (from environment)
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5432")
DB_DATABASE = os.getenv("PGDATABASE", "planning_data")
DB_USER = os.getenv("PGUSER", "planner")
DB_PASSWORD = os.getenv("PGPASSWORD")
DB_SCHEMA = os.getenv("PGSCHEMA", "public") # Used for logging clarity

# --- Test Coordinates ---
# Use coordinates from your last test or change as needed
TEST_LAT = 51.505
TEST_LON = -0.09
TEST_RADIUS = 500 # Meters

async def run_debug_queries():
    """Connects to the DB and runs the constraint queries using SELECT *."""
    conn = None
    if not DB_PASSWORD:
        print("ERROR: PGPASSWORD environment variable not set.", file=sys.stderr)
        return

    print(f"--- Connecting to DB: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_DATABASE} ---")
    try:
        conn = await asyncpg.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_DATABASE,
            host=DB_HOST,
            port=DB_PORT
        )
        print("--- Connection Successful ---")

        # --- Query 1: Intersecting Constraints ---
        print(f"\n--- Running Intersect Query with SELECT * (Lat: {TEST_LAT}, Lon: {TEST_LON}) ---")
        # *** MODIFIED: Use SELECT * to see all loaded columns ***
        intersect_query = """
            SELECT *
            FROM spatial_constraints
            WHERE ST_Intersects(
                geom,
                ST_SetSRID(ST_MakePoint($1, $2), 4326)
            );
        """
        # *** END MODIFICATION ***
        try:
            affecting_results = await conn.fetch(intersect_query, TEST_LON, TEST_LAT)
            print(f"Found {len(affecting_results)} intersecting constraints:")
            if not affecting_results:
                print("  No intersecting constraints found at this location.")
            else:
                # Print all columns for the first few results for inspection
                for i, row in enumerate(affecting_results[:5]): # Limit output for brevity
                    print(f"\n  Intersecting Result {i+1}:")
                    row_dict = dict(row) # Convert record to dictionary
                    for key, value in row_dict.items():
                        # Truncate long geometry strings for readability
                        if key == GEOMETRY_NAME and isinstance(value, str) and len(value) > 100:
                             print(f"    {key}: {value[:100]}...")
                        # Try to pretty print if value looks like JSON string (optional)
                        elif isinstance(value, str) and value.strip().startswith('{'):
                            try:
                                parsed_json = json.loads(value)
                                print(f"    {key}: {json.dumps(parsed_json, indent=2)}")
                            except json.JSONDecodeError:
                                print(f"    {key}: {value}") # Print as string if not valid JSON
                        else:
                            print(f"    {key}: {value} (Type: {type(value).__name__})")
                    if i == 4: # Stop after 5 results
                         print("  ...")
                         break

        except asyncpg.PostgresError as e:
            print(f"ERROR during intersect query: {e}", file=sys.stderr)
            print(f"SQLSTATE: {e.sqlstate}", file=sys.stderr)
            if e.hint: print(f"HINT: {e.hint}", file=sys.stderr)
        except Exception as e:
            print(f"UNEXPECTED ERROR during intersect query: {e}", file=sys.stderr)


        # --- Query 2: Nearby Constraints (Optional - Keep SELECT * for now if needed) ---
        # You can run this if needed, it will also show all columns
        # print(f"\n--- Running Nearby Query with SELECT * (Radius: {TEST_RADIUS}m) ---")
        # nearby_query = """
        #     SELECT *,
        #            ST_Distance(
        #                geom::geography,
        #                ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography
        #            ) AS distance_m
        #     FROM spatial_constraints
        #     WHERE ST_DWithin(
        #         geom::geography,
        #         ST_SetSRID(ST_MakePoint($3, $4), 4326)::geography,
        #         $5 -- radius in meters
        #     )
        #     ORDER BY distance_m;
        # """
        # try:
        #     nearby_results = await conn.fetch(...)
        #     # ... (print logic similar to above) ...
        # except Exception as e:
        #     print(f"ERROR during nearby query: {e}", file=sys.stderr)

    except Exception as e:
        print(f"Failed to connect or execute query: {e}", file=sys.stderr)
    finally:
        if conn:
            await conn.close()
            print("\n--- Connection Closed ---")

if __name__ == "__main__":
    # Need to get GEOMETRY_NAME for printing logic
    GEOMETRY_NAME = os.getenv("GEOMETRY_NAME", "geom")
    asyncio.run(run_debug_queries())