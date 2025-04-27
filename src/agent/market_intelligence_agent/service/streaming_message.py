import json


def streaming_message(messages: list, next_agent, last_agent):
    print('-' * 120)
    agent_name = messages.get('name', None)
    if agent_name:
        if agent_name == "planner":
            full_plan = json.loads(messages['content'])
            print(full_plan['title'])
            print("-" * 120)
            print(full_plan['thought'])
            print("-" * 120)
            print(f"Planner handed off the following plan to the supervisor:")
            for step in full_plan['steps']:
                print("-" * 120)
                print(f"Task: {step['task']}")
                print(f"Agent: {step['agent']}")
                print(f"Description: {step['description']}")
                print(f"Note: {step['note']}")
        if agent_name == "supervisor":
            instructions = json.loads(messages['content'])
            print(f"Supervisor assigned the following task to {next_agent}: \n{instructions['task']}")
        if agent_name == "researcher":
            research_result = json.loads(messages['content'])
            print(f"Researcher has finished the task: {research_result['result_summary']}")
        if agent_name == "coder":
            coder_result = json.loads(messages['content'])
            print(f"Coder has finished the task: {coder_result['result_summary']}")
        if agent_name == "market":
            market_result = json.loads(messages['content'])
            print(f"Market agent has finished the task: {market_result['result_summary']}")
        if agent_name == "analyst":
            print(f"Analyst agent has finished the task")
        if agent_name == "reporter":
            print(f"Reporter has finished the task")
    if next_agent:
        print("=" * 120)
        if next_agent == "planner":
            print('Planner is thinking...')
        if next_agent == "supervisor":
            print(f'Supervisor is evaluating response from {last_agent}...')
        if next_agent == "researcher":
            print('Researcher is gathering information...')
        if next_agent == "coder":
            print('Coder is coding...')
        if next_agent == "market":
            print('Market agent is retrieving market data...')
        if next_agent == "browser":
            print('Browser agent is browsing the web...')
        if next_agent == "analyst":
            print('Analyst agent is analyzing the gathered information...')
        if next_agent == "reporter" and last_agent != "reporter":
            print('Reporter agent is preparing the final report...')
