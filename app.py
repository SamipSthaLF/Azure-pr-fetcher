from flask import Flask, request, render_template, jsonify
import requests
from requests.auth import HTTPBasicAuth
import re
from openai import OpenAI
import markdown
from asgiref.wsgi import WsgiToAsgi  # Import WSGI to ASGI adapter


# Initialize the Flask application
app = Flask(__name__)

# Function to clean description by removing unwanted sections, "---", and extra spaces
def clean_description(description):
    if not description:
        return ""
    
    # Remove sections starting with "Tested on", "Testing proof", "Tests", or "Testing"
    description = re.sub(r"Tested on:.*", "", description, flags=re.DOTALL)
    description = re.sub(r"Testing proof:.*", "", description, flags=re.DOTALL)
    description = re.sub(r"Tests:.*", "", description, flags=re.DOTALL)
    description = re.sub(r"Testing:.*", "", description, flags=re.DOTALL)
    description = re.sub(r"Note for Reviewer:.*", "", description, flags=re.DOTALL)

    # Remove all occurrences of "---"
    description = description.replace('---', '')

    # Remove excessive empty lines and leading/trailing whitespace
    description = re.sub(r'\n\s*\n+', '\n', description)  # Replaces multiple empty lines with a single line
    description = description.strip()  # Remove leading/trailing spaces

    return description

# Route to handle the form input and fetch pull requests
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        organization = request.form['organization']
        project = request.form['project']
        repository = request.form['repository']
        pat = request.form['pat']
        main_branch = request.form['main_branch']
        date_filter = request.form['date_filter']
        openai_api_key = request.form['openai_api_key']

        # API URL for Azure Repos pull requests
        url = f'https://dev.azure.com/{organization}/{project}/_apis/git/repositories/{repository}/pullrequests?api-version=7.1-preview.1'

        # Define headers and authentication for requests
        headers = {'Content-Type': 'application/json'}
        auth = HTTPBasicAuth('', pat)

        # Parameters to filter pull requests
        params = {
            'searchCriteria.status': 'completed',  # Only pull requests with completed status
            'searchCriteria.targetRefName': main_branch,  # PRs merged into the main branch
            'searchCriteria.creationDate': date_filter  # Filter for PRs created after this date
        }

        # Send GET request to Azure DevOps API
        response = requests.get(url, headers=headers, auth=auth, params=params)

        if response.status_code == 200:
            pull_requests = response.json().get('value', [])
            pr_details = []

            # Collect pull request data
            for pr in pull_requests:
                cleaned_description = clean_description(pr['description'])
                pr_details.append({
                    'title': pr['title'],
                    'description': cleaned_description,
                    'url': pr['url']
                })

            # Pass the pull request details and OpenAI key as JSON
            return render_template('results.html', pull_requests=pr_details, openai_api_key=openai_api_key)

        else:
            return f"Failed to retrieve data. Status code: {response.status_code}. Response: {response.text}"

    return render_template('index.html')

# Route to handle generating release notes using OpenAI
@app.route("/release_notes", methods=["POST"])
def generate_release_notes():
    openai_api_key = request.form['openai_api_key']
    pr_details = request.form['pr_details']

    client = OpenAI(api_key = openai_api_key)
    prompt = f"{pr_details}\n\nCan you turn these pull requests into release notes."

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user", "content": prompt
                }
            ]
        )

        release_notes = response.choices[0].message.content

        release_notes = markdown.markdown(release_notes)


        return render_template('release_notes.html', release_notes=release_notes)

    except Exception as e:
        return f"Failed to generate release notes: {str(e)}"

asgi_app = WsgiToAsgi(app)
