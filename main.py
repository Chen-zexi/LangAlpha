import asyncio
import sys
import os
import json
import argparse

project_root = os.path.dirname(os.path.abspath(__file__))

# Define asset paths relative to project root
ASSETS_DIR = os.path.join(project_root, 'assets')
RAW_RESPONSES_DIR = os.path.join(ASSETS_DIR, 'raw_responses')
REPORTS_DIR = os.path.join(ASSETS_DIR, 'reports')


os.makedirs(RAW_RESPONSES_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)


async def main():
    """Main function to prompt for task name, query, run the workflow, and save results."""
    print("Market Intelligence Agent CLI")
    print("-" * 30)

    try:
        task_name = input("Enter a name for this task (used for filenames): ")
        if not task_name:
            print("Task name is required. Exiting.")
            return

        # Sanitize task_name
        safe_task_name = "_".join(task_name.split())

        user_query = input("Enter your query: ")
        if not user_query:
            print("No query entered. Exiting.")
            return

        raw_response, final_report = await run_workflow(user_query=user_query)

        # --- Save Raw Response --- 
        raw_filename = os.path.join(RAW_RESPONSES_DIR, f"{safe_task_name}.json")
        try:
            serializable_raw_response = [chunk.dict() if hasattr(chunk, 'dict') else str(chunk) for chunk in raw_response]
            with open(raw_filename, 'w', encoding='utf-8') as f:
                json.dump(serializable_raw_response, f, indent=4)
            print(f"Raw response saved to: {raw_filename}")
        except Exception as e:
            print(f"Error saving raw response: {e}")

        # --- Save Final Report --- 
        report_filename = os.path.join(REPORTS_DIR, f"{safe_task_name}.md")
        try:
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write(final_report if final_report else "# No final report generated")
            print(f"Final report saved to: {report_filename}")
        except Exception as e:
            print(f"Error saving final report: {e}")

    except KeyboardInterrupt:
        print("\nOperation cancelled by user. Exiting.")
    except Exception as e:
        print(f"\nAn unexpected error occurred during execution: {e}")

if __name__ == "__main__":
    src_path = os.path.join(project_root, 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    parser = argparse.ArgumentParser(description="Run the Market Intelligence Agent.")
    parser.add_argument('-dev', '--development', action='store_true', help='Use the development workflow service.')
    args = parser.parse_args()
    if args.development:
        from src.agent.market_intelligence_agent.service.workflow_service_dev import run_workflow
    else:
        from src.agent.market_intelligence_agent.service.workflow_service import run_workflow
    asyncio.run(main()) 