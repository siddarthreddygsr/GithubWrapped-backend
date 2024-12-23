import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from collections import defaultdict
import os

app = FastAPI()
origins = ['*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

GITHUB_GRAPHQL_URL = 'https://api.github.com/graphql'


def retrieve_contribution_data(username: str, year: str) -> dict:
    token = os.environ.get('GITHUB_TOKEN')
    QUERY = '''
        query($userName:String!, $fromDate: DateTime!, $toDate: DateTime!) {
            user(login: $userName){
                contributionsCollection(from: $fromDate, to: $toDate) {
                    contributionCalendar {
                        totalContributions
                        weeks {
                            contributionDays {
                                contributionCount
                                date
                            }
                        }
                    }
                }
            }
        }
    '''
    payload = {
        'query': QUERY,
        'variables': {
            'userName': username,
            'fromDate': f"{year}-01-01T00:00:00Z",
            'toDate': f"{year}-12-31T23:59:59Z"
        }
    }
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.post(
            GITHUB_GRAPHQL_URL,
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException as e:
        print(f"Error fetching GitHub data: {e}")
        return {}


@app.get("/contributions_graph")
async def get_contributions(username: str):
    if not username:
        return {"error": "Username is required"}

    contribution_data = retrieve_contribution_data(username, "2024")
    contributionCalendar = contribution_data['data']['user']['contributionsCollection']['contributionCalendar']
    weeks = contributionCalendar['weeks']
    contributions_array = []
    for week in weeks:
        contributions_array.append(week['contributionDays'])
    return contributions_array


@app.get("/account_stats")
async def get_account_stats(username: str):
    if not username:
        return {"error": "Username is required"}

    response_data = {}
    contribution_data = retrieve_contribution_data(username, "2024")
    contributionCalendar = contribution_data['data']['user']['contributionsCollection']['contributionCalendar']
    weeks = contributionCalendar['weeks']
    contributions_dict = {}
    contributions_array = []
    highest_contributions_date = "NA"
    highest_contributions = 0
    monthly_contributions = defaultdict(int)
    for week in weeks:
        contributions_array.append(week['contributionDays'])
        for day in week['contributionDays']:
            date_object = datetime.strptime(day['date'], "%Y-%m-%d")
            month_key = date_object.strftime("%B")
            monthly_contributions[month_key] += day['contributionCount']
            if day['contributionCount'] > highest_contributions:
                highest_contributions_date = day['date']
                highest_contributions = day['contributionCount']
            contributions_dict[day['date']] = day['contributionCount']

    date_object = datetime.strptime(highest_contributions_date, "%Y-%m-%d")

    highest_contributions_date = date_object.strftime("%B %d")
    response_data['highest_contributions'] = highest_contributions
    response_data['highest_contributions_date'] = highest_contributions_date
    busiest_month = max(monthly_contributions, key=monthly_contributions.get)
    response_data['busiest_month'] = busiest_month
    response_data['busiest_month_contributions'] = monthly_contributions[busiest_month]

    longest_streak = 0
    current_streak = 0
    sorted_dates = sorted(contributions_dict.keys())

    for i in range(len(sorted_dates)):
        if contributions_dict[sorted_dates[i]] > 0:
            current_streak += 1
            longest_streak = max(longest_streak, current_streak)
        else:
            current_streak = 0

    daily_contributions = [0] * 7

    response_data['longest_streak'] = longest_streak

    for week in contributions_array:
        for day_index, contributions in enumerate(week):
            daily_contributions[day_index] += contributions['contributionCount']

    busiest_day_index = daily_contributions.index(max(daily_contributions))
    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    busiest_day = days[busiest_day_index]
    response_data['total_contributions'] = contributionCalendar['totalContributions']
    response_data['busiest_day'] = busiest_day
    old_contribution_data = retrieve_contribution_data(username, "2023")
    old_contributions_count = old_contribution_data['data']['user']['contributionsCollection']['contributionCalendar']['totalContributions']
    contri_difference = contributionCalendar['totalContributions'] - old_contributions_count
    response_data['adjective'] = "more" if contri_difference > 0 else "less"
    response_data['contribution_difference'] = abs(contri_difference)
    contribution_percentage = abs((contributionCalendar['totalContributions'] - old_contributions_count) / old_contributions_count) * 100
    response_data['contribution_percentage'] = round(contribution_percentage, 2)
    return response_data
