from typing import Any

import requests


class OjClient:
    def __init__(self):
        self.session = requests.Session()

    def login(self, email: str, password: str):
        resp = self.session.post(
            'http://openjudge.cn/api/auth/login/',
            data={
                'email': email,
                'password': password
            },
            timeout=10
        )
        resp.raise_for_status()
        print(resp.json())

    def update_existing_problem(self, group_slug: str, problem_id: int, values: dict[str, Any]):
        url = f'http://{group_slug}.openjudge.cn/api/global-problem/modify/'
        resp = self.session.post(
            url,
            data={
                'privacy': 'private',
                'language': 'zh_CN',
                **values,
                'problemId': problem_id,
            },
            timeout=10
        )
        resp.raise_for_status()
        print(resp.json())
