import asyncio
import json
import os
from pathlib import Path
from autogenstudio import TeamManager

async def run_team_from_config():
    # Create the TeamManager instance
    team_manager = TeamManager()
    
    script_dir = Path(__file__).resolve().parent
    team_json_path = script_dir / "custom_team_config.json"

    with open(team_json_path, "r") as f:
        team_config = json.load(f)

    task_description = """Do your job with the following information:
        1. Portal website url: https://www.brmsprovidergateway.com/provideronline/search.aspx
        2. Member ID (username): E01257465
        3. Date of Birth (password): 08/03/1988
        4. Patient Name: Liza Silina
        5. Service Date: 2024-01-15"""

    result = await team_manager.run(
        task=task_description,
        team_config=team_config
    )
    
    print("Team execution completed with result:", result)


    # async for message in team_manager.run_stream(
    #     task=task_description,
    #     team_config=team_config
    # ):
    #     print(message)

if __name__ == "__main__":
    asyncio.run(run_team_from_config())