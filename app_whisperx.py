import streamlit as st
import os
import subprocess
import dotenv
dotenv.load_dotenv()

HF_TOKEN = os.environ.get("HUGGING_FACE_TOKEN")
def main():
    st.title("Whisperx Processing and Summary Generation")

    # File selector for the user to select the input video
    video_file = st.file_uploader("Choose a video file")
    if video_file:
        video_path = f"./temp/{video_file.name}"  # Change to an appropriate temp path
        with open(video_path, "wb") as f:
            f.write(video_file.read())
    else:
        st.warning("Please upload a video file.")
        return

    # Fields for the user to set parameters
    language = st.selectbox("Select Language", ["en", "pt", "es", "fr"])
    output_format = st.selectbox("Select Output Format", ["all", "txt", "srt"])
    min_speakers = st.slider("Min Speakers", 1, 10, 3)
    max_speakers = st.slider("Max Speakers", 1, 10, 4)

    # Fields for API /generate-summary
    MEETING_TITLE = st.text_input("Meeting Title")
    MEETING_EXTRA_INFO = st.text_area("Extra Meetings Information")
    SPEAKERS_INFO = st.text_area("Speakers Information")
    claude_model = st.selectbox(
        "Select Claude Model", ["claude-2.0", "claude-instant-1"]
    )
    output_file_name = st.text_input("Output File Name for Summary", "_ata.txt")

    if st.button("Process and Generate Summary"):
        # Run the whisperx script
        cmd = [
            "whisperx",
            video_path,
            "--model",
            "large-v2",
            "--language",
            language,
            "--hf_token",
            "{HF_TOKEN}",
            "--output_format",
            output_format,
            "--output_dir",
            "./data/namastex/",
            "--diarize",
            "--min_speakers",
            str(min_speakers),
            "--max_speakers",
            str(max_speakers),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        st.write(result.stdout)

    st.write("Select and set parameters to start processing.")


if __name__ == "__main__":
    main()
