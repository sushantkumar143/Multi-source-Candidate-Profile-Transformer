import requests
import json

def run_test():
    try:
        files = {
            'resume': open('input/candidates/sushant_kumar/resume.pdf', 'rb'),
            'csv': open('input/candidates/sushant_kumar/candidate.csv', 'rb'),
            'linkedin': open('input/candidates/sushant_kumar/linkedin.txt', 'rb'),
            'recruiter_notes': open('input/candidates/sushant_kumar/recruiter_notes.txt', 'rb'),
            'links': open('input/candidates/sushant_kumar/links.json', 'rb')
        }
    except FileNotFoundError:
        # Fallback for dummy candidate if sushant_kumar is not present
        files = {
            'resume': open('input/candidates/dummy_candidate/resume.pdf', 'rb'),
            'csv': open('input/candidates/dummy_candidate/candidate.csv', 'rb'),
            'linkedin': open('input/candidates/dummy_candidate/linkedin.txt', 'rb'),
            'recruiter_notes': open('input/candidates/dummy_candidate/recruiter_notes.txt', 'rb'),
            'links': open('input/candidates/dummy_candidate/links.json', 'rb')
        }

    response = requests.post('http://127.0.0.1:8000/process', files=files)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("Candidate Profile extracted successfully!")
        print(json.dumps(data.get('candidate', {}), indent=2))
    else:
        print(response.text)

if __name__ == '__main__':
    run_test()
