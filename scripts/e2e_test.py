import requests

BASE_URL = 'http://127.0.0.1:8000'

print('1. Creating Task...')
res = requests.post(f'{BASE_URL}/api/tasks', json={'goal': 'Open calculator and calculate 5+5'}, timeout=10)
task = res.json()
task_id = task['id']
print(f'Task created: {task_id}')

print('2. Planning...')
res = requests.post(f'{BASE_URL}/api/planner/plan', json={'goal': 'Open calculator and calculate 5+5', 'task_id': task_id}, timeout=10)
plan = res.json()
print(f'Plan Response: {res.status_code} - {list(plan.keys()) if isinstance(plan, dict) else plan}')
