import requests
import json

files = {
    'resume': open('input/resume.pdf', 'rb'),
    'csv': open('input/candidate.csv', 'rb'),
    'linkedin': open('input/linkedin.txt', 'rb'),
    'recruiter_notes': open('input/recruiter_notes.txt', 'rb'),
    'links': open('input/links.json', 'rb')
}

response = requests.post('http://127.0.0.1:8000/process', files=files)
print(f"Status Code: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print("Candidate Profile extracted successfully!")
    print(json.dumps(data.get('candidate', {}), indent=2))
else:
    print(response.text)
