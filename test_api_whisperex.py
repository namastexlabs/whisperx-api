import requests

# Assuming your FastAPI app is running on localhost:11300
url = "http://localhost:11300/whisperex-transcribe/"

with open("./test_whatever.mp3", "rb") as file:
    response = requests.post(
        url,
        files={"file": file},
        data={"min_speakers": 1, "max_speakers": 2},
    )

print(response.json())
